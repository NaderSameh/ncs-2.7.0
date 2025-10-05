import struct
import ipaddress
from typing import Optional, List, Dict

FLAG_SEQUENCE = 0x7E
ADDRESS_FIELD = 0xFF
CONTROL_FIELD = 0x03


def escape_bytes(data: bytes) -> bytes:
    """Escape control characters, flag, and escape bytes (RFC1662)."""
    escaped = bytearray()
    for b in data:
        if b < 0x20 or b in (0x7E, 0x7D):
            escaped.append(0x7D)
            escaped.append(b ^ 0x20)
        else:
            escaped.append(b)
    return bytes(escaped)


def unescape_bytes(data: bytes) -> bytes:
    """Reverse RFC1662 escaping."""
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b == 0x7D and i + 1 < n:
            out.append(data[i + 1] ^ 0x20)
            i += 2
        else:
            out.append(b)
            i += 1
    return bytes(out)


def compute_fcs(data: bytes) -> int:
    """Compute PPP FCS (CRC-16-CCITT, reversed polynomial)."""
    fcs = 0xFFFF
    for b in data:
        fcs ^= b
        for _ in range(8):
            if fcs & 1:
                fcs = (fcs >> 1) ^ 0x8408
            else:
                fcs >>= 1
    return (~fcs) & 0xFFFF


def build_ppp_frame(protocol: int, payload: bytes) -> bytes:
    """
    Build PPP frame with RFC1662 HDLC-like framing:
    - Flag (0x7E) start/end
    - Escaped content
    - Protocol big-endian
    - FCS little-endian
    """
    header = struct.pack("!BBH", 0xFF, 0x03, protocol)  # FF 03 + protocol (big endian)
    fcs = compute_fcs(header + payload)
    fcs_bytes = struct.pack("<H", fcs)  # FCS is little-endian
    body = escape_bytes(header + payload + fcs_bytes)
    return bytes([0x7E]) + body + bytes([0x7E])


def build_ppp_frame_for_cmux(protocol: int, payload: bytes) -> bytes:
    """
    Build PPP frame content for embedding in CMUX (no 0x7E frame delimiters):
    - Just escaped content with protocol and FCS
    - For use inside CMUX UIH frames
    """
    header = struct.pack("!BBH", 0xFF, 0x03, protocol)  # FF 03 + protocol (big endian)
    fcs = compute_fcs(header + payload)
    fcs_bytes = struct.pack("<H", fcs)  # FCS is little-endian
    body = escape_bytes(header + payload + fcs_bytes)
    return body  # NO 0x7E delimiters for CMUX embedding


def _strip_fcs(data: bytes):
    """Return tuple (without_fcs, valid_fcs: bool)."""
    if len(data) < 2:
        return data, False
    without = data[:-2]
    sent_fcs = int.from_bytes(data[-2:], "little")
    calc_fcs = compute_fcs(without)
    return without, sent_fcs == calc_fcs


def parse_ppp_frames(stream: bytes):
    """Extract and parse PPP frames from a raw CMUX payload stream.
    Returns a list of dicts with keys: protocol, payload, control (for LCP/IPCP), raw.
    The 'control' value is a dict with code, id, length, options (raw options bytes) for control protocols.
    Accepts ACFC (Address/Control Field Compression) and PFC (Protocol Field Compression).
    """
    frames = []
    # Split on 0x7E flag boundaries, ignoring empty segments
    seg = bytearray()
    for b in stream:
        if b == FLAG_SEQUENCE:
            if seg:
                frames.append(bytes(seg))
                seg.clear()
        else:
            seg.append(b)
    # If trailing buffer without closing flag, ignore it for simplicity
    result = []
    for fr in frames:
        data = unescape_bytes(fr)
        if len(data) < 2 + 2:  # minimal proto + FCS
            continue
        # Strip FCS (last 2 bytes)
        core, fcs_ok = _strip_fcs(data)
        if len(core) < 1:
            continue
        i = 0
        # Handle ACFC: if starts with FF 03, consume them; else assume ACFC
        if len(core) >= 2 and core[0] == ADDRESS_FIELD and core[1] == CONTROL_FIELD:
            i = 2
        # Parse protocol with/without PFC
        if i >= len(core):
            continue
        if core[i] & 0x01:  # could be 1-byte PFC (e.g., 0x21 for IPv4)
            proto = core[i]
            i += 1
            # Expand to 16-bit value for consistency
            if proto < 0x100:
                proto = proto
        else:
            if i + 1 >= len(core):
                continue
            proto = (core[i] << 8) | core[i + 1]
            i += 2
        payload = core[i:]
        entry = {"protocol": proto, "payload": payload, "raw": fr, "fcs_ok": fcs_ok}
        # Control protocols (LCP 0xC021, IPCP 0x8021, IPv6CP 0x8057) start with Code, Id, Length
        if proto in (0xC021, 0x8021, 0x8057) and len(payload) >= 4:
            code, ident, length = struct.unpack("!BBH", payload[:4])
            opts = payload[4:length] if length <= len(payload) else payload[4:]
            entry["control"] = {"code": code, "id": ident, "length": length, "options": opts}
        result.append(entry)
    return result


