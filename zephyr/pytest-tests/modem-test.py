import socket
import time
import pytest
from conftest import zephyr_base
from cmux_frames import build_ua, build_uih, split_cmux_frames, parse_cmux_frame, build_uih_frame
from ppp_stub import (
    lcp_configure_request, build_ppp_frame,
    parse_ppp_frames, build_ipcp_conf_nak, build_ipcp_conf_ack, build_lcp_conf_ack, build_lcp_echo_reply,
    build_ipcp_conf_req, build_ppp_ipv4_icmp_echo, PPPStream, build_lcp_conf_req,
    lcp_configure_request_with_options, lcp_configure_request_no_options, build_pap_auth_ack,
    build_ipcp_conf_req_with_dns, build_ipv6cp_conf_req,
    build_ipv6cp_conf_ack, build_lcp_echo_req, ipcp_configure_request, ipv6cp_configure_request
)
from pathlib import Path

@pytest.fixture(scope="module")
def elf_path():
    return zephyr_base / "samples/modem_test/build/zephyr/zephyr.elf"  # adjust as needed

# -------------------- Persistent-socket helpers --------------------

def sock_send_immediate(sock: socket.socket, payload):
    """Send data immediately without any buffering"""
    try:
        # Disable Nagle's algorithm to send immediately
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
        # Send the payload
        sock.sendall(payload)
        
        # Force OS-level flush
        try:
            import os
            if hasattr(os, 'fsync'):
                os.fsync(sock.fileno())
        except:
            pass
        
        # Force socket flush if available
        if hasattr(sock, 'flush'):
            sock.flush()
            
        print(f"Sent frame with immediate flush")
        
    except Exception as e:
        print(f"Socket send error: {e}")
        # Fall back to normal send
        sock.sendall(payload)

def sock_send(sock: socket.socket, payload, *, as_bytes: bool = False):
    if as_bytes:
        print(f"DEBUG: Sending CMUX frame: {payload.hex()}")
        sock.sendall(payload)
        time.sleep(0.02)  # Small delay to avoid OS buffering/concatenation
    else:
        if isinstance(payload, str):
            sock.sendall(payload.encode())
        else:
            sock.sendall(bytes(payload))


def sock_recv_line(sock: socket.socket, timeout: float = 1.0) -> str:
    end = time.time() + timeout
    buf = bytearray()
    sock.setblocking(False)
    while time.time() < end:
        try:
            chunk = sock.recv(1024)
            if chunk:
                buf += chunk
                # look for CR/LF and strip NULs
                for sep in (b"\r\n", b"\n", b"\r"):
                    idx = buf.find(sep)
                    if idx != -1:
                        line = bytes(buf[:idx]).decode(errors="replace").strip("\x00\r\n")
                        # keep remaining in buffer for next reads if needed (simple approach: discard)
                        return line
        except BlockingIOError:
            pass
        time.sleep(0.02)
    # timeout: return whatever was read (trimmed)
    return bytes(buf).decode(errors="replace").strip("\x00\r\n")


def sock_recv_bytes(sock: socket.socket, timeout: float = 1.0) -> bytes:
    end = time.time() + timeout
    buf = bytearray()
    sock.setblocking(False)
    while time.time() < end:
        try:
            chunk = sock.recv(4096)
            if chunk:
                buf += chunk
                # heuristics: small pause after first data
                time.sleep(0.05)
                break
        except BlockingIOError:
            pass
        time.sleep(0.02)
    return bytes(buf)


# -------------------- CMUX streaming deframer --------------------

class CMUXStream:
    """Stateful CMUX frame deframer buffering between reads.
    Feed raw bytes and get a list of complete frames (FLAG..FLAG) out.
    """
    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        if not data:
            return []
        self._buf.extend(data)
        out = []
        while True:
            # Find BOF
            try:
                start = self._buf.index(b"\xF9")
            except ValueError:
                # No flag at all, drop old bytes
                self._buf.clear()
                break
            # Find EOF after BOF
            try:
                end = self._buf.index(b"\xF9", start + 1)
            except ValueError:
                # Keep from BOF onward for next time, drop any preamble
                if start > 0:
                    del self._buf[:start]
                break
            # Extract one full frame
            out.append(bytes(self._buf[start:end+1]))
            # Remove through EOF
            del self._buf[:end+1]
        return out


# -------------------- CMUX/AT helpers --------------------

