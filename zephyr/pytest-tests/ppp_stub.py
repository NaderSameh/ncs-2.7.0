import struct

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