def build_conf_ack(protocol: int, identifier: int, options: bytes) -> bytes:
    payload = struct.pack("!BBH", 2, identifier, 4 + len(options)) + options
    return build_ppp_frame(protocol, payload)


def build_lcp_conf_req(identifier: int, options: bytes = b"") -> bytes:
    """Build LCP Configure-Request (Code=1) with given identifier and options."""
    payload = struct.pack("!BBH", 1, identifier, 4 + len(options)) + options
    return build_ppp_frame(0xC021, payload)


def build_lcp_conf_ack(identifier: int, options: bytes) -> bytes:
    return build_conf_ack(0xC021, identifier, options)


def build_ipcp_conf_ack(identifier: int, options: bytes) -> bytes:
    return build_conf_ack(0x8021, identifier, options)


def build_ipv6cp_conf_ack(identifier: int, options: bytes) -> bytes:
    return build_conf_ack(0x8057, identifier, options)


def build_ipcp_conf_nak(identifier: int, ip_addr: str, dns1: str = None, dns2: str = None) -> bytes:
    """Build an IPCP Configure-Nak proposing our IP and optionally DNS servers.
    - IP-Address option type=3, len=6
    - Primary DNS option type=129, len=6 (RFC1877)
    - Secondary DNS option type=131, len=6 (RFC1877)
    """
    options = bytearray()
    ip_packed = ipaddress.IPv4Address(ip_addr).packed
    options += struct.pack("!BB", 3, 6) + ip_packed
    if dns1:
        options += struct.pack("!BB", 129, 6) + ipaddress.IPv4Address(dns1).packed
    if dns2:
        options += struct.pack("!BB", 131, 6) + ipaddress.IPv4Address(dns2).packed
    payload = struct.pack("!BBH", 3, identifier, 4 + len(options)) + bytes(options)
    return build_ppp_frame(0x8021, payload)


def build_lcp_echo_reply(identifier: int, data: bytes = b"") -> bytes:
    """Build LCP Echo-Reply (Code=10) with same Identifier and optional data."""
    payload = struct.pack("!BBH", 10, identifier, 4 + len(data)) + data
    return build_ppp_frame(0xC021, payload)


def build_lcp_echo_req(identifier: int, data: bytes = b"") -> bytes:
    """Build LCP Echo-Request (Code=9) with Identifier and optional data."""
    # Return just the LCP payload, not wrapped in PPP frame
    payload = struct.pack("!BBH", 9, identifier, 4 + len(data)) + data
    return payload


def _ip_checksum(data: bytes) -> int:
    s = 0
    # Sum 16-bit words
    for i in range(0, len(data), 2):
        w = data[i] << 8
        if i + 1 < len(data):
            w |= data[i + 1]
        s += w
        s = (s & 0xFFFF) + (s >> 16)
    return (~s) & 0xFFFF


def _icmp_checksum(data: bytes) -> int:
    # ICMP uses same 16-bit one's complement
    return _ip_checksum(data)


def build_ppp_ipv4_icmp_echo(src_ip: str, dst_ip: str, ident: int = 1, seq: int = 1) -> bytes:
    """Build a PPP frame (proto 0x0021) carrying a minimal IPv4 ICMP Echo Request."""
    src = ipaddress.IPv4Address(src_ip).packed
    dst = ipaddress.IPv4Address(dst_ip).packed
    # ICMP Echo Request: type=8, code=0, checksum=0, id, seq, no payload
    icmp_hdr = struct.pack("!BBHHH", 8, 0, 0, ident & 0xFFFF, seq & 0xFFFF)
    icmp_ck = _icmp_checksum(icmp_hdr)
    icmp_hdr = struct.pack("!BBHHH", 8, 0, icmp_ck, ident & 0xFFFF, seq & 0xFFFF)

    # IPv4 header
    version_ihl = (4 << 4) | 5
    tos = 0
    total_len = 20 + len(icmp_hdr)
    identification = 0
    flags_frag = 0
    ttl = 64
    proto = 1  # ICMP
    hdr_ck = 0
    iphdr = struct.pack("!BBHHHBBH4s4s", version_ihl, tos, total_len, identification, flags_frag, ttl, proto, hdr_ck, src, dst)
    hdr_ck = _ip_checksum(iphdr)
    iphdr = struct.pack("!BBHHHBBH4s4s", version_ihl, tos, total_len, identification, flags_frag, ttl, proto, hdr_ck, src, dst)

    ipv4_payload = iphdr + icmp_hdr
    return build_ppp_frame(0x0021, ipv4_payload)


def build_ipcp_conf_req(identifier: int, ip_addr: str, dns1: Optional[str] = None, dns2: Optional[str] = None) -> bytes:
    """Build an IPCP Configure-Request proposing our IP (type=3) and optional DNS servers (129/131)."""
    options = bytearray()
    options += struct.pack("!BB", 3, 6) + ipaddress.IPv4Address(ip_addr).packed
    if dns1:
        options += struct.pack("!BB", 129, 6) + ipaddress.IPv4Address(dns1).packed
    if dns2:
        options += struct.pack("!BB", 131, 6) + ipaddress.IPv4Address(dns2).packed
    payload = struct.pack("!BBH", 1, identifier, 4 + len(options)) + bytes(options)
    return build_ppp_frame(0x8021, payload)