def get_at_command_cmux(sock: socket.socket, *, expected: bytes, timeout: float = 5.0, prebuffer: list | None = None, cmux: CMUXStream | None = None):
    """Wait for a CMUX UIH frame whose payload (minus CR/LF/NUL) matches or starts with expected.
    While waiting, auto-respond to common periodic queries to avoid stalling the script.
    """
    def norm(p):
        return (p.get("payload") or b"").rstrip(b"\r\n\x00")

    def maybe_answer_periodic(p):
        pl = norm(p)
        if pl in (b"AT", b"AT+CREG=1", b"AT+CGREG=1", b"AT+CEREG=1"):
            ok = build_uih_frame(dlci=p['dlci'], cr=p['cr'], pf=1, payload=b"OK\r")
            sock_send(sock, ok, as_bytes=True)
            return True
        if pl == b"AT+CREG?":
            resp = build_uih_frame(dlci=p['dlci'], cr=p['cr'], pf=1, payload=b"+CREG: 0,5\r")
            ok = build_uih_frame(dlci=p['dlci'], cr=p['cr'], pf=1, payload=b"OK\r")
            sock_send(sock, resp, as_bytes=True); sock_send(sock, ok, as_bytes=True)
            return True
        if pl == b"AT+CGREG?":
            resp = build_uih_frame(dlci=p['dlci'], cr=p['cr'], pf=1, payload=b"+CGREG: 0,5\r")
            ok = build_uih_frame(dlci=p['dlci'], cr=p['cr'], pf=1, payload=b"OK\r")
            sock_send(sock, resp, as_bytes=True); sock_send(sock, ok, as_bytes=True)
            return True
        if pl == b"AT+CEREG?":
            resp = build_uih_frame(dlci=p['dlci'], cr=p['cr'], pf=1, payload=b"+CEREG: 0,5\r")
            ok = build_uih_frame(dlci=p['dlci'], cr=p['cr'], pf=1, payload=b"OK\r")
            sock_send(sock, resp, as_bytes=True); sock_send(sock, ok, as_bytes=True)
            return True
        if pl == b"AT+CSQ":
            resp = build_uih_frame(dlci=p['dlci'], cr=p['cr'], pf=1, payload=b"+CSQ: 15,99\r")
            ok = build_uih_frame(dlci=p['dlci'], cr=p['cr'], pf=1, payload=b"OK\r")
            sock_send(sock, resp, as_bytes=True); sock_send(sock, ok, as_bytes=True)
            return True
        return False

    # Check prebuffer first
    if prebuffer is not None:
        i = 0
        while i < len(prebuffer):
            p = prebuffer[i]
            if (p.get("ctrl", 0) & 0xEF) == 0xEF:
                pl = norm(p)
                if pl == expected or pl.startswith(expected):
                    return prebuffer.pop(i)
                if maybe_answer_periodic(p):
                    prebuffer.pop(i)
                    continue
            i += 1
    end = time.time() + timeout
    cmux = cmux or CMUXStream()
    while time.time() < end:
        raw = sock_recv_bytes(sock, 1.0)
        if not raw:
            continue
        frames = cmux.feed(raw)
        for f in frames:
            try:
                p = parse_cmux_frame(f)
            except Exception:
                continue
            if (p.get("ctrl", 0) & 0xEF) == 0xEF:
                pl = norm(p)
                if pl == expected or pl.startswith(expected):
                    return p
                maybe_answer_periodic(p)
    return None


def handle_cmux_handshake(sock: socket.socket, timeout: float = 10.0, dlcis=(0, 1, 2), prebuffer: list | None = None, cmux: CMUXStream | None = None):
    """Respond UA to incoming SABM frames for given DLCIs. Buffer any non-SABM frames into prebuffer."""
    end = time.time() + timeout
    open_set = set()
    cmux = cmux or CMUXStream()
    while time.time() < end and open_set != set(dlcis):
        raw = sock_recv_bytes(sock, 0.5)
        if not raw:
            continue
        frames = cmux.feed(raw)
        for f in frames:
            try:
                p = parse_cmux_frame(f)
            except Exception:
                continue
            ctrl = p.get("ctrl", 0)
            # SABM base 0x2F (PF could be set)
            if (ctrl & ~0x10) == 0x2F and p.get("dlci") in dlcis:
                dlci = p["dlci"]
                # reply UA with opposite C/R bit and PF=1 to be explicit
                cr_reply = 1 - (p.get("cr", 0) & 1)
                ua = build_ua(dlci=dlci, cr=cr_reply, pf=1)
                sock_send(sock, ua, as_bytes=True)
                open_set.add(dlci)
            else:
                # Buffer non-SABM frames so higher layers can process them
                if prebuffer is not None:
                    prebuffer.append(p)
    return open_set == set(dlcis)


def serve_cmux_at(sock: socket.socket, duration: float = 20.0):
    """Handle AT commands over CMUX on DLCI 1 for a while to satisfy periodic scripts."""
    end = time.time() + duration
    while time.time() < end:
        raw = sock_recv_bytes(sock, 0.5)
        if not raw:
            continue
        frames = split_cmux_frames(raw)
        for f in frames:
            try:
                p = parse_cmux_frame(f)
            except Exception:
                continue
            payload = p.get("payload", b"")
            if not payload:
                continue
            
            # Use centralized AT command handler
            handle_at_command(sock, p['dlci'], p['cr'], payload)


# -------------------- Original helpers, adapted to persistent socket --------------------

def send_and_receive(sock, message, timeout=2.0):
    sock.settimeout(timeout)
    sock_send(sock, message)
    time.sleep(0.1)
    try:
        resp = sock.recv(1024).decode(errors="replace")
    except socket.timeout:
        resp = ""
    return resp.strip()


def send_only(sock, message, timeout=1.0, *, as_bytes=False):
    sock.settimeout(timeout)
    sock_send(sock, message, as_bytes=as_bytes)


def recieve_only(sock, timeout=1.0):
    return sock_recv_line(sock, timeout)


def recieve_only_any(sock, timeout=1.0):
    return sock_recv_bytes(sock, timeout)


# -------------------- New: drain raw AT until CMUX --------------------

def drain_until_cmux(sock: socket.socket, timeout: float = 30.0) -> bool:
    """Consume raw AT commands (including periodic queries) until AT+CMUX arrives.
    Respond appropriately to keep firmware happy. Returns True if CMUX cmd handled.
    """
    end = time.time() + timeout
    # Known responses for queries; now report registered (0,5)
    query_resp = {
        "AT+CREG?": "+CREG: 0,5",
        "AT+CEREG?": "+CEREG: 0,5",
        "AT+CGREG?": "+CGREG: 0,5",
    }
    ok_only = {"AT", "AT+CREG=1", "AT+CEREG=1", "AT+CGREG=1"}
    while time.time() < end:
        line = sock_recv_line(sock, timeout=2.0)
        if not line:
            continue
        # Normalize whitespace
        line = line.strip()
        if line.startswith("AT+CMUX="):
            # Acknowledge CMUX setup
            send_only(sock, "OK\r\n")
            return True
        if line in query_resp:
            send_only(sock, f"{query_resp[line]}\r\n")
            send_only(sock, "OK\r\n")
            continue
        if line in ok_only:
            send_only(sock, "OK\r\n")
            continue
        # Ignore unrelated noise
    return False


