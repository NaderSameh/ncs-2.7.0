import socket
import time
import pytest
from conftest import zephyr_base
from cmux_frames import build_ua, build_uih, send_frame_tcp, build_sabm, split_cmux_frames, parse_cmux_frame, build_uih_frame
from ppp_stub import (
    lcp_configure_request,build_ppp_frame
)

@pytest.fixture(scope="module")
def elf_path():
    return zephyr_base / "samples/modem_test/build_1/zephyr/zephyr.elf"  # adjust as needed

def send_and_receive(host, port, message, timeout=2.0):
    """Connect to UART over TCP, send a message, and receive the echo."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(message.encode())

        # Allow QEMU time to echo back
        time.sleep(0.1)

        try:
            response = sock.recv(1024).decode()
        except socket.timeout:
            response = ""

        return response.strip()

def send_only(host, port, message, timeout=1.0, bytes=False):
    """Connect to UART over TCP, send a message"""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        if bytes:
            sock.sendall(message)
        else:
            sock.sendall(message.encode())
        return b''



def recieve_only(host, port, timeout=1.0):
    """Connect to UART over TCP, receive a message"""
    end_time = time.time() + timeout
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.setblocking(False)
        data = b""
        while time.time() < end_time:
            try:
                chunk = sock.recv(1024)
                if chunk:
                    data += chunk
                    break
            except BlockingIOError:
                pass
            time.sleep(0.05)
        return data.decode().strip('\x00\r\n')

def recieve_only_any(host, port, timeout=1.0):
    """Connect to UART over TCP, receive a message"""
    end_time = time.time() + timeout
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.setblocking(False)
        data = b""
        while time.time() < end_time:
            try:
                chunk = sock.recv(1024)
                if chunk:
                    data += chunk
                    break
            except BlockingIOError:
                pass
            time.sleep(0.05)
        return data
    
def get_at_command(host,port, expected=b"AT+CFUN=1"):
    for _ in range(10):  # retry a few times
        raw = recieve_only_any(host, port, 5)
        frames = split_cmux_frames(raw)
        if not frames:
            continue
        parsed = [parse_cmux_frame(f) for f in frames if f]
        for p in parsed:
            if p and p.get("payload") == expected:
                return p
    return None



import struct
import binascii

PPP_FLAG = 0x7E
PPP_ADDR = 0xFF
PPP_CTRL = 0x03

# Protocols
PPP_LCP = 0xC021
PPP_IPCP = 0x8021

def ppp_fcs16(data: bytes) -> int:
    """Calculate PPP FCS16."""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    crc ^= 0xFFFF
    return crc & 0xFFFF

def ppp_frame(protocol: int, payload: bytes) -> bytes:
    """Wrap payload in PPP frame."""
    header = struct.pack("!BBH", PPP_ADDR, PPP_CTRL, protocol)
    data = header + payload
    fcs = ppp_fcs16(data)
    data += struct.pack("<H", fcs)  # little-endian per PPP
    return bytes([PPP_FLAG]) + data + bytes([PPP_FLAG])

def build_lcp_confreq(ident: int = 1) -> bytes:
    """Build a simple LCP Configure-Request frame."""
    # Code=1 (ConfReq), ID, Length
    # No options = minimal request
    code = 1
    options = b''  # we could add MRU, ACCM, etc
    length = 4 + len(options)
    payload = struct.pack("!BBH", code, ident, length) + options
    return ppp_frame(PPP_LCP, payload)

def ppp_async_escape(data: bytes) -> bytes:
    out = bytearray()
    for b in data:
        if b == 0x7E:          # FLAG
            out += b'\x7D\x5E'
        elif b == 0x7D:        # ESC
            out += b'\x7D\x5D'
        else:
            out.append(b)
    return bytes(out)


def ppp_build_frame(protocol: int, payload: bytes) -> bytes:
    header = struct.pack("!BBH", PPP_ADDR, PPP_CTRL, protocol)  # FF 03 + proto
    core = header + payload
    fcs = ppp_fcs16(core)
    core += struct.pack("<H", fcs)  # little-endian FCS

    # Async-escape the *core*, then add 0x7E flags around it
    esc = ppp_async_escape(core)
    return bytes([PPP_FLAG]) + esc + bytes([PPP_FLAG])


import os

def lcp_confreq(ident: int = 1) -> bytes:
    # Code=1 (ConfReq), ID, Length (options below)
    opts = bytearray()

    # MRU 1500 -> type 1, len 4, value 0x05DC
    opts += bytes([0x01, 0x04, 0x05, 0xDC])

    # Magic-Number (random 4 bytes) -> type 5, len 6
    magic = os.urandom(4)
    opts += bytes([0x05, 0x06]) + magic

    code = 0x01
    length = 4 + len(opts)
    payload = struct.pack("!BBH", code, ident, length) + opts
    return ppp_build_frame(PPP_LCP, payload)


def test_modem_start(qemu):

    host = "localhost"
    port = 1235
    # send_only(host, port, "RDY\r\n")
    # send_only(host, port, "APP RDY\r\n")
    response = recieve_only(host,port,90)
    assert response == "ATE0", f"Expected 'ATE0', got '{response}'"
    time.sleep(0.1)
    send_only(host, port, "OK\r\n")
    response = recieve_only(host,port,5)
    assert response == "AT+CGSN", f"Expected 'AT+CGSN', got '{response}'"
    send_only(host, port, "+CGSN 80008000800\r\n")
    time.sleep(0.1)
    send_only(host, port, "OK\r\n")
    response = recieve_only(host,port,5)
    assert response == "AT+QCFG=\"nwscanmode\",0,1", f"Expected 'nwscanmode', got '{response}'"
    time.sleep(0.1)
    send_only(host, port, "OK\r\n")
    response = recieve_only(host,port,5)
    assert response == "AT+QDSIM=1", f"Expected 'AT+QDSIM=1', got '{response}'"
    time.sleep(0.1)
    send_only(host, port, "OK\r\n")
    response = recieve_only(host,port,5)
    assert response == "AT+QCCID", f"Expected 'AT+QCCID', got '{response}'"
    # time.sleep(0.1)
    send_only(host, port, "+QCCID: 100010001000\r\n")
    send_only(host, port, "OK\r\n")
    response = recieve_only(host,port,5)
    assert response == "AT+CFUN=4", f"Expected 'AT+CFUN=4', got '{response}'"
    time.sleep(0.2)
    send_only(host, port, "OK\r\n")
    response = recieve_only(host,port,5)
    assert response == "AT+CREG=1", f"Expected 'AT+CREG=1', got '{response}'"
    time.sleep(0.1)
    send_only(host, port, "OK\r\n")
    response = recieve_only(host,port,5)
    assert response == "AT+CGREG=1", f"Expected 'AT+CGREG=1', got '{response}'"
    time.sleep(0.1)
    send_only(host, port, "OK\r\n")
    response = recieve_only(host,port,90)
    assert response == "AT+CEREG=1", f"Expected 'AT+CEREG=1', got '{response}'"
    time.sleep(0.1)
    send_only(host, port, "OK\r\n")
    response = recieve_only(host,port,5)
    assert response == "AT+CREG?", f"Expected 'AT+CREG?', got '{response}'"
    time.sleep(0.1)
    send_only(host, port, "+CREG: 0,2\r\n")
    send_only(host, port, "OK\r\n")
    # assert response == "AT+CEREG?", f"Expected 'AT+CEREG?', got '{response}'"
    time.sleep(0.1)
    send_only(host, port, "+CEREG: 0,2\r\n")
    send_only(host, port, "OK\r\n")
    # assert response == "AT+CGREG?", f"Expected 'AT+CGREG?', got '{response}'"
    time.sleep(0.1)
    send_only(host, port, "+CGREG: 0,2\r\n")
    send_only(host, port, "OK\r\n")
    response = recieve_only(host,port,5)
    if response == "AT+CREG?":
        response = recieve_only_any(host,port,5)
        assert response == b'AT+CMUX=0,0,5,127,10,3,30,10,2\r', f"Expected 'AT+CMUX=0,0,5,127,10,3,30,10,2', got '{response}'"
    # assert response == "AT+CMUX=0,0,5,127,10,3,30,10,2", f"Expected 'AT+CMUX=0,0,5,127,10,3,30,10,2', got '{response}'"
    time.sleep(0.1)
    response = recieve_only_any(host,port,30)
    assert bytes(response) == bytes(b'\xf9\x03?\x01\x1c\xf9')


    f=build_ua(dlci=0,cr=1,pf=1)
    f2=build_ua(dlci=1,cr=1,pf=1)
    f3=build_ua(dlci=2,cr=1,pf=1)
    b=build_sabm(dlci=0, cr=1, pf=1)
    b2=build_sabm(dlci=1, cr=1, pf=1)
    b3=build_sabm(dlci=2, cr=1, pf=1)
    b4=build_sabm(dlci=3, cr=1, pf=1)
    u1= build_uih(0, 0, 0, b'\xe3\x07\x07\x0d\x01')
    # u2= build_uih(2, 0, 0)

    send_only(host, port,f,bytes=True)  # Example frame for UA DLCI0 (needs correct FCS)
    send_only(host, port,b,bytes=True) 
    # time.sleep(0.1)
    send_only(host, port,b2,bytes=True) 
    send_only(host, port,f2,bytes=True) 
    # time.sleep(0.1)
    send_only(host, port,u1,bytes=True)
    # time.sleep(0.1)
    send_only(host, port,f3,bytes=True)
    send_only(host, port,b3,bytes=True)
    send_only(host, port,f3,bytes=True)

    # send_only(host, port,b4,bytes=True)
    # assert response == bytes(b'\xf9\x0bs\x01\x92\xf9')

    # raw = recieve_only_any(host,port,5)
    # frames = split_cmux_frames(raw)
    # parsed = [parse_cmux_frame(f) for f in frames]
    # print(f"Parsed frames: {parsed}")

    res = get_at_command(host,port,expected=b"AT+CFUN=1")
    assert res['payload'] == b'AT+CFUN=1'
    ok = build_uih_frame(dlci=res['dlci'], cr=res['cr'], pf=1, payload=b'OK\r')
    send_only(host, port,ok,bytes=True)


    res = get_at_command(host,port,expected=b"AT+CGACT=0,1")
    assert res['payload'] == b'AT+CGACT=0,1'
    ok = build_uih_frame(dlci=res['dlci'], cr=res['cr'], pf=1, payload=b'OK\r')
    send_only(host, port,ok,bytes=True)

    res = get_at_command(host,port,expected=b'AT+CGDCONT=1,"IP","internet"')
    assert res['payload'] == b'AT+CGDCONT=1,"IP","internet"'
    ok = build_uih_frame(dlci=res['dlci'], cr=res['cr'], pf=1, payload=b'OK\r')
    send_only(host, port,ok,bytes=True)

    res = get_at_command(host,port,expected=b'ATD*99***1#')
    assert res['payload'] == b'ATD*99***1#'
    ok = build_uih_frame(dlci=res['dlci'], cr=res['cr'], pf=1, payload=b'OK\r')
    send_only(host, port,ok,bytes=True)

    ok = build_uih_frame(dlci=2, cr=res['cr'], pf=1, payload=b'+CREG: 0,5\r\n')
    send_only(host, port,ok,bytes=True)
    ok = build_uih_frame(dlci=2, cr=res['cr'], pf=1, payload=b'+CGREG: 0,5\r\n')
    send_only(host, port,ok,bytes=True)

    print(" PPP !!! sequence")


    raw = recieve_only_any(host,port,5)
    frames = split_cmux_frames(raw)
    parsed = [parse_cmux_frame(f) for f in frames]
    print(f"Parsed frames 2: {parsed}")

    rss = b'\x7e\xff\x7d\x23\x80\x57\x7d\x21\x7d\x21\x7d\x20\x7d\x2e\x7d\x21\x7d\x2a\x41\xc7\x5c\x61\x7d\x35\x55\x45\x33\x5c\xc0\x7e'

    raw = b'\x7e\xff\x7d\x23\xc0\x21\x7d\x21\x7d\x21\x7d\x20\x7d\x39\x7d\x22\x7d\x26\x7d\x20\x7d\x20\x7d\x20\x7d\x20\x7d\x23\x7d\x25\xc2\x23\x7d\x25\x7d\x25\x7d\x26\x94\x83\xea\xce\x7d\0x27\x7d\x22\x7d\x28\x7d\x22\x6b\x7c\x7e'
    
    cmux_frame = build_uih_frame(dlci=1, cr=1, pf=1, payload=raw)
    send_only(host, port, cmux_frame, bytes=True)
    cmux_frame = build_uih_frame(dlci=1, cr=1, pf=1, payload=rss)
    send_only(host, port, cmux_frame, bytes=True)

    raw = recieve_only_any(host,port,10)
    frames = split_cmux_frames(raw)
    parsed = [parse_cmux_frame(f) for f in frames]
    print(f"Parsed frames 3: {parsed}")

    raw = recieve_only_any(host,port,5)
    frames = split_cmux_frames(raw)
    parsed = [parse_cmux_frame(f) for f in frames]
    print(f"Parsed frames 4: {parsed}")
    time.sleep(30)