# Example: LCP Configure-Request (minimal)

def lcp_configure_request():
    # Code=1 (Configure-Request), Identifier=1, Length=8
    # Option: MRU (type=1, length=4, value=1500)
    code = 1
    identifier = 1
    length = 8
    option_type = 1
    option_len = 4
    mru = 1500

    return struct.pack("!BBHBBH", code, identifier, length, option_type, option_len, mru)


def lcp_configure_request_with_options(ident: int) -> bytes:
    """Build LCP Configure-Request with NO options (Zephyr rejects MRU)"""
    # Send empty LCP Configure-Request like a real modem that doesn't need options
    options = bytearray()  # No options
    
    length = 4 + len(options)
    frame = bytearray([1, ident, (length >> 8) & 0xFF, length & 0xFF])
    frame.extend(options)
    return bytes(frame)


def lcp_configure_request_no_options(ident: int) -> bytes:
    """Build LCP Configure-Request with NO options (since Zephyr rejects MRU)"""
    # Send empty LCP Configure-Request like a real modem that doesn't need options
    options = bytearray()  # No options
    
    length = 4 + len(options)
    frame = bytearray([1, ident, (length >> 8) & 0xFF, length & 0xFF])
    frame.extend(options)
    return bytes(frame)


def build_pap_auth_ack(ident: int, message: bytes) -> bytes:
    """Build PAP Authentication-Ack"""
    msg_len = len(message)
    length = 5 + msg_len
    frame = bytearray([2, ident, (length >> 8) & 0xFF, length & 0xFF, msg_len])
    frame.extend(message)
    return bytes(frame)


def build_ipcp_conf_req_with_dns(ident: int) -> bytes:
    """Build IPCP Configure-Request with IP and DNS options (like real modem)"""
    options = bytearray()
    
    # Option 3: IP Address - propose our IP
    options.extend([0x03, 0x06, 10, 0, 0, 1])  # 10.0.0.1
    
    # Option 129: Primary DNS 
    options.extend([0x81, 0x06, 8, 8, 8, 8])  # 8.8.8.8
    
    # Option 131: Secondary DNS
    options.extend([0x83, 0x06, 8, 8, 4, 4])  # 8.8.4.4
    
    length = 4 + len(options)
    frame = bytearray([1, ident, (length >> 8) & 0xFF, length & 0xFF])
    frame.extend(options)
    return bytes(frame)


def build_ipv6cp_conf_req(ident: int) -> bytes:
    """Build IPv6CP Configure-Request"""
    options = bytearray()
    
    # Option 1: Interface Identifier - 8 bytes 
    options.extend([0x01, 0x0A, 0x86, 0x3F, 0xFE, 0x37, 0x33, 0x38, 0x9A, 0xD7])
    
    length = 4 + len(options)
    frame = bytearray([1, ident, (length >> 8) & 0xFF, length & 0xFF])
    frame.extend(options)
    return bytes(frame)


def ipcp_configure_request(ident: int) -> bytes:
    """Build IPCP Configure-Request"""
    # Send empty IPCP Configure-Request (no options needed for basic setup)
    options = bytearray()
    
    length = 4 + len(options)
    frame = bytearray([1, ident, (length >> 8) & 0xFF, length & 0xFF])
    frame.extend(options)
    return bytes(frame)


def ipv6cp_configure_request(ident: int) -> bytes:
    """Build IPv6CP Configure-Request"""
    # Send empty IPv6CP Configure-Request (no options needed for basic setup)
    options = bytearray()
    
    length = 4 + len(options)
    frame = bytearray([1, ident, (length >> 8) & 0xFF, length & 0xFF])
    frame.extend(options)
    return bytes(frame)



class PPPStream:
    """Stateful PPP frame deframer.
    Feed raw bytes (possibly partial) and get parsed PPP frames out.
    Keeps leftover between calls to handle frames split across CMUX frames/reads.
    """
    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> List[Dict]:
        # Append new data
        self._buf.extend(data)
        frames = []
        # Find complete frames between 0x7E flags. Multiple can be present.
        start = 0
        out_frames = []
        while True:
            try:
                # Find next flag
                idx_flag = self._buf.index(FLAG_SEQUENCE, start)
            except ValueError:
                # No more flags
                break
            # If there is data since last start and we found a flag, that's a frame segment
            if idx_flag > start:
                out_frames.append(bytes(self._buf[start:idx_flag]))
            # Move start to after this flag
            start = idx_flag + 1
        # Keep trailing data after last flag as leftover
        self._buf = bytearray(self._buf[start:])
        # Parse collected raw frame bodies
        result = []
        for fr in out_frames:
            # Each 'fr' is the content between flags; let existing parser handle it by re-adding flags
            parsed = parse_ppp_frames(bytes([FLAG_SEQUENCE]) + fr + bytes([FLAG_SEQUENCE]))
            result.extend(parsed)
        return result