def wait_for_log_patterns(start_offset: int, patterns, timeout: float = 30.0, logfile: Path = Path("qemu_logs.txt")) -> bool:
    """Tail qemu_logs.txt from start_offset and look for any of the patterns."""
    end = time.time() + timeout
    offset = start_offset
    while time.time() < end:
        try:
            size = logfile.stat().st_size
            if size > offset:
                with open(logfile, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(offset)
                    chunk = f.read()
                    offset = f.tell()
                    for p in patterns:
                        if p in chunk:
                            return True
        except FileNotFoundError:
            pass
        time.sleep(0.2)
    return False


# -------------------- PPP IPCP driver over CMUX --------------------

def detect_ppp_dlci(sock: socket.socket, sniff_time: float = 2.0, default_dlci: int = 1) -> int:
    """Sniff CMUX UIH payloads and identify which DLCI carries PPP.
    Uses PPPStream deframing and looks for valid PPP protocols (LCP/IPCP/IPv4).
    Returns the detected DLCI, or default_dlci if none found.
    """
    end = time.time() + sniff_time
    deframers = {}
    guess = default_dlci
    while time.time() < end:
        raw = sock_recv_bytes(sock, 0.5)
        if not raw:
            continue
        frames = split_cmux_frames(raw)
        for f in frames:
            try:
                p = parse_cmux_frame(f)
            except Exception:
                continue
            if (p.get("ctrl", 0) & 0xEF) != 0xEF:
                continue
            dlci = p.get("dlci")
            payload = p.get("payload", b"")
            if not payload:
                continue
            df = deframers.setdefault(dlci, PPPStream())
            try:
                parsed = df.feed(payload)
            except Exception:
                parsed = []
            for pf in parsed:
                proto = pf.get("protocol")
                # Consider it PPP if we see typical protocols, even if FCS invalid
                if proto in (0xC021, 0x8021, 0x0021, 0xC023, 0x8057):
                    return dlci
            # Heuristic fallback: if we see many 0x7E HDLC flags in payload, update guess
            if payload.count(b"\x7E") >= 1:
                guess = dlci
    return guess


def handle_at_command(sock: socket.socket, dlci: int, cr: int, payload: bytes, *, 
                     detect_carrier_on: bool = False, 
                     detect_periodic_complete: bool = False) -> dict:
    """Handle a single AT command and send appropriate response.
    Returns dict with keys: 'handled', 'carrier_on_detected', 'periodic_script_complete'
    """
    pl = payload.rstrip(b"\r\n")
    result = {'handled': False, 'carrier_on_detected': False, 'periodic_script_complete': False}
    
    if pl in (b"AT+CREG=1", b"AT+CEREG=1", b"AT+CGREG=1", b"AT"):
        # Configuration commands - just respond OK
        ok = build_uih_frame(dlci=dlci, cr=cr, pf=1, payload=b"OK\r")
        sock_send_immediate(sock, ok)
        print(f"Responded to AT config command: {pl.decode('utf-8', errors='ignore')} on DLCI {dlci}")
        result['handled'] = True
        
    elif pl in (b"AT+CREG?", b"AT+CEREG?", b"AT+CGREG?"):
        # Registration status queries - respond with registered status
        if pl == b"AT+CREG?":
            resp = build_uih_frame(dlci=dlci, cr=cr, pf=1, payload=b"+CREG: 0,5\r")
        elif pl == b"AT+CEREG?":
            resp = build_uih_frame(dlci=dlci, cr=cr, pf=1, payload=b"+CEREG: 0,5\r")
        elif pl == b"AT+CGREG?":
            resp = build_uih_frame(dlci=dlci, cr=cr, pf=1, payload=b"+CGREG: 0,5\r")
        
        ok = build_uih_frame(dlci=dlci, cr=cr, pf=1, payload=b"OK\r")
        sock_send_immediate(sock, resp)
        sock_send_immediate(sock, ok)
        print(f"Responded to registration query: {pl.decode('utf-8', errors='ignore')} on DLCI {dlci}")
        result['handled'] = True
        
        # Mark carrier on as detected after first registration query if requested
        if detect_carrier_on:
            result['carrier_on_detected'] = True
            print("Carrier on detected via registration query")
        
    elif pl == b"AT+CSQ":
        # Signal quality query
        resp = build_uih_frame(dlci=dlci, cr=cr, pf=1, payload=b"+CSQ: 15,99\r")
        ok = build_uih_frame(dlci=dlci, cr=cr, pf=1, payload=b"OK\r")
        sock_send_immediate(sock, resp)
        sock_send_immediate(sock, ok)
        print(f"Responded to signal quality query on DLCI {dlci}")
        result['handled'] = True
        
        # AT+CSQ is the last command in the periodic script if requested
        if detect_periodic_complete:
            result['periodic_script_complete'] = True
            print("Periodic script completed - ready for PPP negotiation")
        
    elif pl == b"AT+CGACT?":
        # PDP context activation status query
        resp = build_uih_frame(dlci=dlci, cr=cr, pf=1, payload=b"+CGACT: 1,1\r")
        ok = build_uih_frame(dlci=dlci, cr=cr, pf=1, payload=b"OK\r")
        sock_send_immediate(sock, resp)
        sock_send_immediate(sock, ok)
        print(f"Responded to PDP context query on DLCI {dlci}")
        result['handled'] = True
        
    elif pl.startswith(b"AT+CGACT="):
        # PDP context activation command
        ok = build_uih_frame(dlci=dlci, cr=cr, pf=1, payload=b"OK\r")
        sock_send_immediate(sock, ok)
        print(f"Responded to PDP context activation on DLCI {dlci}")
        result['handled'] = True
        
    elif pl.startswith(b"AT+CGDCONT="):
        # PDP context definition command
        ok = build_uih_frame(dlci=dlci, cr=cr, pf=1, payload=b"OK\r")
        sock_send_immediate(sock, ok)
        print(f"Responded to PDP context definition on DLCI {dlci}")
        result['handled'] = True
        
    # Add more AT commands as needed
    return result


def handle_ppp_on_cmux(sock: socket.socket, *, my_ip: str = "10.0.0.2", dns1: str = "8.8.8.8", dns2: str = "1.1.1.1", timeout: float = 45.0, ppp_dlci: int = 1) -> bool:
    """Act as a cellular modem PPP server on DLCI 1.
    - Wait for Zephyr to initialize PPP stack (after carrier on)
    - Respond to Zephyr's LCP Configure-Request and send our own
    - Wait for Zephyr to initiate IPCP negotiation or start it ourselves
    - Assign IP address through IPCP NAK/ACK flow
    - Handle periodic AT commands on any DLCI to prevent timeouts
    
    This follows cellular modem behavior where PPP negotiation starts after carrier on.
    """
    print(f"Waiting for Zephyr to initialize PPP stack (after carrier on)...")
    
    # Wait for carrier on state while handling AT commands to prevent timeouts
    carrier_on_detected = False
    detect_start = time.time()
    cmux = CMUXStream()
    
    end = time.time() + timeout
    ip_assigned = False
    lcp_established = False
    lcp_req_sent = False
    lcp_negotiation_started = False
    ipcp_negotiation_started = False
    last_ack_time = 0
    lcp_configure_req_id = 1  # Track our own Configure-Request ID
    next_ident = 10  # Starting identifier for our Configure-Requests
    
    # Track negotiation state  
    zephyr_ip = "10.0.0.1"  # IP we'll assign to Zephyr
    ipcp_we_acked_zephyr = False  # Did we ack Zephyr's IPCP Configure-Request?
    ipcp_zephyr_acked_us = False  # Did Zephyr ack our IPCP Configure-Request?
    ipv6cp_we_acked_zephyr = False  # Did we ack Zephyr's IPv6CP Configure-Request?
    ipv6cp_zephyr_acked_us = False  # Did Zephyr ack our IPv6CP Configure-Request?
    
    print(f"Starting PPP server on DLCI {ppp_dlci} (hybrid mode)")
    
    # Stateful PPP deframers per DLCI
    deframers = {ppp_dlci: PPPStream()}
    
    # Wait for carrier on, then give extra time for PPP interface to come up
    print("Waiting for Zephyr interface to come up after carrier on...")
    carrier_on_detected = False
    
    # Track when periodic script completes
    periodic_script_complete = False

    while time.time() < end and not ip_assigned:
        current_time = time.time()
        
        raw = sock_recv_bytes(sock, 0.2)
        frames = split_cmux_frames(raw) if raw else []
        for f in frames:
            try:
                p = parse_cmux_frame(f)
            except Exception:
                continue
            if (p.get("ctrl", 0) & 0xEF) != 0xEF:
                continue
            dlci = p.get("dlci")
            payload = p.get("payload", b"")
            if not payload:
                continue
            
            # Handle periodic AT commands on any DLCI to prevent timeouts
            pl = payload.rstrip(b"\r\n")  # Strip both \r and \n
            
            # Try to handle as AT command first
            at_result = handle_at_command(sock, dlci, p['cr'], payload, 
                                        detect_carrier_on=(not carrier_on_detected),
                                        detect_periodic_complete=(not periodic_script_complete))
            
            if at_result['handled']:
                if at_result['carrier_on_detected']:
                    carrier_on_detected = True
                if at_result['periodic_script_complete']:
                    periodic_script_complete = True
                continue
                
            # Process PPP frames only on the PPP DLCI
            if dlci != ppp_dlci:
                continue
                
            df = deframers.setdefault(dlci, PPPStream())
            for pf in df.feed(payload):
                proto = pf["protocol"]
                ctrl = pf.get("control")
                print(f"Received PPP frame: proto=0x{proto:04x}, ctrl={ctrl}")
                
                if proto == 0xC021:  # LCP
                    if ctrl and ctrl.get("code") == 1:  # ConfReq from Zephyr
                        ident = ctrl["id"]
                        opts = ctrl["options"]
                        print(f"Received LCP Configure-Request (id={ident}) - establishing LCP")
                        
                        # Send Configure-Ack to accept Zephyr's LCP options
                        ack = build_lcp_conf_ack(ident, opts)
                        ui_ack = build_uih_frame(dlci=dlci, cr=1, pf=1, payload=ack)
                        
                        # Debug: log the frame we're about to send
                        print(f"DEBUG: Sending LCP Ack frame: {ui_ack.hex()[:60]}...")
                        
                        sock_send_immediate(sock, ui_ack)
                        print(f"Sent LCP Configure-Ack (id={ident}) - FRAME ISOLATED")
                        last_ack_time = time.time()  # Fixed variable name
                        
                        # DO NOT send our own Configure-Request - wait to see if Zephyr transitions to OPENED
                        print("Waiting for Zephyr to reach LCP OPENED state...")
                        
                    elif ctrl and ctrl.get("code") == 2:  # ConfAck from Zephyr
                        print("LCP established successfully!")
                        lcp_established = True
                        
                        # DON'T send anything else - wait for Zephyr to initiate IPCP/IPv6CP
                        print("LCP complete - waiting for Zephyr to initiate next protocols...")
                        
                    elif ctrl and ctrl.get("code") == 4:  # ConfReject from Zephyr
                        ident = ctrl["id"] 
                        rejected_opts = ctrl["options"]
                        print(f"Received LCP Configure-Reject (id={ident}) - options rejected: {rejected_opts.hex()}")
                        
                        # Resend LCP Configure-Request without rejected options (should be none now)
                        time.sleep(0.1)
                        retry_lcp = lcp_configure_request_with_options(ident)
                        ppp_req = build_ppp_frame(0xC021, retry_lcp)
                        ui_req = build_uih_frame(dlci=dlci, cr=1, pf=1, payload=ppp_req)
                        sock_send(sock, ui_req, as_bytes=True)
                        print(f"Resent LCP Configure-Request (id={ident}) with NO OPTIONS")
                        
                    elif ctrl and ctrl.get("code") == 9:  # Echo-Request
                        ident = ctrl["id"]
                        data = pf["payload"][4:ctrl["length"]]
                        echo = build_lcp_echo_reply(ident, data)
                        ui = build_uih_frame(dlci=dlci, cr=1, pf=1, payload=echo)
                        sock_send(sock, ui, as_bytes=True)
                        print(f"Replied to LCP Echo-Request (id={ident})")
                        
                elif proto == 0x8021 and ctrl:  # IPCP 
                    code = ctrl["code"]
                    ident = ctrl["id"]
                    opts = ctrl["options"]
                    print(f"Received IPCP: code={code}, id={ident}")
                    
                    if code == 1:  # ConfReq from Zephyr - ACK it and send our own request
                        print(f"ACKing IPCP Configure-Request (id={ident}) immediately")
                        ack = build_ipcp_conf_ack(ident, opts)
                        print(f"DEBUG: IPCP ack frame: {ack.hex()}")
                        ui = build_uih_frame(dlci=dlci, cr=1, pf=1, payload=ack)
                        print(f"DEBUG: IPCP ack in CMUX: {ui.hex()}")
                        sock_send(sock, ui, as_bytes=True)
                        print("Sent IPCP Configure-Ack")
                        ipcp_we_acked_zephyr = True
                        
                        # Now send our own Configure-Request to complete negotiation
                        print("Sending our IPCP Configure-Request (without DNS)")
                        # Use simple IPCP request without DNS to avoid rejection
                        our_req = build_ipcp_conf_req(next_ident, "10.0.0.2")  # No DNS options
                        ui_req = build_uih_frame(dlci=dlci, cr=1, pf=1, payload=our_req)
                        sock_send(sock, ui_req, as_bytes=True)
                        next_ident += 1
                        print("Sent our IPCP Configure-Request")
                        
                        # Check if IPCP is fully negotiated
                        if ipcp_we_acked_zephyr and ipcp_zephyr_acked_us:
                            ip_assigned = True
                            print("IPCP fully negotiated!")
                            
                    elif code == 2:  # ConfAck from Zephyr to our IPCP request
                        print("Received IPCP Configure-Ack from Zephyr")
                        ipcp_zephyr_acked_us = True
                        
                        # Check if IPCP is fully negotiated
                        if ipcp_we_acked_zephyr and ipcp_zephyr_acked_us:
                            ip_assigned = True
                            print("IPCP fully negotiated!")
                    
                    elif code == 4:  # Configure-Reject from Zephyr
                        print("Received IPCP Configure-Reject from Zephyr - resending without rejected options")
                        # Resend Configure-Request without the rejected options (just IP)
                        our_req = build_ipcp_conf_req(next_ident, "10.0.0.2")  # Only IP, no DNS
                        ui_req = build_uih_frame(dlci=dlci, cr=1, pf=1, payload=our_req)
                        sock_send(sock, ui_req, as_bytes=True)
                        next_ident += 1
                        print("Resent IPCP Configure-Request (simplified)")
                        
                elif proto == 0x8057 and ctrl:  # IPv6CP
                    code = ctrl["code"] 
                    ident = ctrl["id"]
                    opts = ctrl["options"]
                    print(f"Received IPv6CP: code={code}, id={ident}")
                    
                    if code == 1:  # Configure-Request - ACK it and send our own request
                        print(f"ACKing IPv6CP Configure-Request (id={ident}) immediately")
                        conf_ack = build_ipv6cp_conf_ack(ident, opts)
                        ui = build_uih_frame(dlci=dlci, cr=1, pf=1, payload=conf_ack)
                        sock_send(sock, ui, as_bytes=True)
                        print("Sent IPv6CP Configure-Ack")
                        ipv6cp_we_acked_zephyr = True
                        
                        # Now send our own Configure-Request to complete negotiation
                        print("Sending our IPv6CP Configure-Request")
                        our_req_payload = build_ipv6cp_conf_req(next_ident)
                        our_req = build_ppp_frame(0x8057, our_req_payload)
                        ui_req = build_uih_frame(dlci=dlci, cr=1, pf=1, payload=our_req)
                        sock_send(sock, ui_req, as_bytes=True)
                        next_ident += 1
                        print("Sent our IPv6CP Configure-Request")
                        
                        # Check if IPv6CP is fully negotiated
                        if ipv6cp_we_acked_zephyr and ipv6cp_zephyr_acked_us:
                            ipv6_configured = True
                            print("IPv6CP fully negotiated!")
                        return 0
                        
                    elif code == 2:  # ConfAck from Zephyr to our IPv6CP request
                        print("Received IPv6CP Configure-Ack from Zephyr")
                        ipv6cp_zephyr_acked_us = True
                        
                        # Check if IPv6CP is fully negotiated 
                        if ipv6cp_we_acked_zephyr and ipv6cp_zephyr_acked_us:
                            ipv6_configured = True
                            print("IPv6CP fully negotiated!")
                        
                elif proto == 0xC023 and ctrl:  # PAP
                    code = ctrl["code"]
                    ident = ctrl["id"]
                    print(f"Received PAP: code={code}, id={ident}")
                    
                    if code == 1:  # Auth-Request from Zephyr
                        print("Received PAP Auth-Request - sending success")
                        pap_success = build_pap_auth_ack(ident, b"Login ok")
                        ppp_pap = build_ppp_frame(0xC023, pap_success)
                        ui_pap = build_uih_frame(dlci=dlci, cr=1, pf=1, payload=ppp_pap)
                        sock_send(sock, ui_pap, as_bytes=True)
                        print("Sent PAP Auth-Ack")
                    else:
                        print(f"Unhandled PAP code: {code}")
                    
                else:
                    # Debug: log any unhandled PPP protocols
                    print(f"Unhandled PPP protocol: 0x{proto:04x} (ctrl={ctrl})")
                    # Debug: log any unhandled PPP protocols
                    print(f"Unhandled PPP protocol: 0x{proto:04x} (ctrl={ctrl})")
        
        # Check if we need to send our LCP Configure-Request after timeout
        if last_ack_time > 0 and not lcp_req_sent and (time.time() - last_ack_time) > 2.0:
            print("Timeout reached - sending our LCP Configure-Request to complete negotiation")
            our_lcp = lcp_configure_request_no_options(lcp_configure_req_id)
            ppp_req = build_ppp_frame(0xC021, our_lcp)
            ui_req = build_uih_frame(dlci=ppp_dlci, cr=1, pf=1, payload=ppp_req)
            
            # Debug: log the frame we're about to send
            print(f"DEBUG: Sending LCP Req frame: {ui_req.hex()[:60]}...")
            
            sock_send_immediate(sock, ui_req)
            print(f"Sent LCP Configure-Request (id={lcp_configure_req_id}) with NO OPTIONS")
            lcp_req_sent = True
            lcp_configure_req_id += 1
                        
        time.sleep(0.02)
    
    if ip_assigned:
        print(f"IPCP negotiation successful! Zephyr should have IP {zephyr_ip}")
        return zephyr_ip



# -------------------- New: handle raw PPP negotiation without CMUX wrapping --------------------

def handle_raw_ppp_negotiation(sock: socket.socket, my_ip: str, dns1: str, dns2: str, timeout: float) -> bool:
    """Handle PPP negotiation using raw PPP frames (no CMUX wrapping)."""
    end_time = time.time() + timeout
    ip_assigned = False
    
    ppp_stream = PPPStream()
    sock.setblocking(False)  # Set non-blocking mode
    
    while time.time() < end_time:
        try:
            # Receive data and parse PPP frames
            data = sock.recv(1024)
            if data:
                # Feed data to PPP stream parser
                for ppp_frame in ppp_stream.feed(data):
                    proto = ppp_frame["protocol"]
                    ctrl = ppp_frame.get("control")
                    
                    if proto == 0xC021:  # LCP
                        if ctrl and ctrl.get("code") == 1:  # ConfReq
                            ident = ctrl["id"]
                            opts = ctrl["options"]
                            ack = build_lcp_conf_ack(ident, opts)
                            sock_send(sock, ack, as_bytes=True)
                        elif ctrl and ctrl.get("code") == 9:  # Echo-Request
                            ident = ctrl["id"]
                            data_len = ctrl["length"]
                            echo_data = ppp_frame["payload"][4:data_len] if data_len > 4 else b""
                            echo = build_lcp_echo_reply(ident, echo_data)
                            sock_send(sock, echo, as_bytes=True)
                            
                    elif proto == 0x8021 and ctrl:  # IPCP
                        code = ctrl["code"]
                        ident = ctrl["id"]
                        opts = ctrl["options"]
                        
                        if code == 2:  # ConfAck
                            ip_assigned = True
                            
                        elif code == 1:  # ConfReq from Zephyr
                            # Parse IP address from options
                            have_ip = False
                            ip_val = None
                            i = 0
                            while i + 2 <= len(opts):
                                opt_len = opts[i+1]
                                if opt_len < 2 or i + opt_len > len(opts):
                                    break
                                opt_type = opts[i]
                                if opt_type == 3 and opt_len == 6:  # IP address option
                                    have_ip = True
                                    ip_bytes = opts[i+2:i+6]
                                    if len(ip_bytes) == 4:
                                        ip_val = ".".join(str(b) for b in ip_bytes)
                                i += opt_len
                                
                            if have_ip and ip_val not in (None, "0.0.0.0"):
                                # Accept the IP request
                                ack = build_ipcp_conf_ack(ident, opts)
                                sock_send(sock, ack, as_bytes=True)
                            else:
                                # Propose our IP
                                nak = build_ipcp_conf_nak(ident, my_ip, dns1, dns2)
                                sock_send(sock, nak, as_bytes=True)
                                
        except BlockingIOError:
            pass
        except Exception as e:
            print(f"Error in raw PPP negotiation: {e}")
            
        time.sleep(0.05)
        
    # Send a proactive IPCP Configure-Request to help establish IP
    try:
        conf_req = build_ipcp_conf_req(my_ip, dns1, dns2)
        sock_send(sock, conf_req, as_bytes=True)
    except Exception:
        pass
    
    return ip_assigned


# -------------------- Test --------------------

def test_modem_start(qemu, uart_sock):
    s = uart_sock

    # Mark current end of qemu log so we only scan new lines for assertions later
    log_path = Path("qemu_logs.txt")
    try:
        start_off = log_path.stat().st_size
    except FileNotFoundError:
        start_off = 0

    # Pre-CMUX AT dialog on raw UART
    response = recieve_only(s, 90)
    assert response == "ATE0", f"Expected 'ATE0', got '{response}'"
    time.sleep(0.1)
    send_only(s, "OK\r\n")

    response = recieve_only(s, 5)
    assert response == "AT+CGSN", f"Expected 'AT+CGSN', got '{response}'"
    send_only(s, "+CGSN 80008000800\r\n")
    time.sleep(0.1)
    send_only(s, "OK\r\n")

    response = recieve_only(s, 5)
    assert response == "AT+QCFG=\"nwscanmode\",0,1", f"Expected 'nwscanmode', got '{response}'"
    time.sleep(0.1)
    send_only(s, "OK\r\n")

    response = recieve_only(s, 5)
    assert response == "AT+QDSIM=0", f"Expected 'AT+QDSIM=1', got '{response}'"
    time.sleep(0.1)
    send_only(s, "OK\r\n")

    response = recieve_only(s, 5)
    assert response == "AT+QCCID", f"Expected 'AT+QCCID', got '{response}'"
    send_only(s, "+QCCID: 100010001000\r\n")
    send_only(s, "OK\r\n")

    response = recieve_only(s, 5)
    assert response == "AT+CFUN=4", f"Expected 'AT+CFUN=4', got '{response}'"
    time.sleep(0.2)
    send_only(s, "OK\r\n")

    response = recieve_only(s, 5)
    assert response == "AT+CREG=1", f"Expected 'AT+CREG=1', got '{response}'"
    time.sleep(0.1)
    send_only(s, "OK\r\n")

    response = recieve_only(s, 5)
    assert response == "AT+CGREG=1", f"Expected 'AT+CGREG=1', got '{response}'"
    time.sleep(0.1)
    send_only(s, "OK\r\n")

    response = recieve_only(s, 90)
    assert response == "AT+CEREG=1", f"Expected 'AT+CEREG=1', got '{response}'"
    time.sleep(0.1)
    send_only(s, "OK\r\n")

    response = recieve_only(s, 5)
    assert response == "AT+CREG?", f"Expected 'AT+CREG?', got '{response}'"
    time.sleep(0.1)
    send_only(s, "+CREG: 0,5\r\n")
    send_only(s, "OK\r\n")

    # Remove unsolicited pre-CMUX URCs; let drain_until_cmux answer any further queries

    # Expect CMUX setup request at some point; handle periodic queries if they interleave
    assert drain_until_cmux(s, timeout=30.0), "Timed out waiting for AT+CMUX while handling periodic queries"

    # After OK to AT+CMUX, the firmware will shift to CMUX and send SABM frames
    time.sleep(0.2)

    # Respond UA to SABMs for DLCI 0/1/2 and buffer other frames using CMUX deframer
    prebuf: list = []
    cmux = CMUXStream()
    handled = handle_cmux_handshake(s, timeout=10.0, dlcis=(0, 1, 2), prebuffer=prebuf, cmux=cmux)
    assert handled, "Failed to complete CMUX SABM/UA handshake"

    # Handle AT dialog inside CMUX first (use prebuffer to catch early frames)
    res = get_at_command_cmux(s, expected=b"AT+CFUN=1", timeout=20, prebuffer=prebuf, cmux=cmux)
    assert res and (res['payload'] or b'').rstrip(b'\r\n\x00').startswith(b'AT+CFUN=1')
    at_dlci = res['dlci']
    ok = build_uih_frame(dlci=at_dlci, cr=res['cr'], pf=1, payload=b'OK\r')
    send_only(s, ok, as_bytes=True)

    res = get_at_command_cmux(s, expected=b"AT+CGACT=0,1", timeout=20, prebuffer=prebuf, cmux=cmux)
    assert res and (res['payload'] or b'').rstrip(b'\r\n\x00').startswith(b'AT+CGACT=0,1')
    ok = build_uih_frame(dlci=res['dlci'], cr=res['cr'], pf=1, payload=b'OK\r')
    send_only(s, ok, as_bytes=True)

    res = get_at_command_cmux(s, expected=b'AT+CGDCONT=1,"IP","internet"', timeout=20, prebuffer=prebuf, cmux=cmux)
    assert res and (res['payload'] or b'').rstrip(b'\r\n\x00').startswith(b'AT+CGDCONT=1,"IP","internet"')
    ok = build_uih_frame(dlci=res['dlci'], cr=res['cr'], pf=1, payload=b'OK\r')
    send_only(s, ok, as_bytes=True)

    res = get_at_command_cmux(s, expected=b'ATD*99***1#', timeout=25, prebuffer=prebuf, cmux=cmux)
    assert res and (res['payload'] or b'').rstrip(b'\r\n\x00').startswith(b'ATD*99***1#')
    
    # In Zephyr's design, no CONNECT response is sent - the DLCI silently switches to PPP mode
    # after ATD*99***1#. This matches the MODEM_CHAT_SCRIPT_CMD_RESP_NONE behavior.
    ppp_dlci = res['dlci']  # The DLCI that received ATD*99***1# becomes the PPP DLCI
    print(f"PPP DLCI: {ppp_dlci} (no CONNECT response sent, switching to PPP mode)")
    time.sleep(0.5)  # Brief pause to let Zephyr initiate PPP
    
    # Act as PPP server - wait for Zephyr to initiate LCP, don't send initial LCP ourselves
    print(f"Starting PPP server on DLCI {ppp_dlci} (waiting for client to initiate)...")
    got_ip = handle_ppp_on_cmux(s, my_ip="10.0.0.2", dns1="8.8.8.8", dns2="1.1.1.1", timeout=60.0, ppp_dlci=ppp_dlci)
    print(f"IPCP negotiation result: {got_ip}")
    

    res = get_at_command_cmux(s, expected=b"AT+CCLK?", timeout=20, prebuffer=prebuf, cmux=cmux)
    assert res and (res['payload'] or b'').rstrip(b'\r\n\x00').startswith(b'AT+CCLK?')
    at_dlci = res['dlci']
    ok = build_uih_frame(dlci=at_dlci, cr=res['cr'], pf=1, payload=b'+CCLK: "25/09/28,10:08:41+00"\r')
    send_only(s, ok, as_bytes=True)
    qemu_log_path = Path("qemu_logs.txt")
    assert qemu_log_path.exists(), "QEMU logs file not found"
    log_content = qemu_log_path.read_text()
    assert "1759054121" in log_content, "Expected timestamp not found in QEMU logs"

    res = get_at_command_cmux(s, expected=b"AT+QIACT=3", timeout=20, prebuffer=prebuf, cmux=cmux)
    assert res and (res['payload'] or b'').rstrip(b'\r\n\x00').startswith(b'AT+QIACT=3')
    at_dlci = res['dlci']
    ok = build_uih_frame(dlci=at_dlci, cr=res['cr'], pf=1, payload=b'OK\r')
    send_only(s, ok, as_bytes=True)

    res = get_at_command_cmux(s, expected=b"AT+QLBSCFG=\"contextid\",3", timeout=20, prebuffer=prebuf, cmux=cmux)
    assert res and (res['payload'] or b'').rstrip(b'\r\n\x00').startswith(b'AT+QLBSCFG=\"contextid\",3')
    at_dlci = res['dlci']
    ok = build_uih_frame(dlci=at_dlci, cr=res['cr'], pf=1, payload=b'OK\r')
    send_only(s, ok, as_bytes=True)

    res = get_at_command_cmux(s, expected=b"AT+QLBSCFG=\"token\",\"41q7p1007W1861f5\"", timeout=20, prebuffer=prebuf, cmux=cmux)
    assert res and (res['payload'] or b'').rstrip(b'\r\n\x00').startswith(b'AT+QLBSCFG=\"token\",\"41q7p1007W1861f5\"')
    at_dlci = res['dlci']
    ok = build_uih_frame(dlci=at_dlci, cr=res['cr'], pf=1, payload=b'OK\r')
    send_only(s, ok, as_bytes=True)
    
    res = get_at_command_cmux(s, expected=b"AT+QLBSCFG=\"asynch\",0", timeout=20, prebuffer=prebuf, cmux=cmux)
    assert res and (res['payload'] or b'').rstrip(b'\r\n\x00').startswith(b'AT+QLBSCFG=\"asynch\",0')
    at_dlci = res['dlci']
    ok = build_uih_frame(dlci=at_dlci, cr=res['cr'], pf=1, payload=b'OK\r')
    send_only(s, ok, as_bytes=True)

    res = get_at_command_cmux(s, expected=b"AT+QLBS", timeout=20, prebuffer=prebuf, cmux=cmux)
    assert res and (res['payload'] or b'').rstrip(b'\r\n\x00').startswith(b'AT+QLBS')
    at_dlci = res['dlci']
    resp = build_uih_frame(dlci=at_dlci, cr=res['cr'], pf=1, payload=b'+QLBS: 0,30.121239,31.364294\r')
    ok = build_uih_frame(dlci=at_dlci, cr=res['cr'], pf=1, payload=b'OK\r')
    send_only(s, resp, as_bytes=True)
    send_only(s, ok, as_bytes=True)


    # Continue to service CMUX AT commands on other DLCIs while PPP runs
    serve_cmux_at(s, duration=25.0)  # Extended duration to allow L4_CONNECTED event

    # Optional: read back some PPP response bytes (ignore content for now)
    _ = recieve_only_any(s, 2.0)

    # Keep test short; firmware should now proceed with registration path
    time.sleep(0.5)

    # Assert registration based on firmware logs (longer timeout)
    ok = wait_for_log_patterns(
        start_offset=start_off,
        patterns=[
            "modem_cellular_log_event: event registered",
            "switch from await registered to carrier on",
            "HEREEEEEEE!!!!",  # This indicates NET_EVENT_L4_CONNECTED was received
        ],
        timeout=120.0,  # Extended timeout for L4_CONNECTED
        logfile=log_path,
    )
    assert ok, "Modem did not reach L4_CONNECTED state within timeout"

def serve_cmux_at_separate(sock: socket.socket, duration: float, at_dlci: int):
    """Handle AT commands on the AT DLCI while PPP DLCI is in raw mode."""
    end_time = time.time() + duration
    cmux_deframer = CMUXStream()
    sock.setblocking(False)  # Set non-blocking mode
    
    while time.time() < end_time:
        try:
            data = sock.recv(1024)
            if data:
                # Parse CMUX frames on AT DLCI only
                for frame in cmux_deframer.feed(data):
                    dlci = frame['dlci']
                    payload = frame['payload']
                    
                    # Only handle AT commands on the AT DLCI
                    if dlci != at_dlci:
                        continue
                        
                    # Use centralized AT command handler
                    at_result = handle_at_command(sock, dlci, frame['cr'], payload)
                    # Note: we don't use the detection flags here since this is during PPP
                    
        except BlockingIOError:
            pass
        except Exception as e:
            print(f"Error in CMUX AT handling: {e}")
            
        time.sleep(0.05)
