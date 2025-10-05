# cmux_frames.py
import socket
import struct
from typing import List


# UIH frame control byte mask
CONTROL_UIH = 0xEF

# Reversed CRC table from ETSI TS 101 369 (poly=0x07, reversed table)
CRCTABLE = [
0x00,0x91,0xE3,0x72,0x07,0x96,0xE4,0x75,0x0E,0x9F,0xED,0x7C,0x09,0x98,0xEA,0x7B,
0x1C,0x8D,0xFF,0x6E,0x1B,0x8A,0xF8,0x69,0x12,0x83,0xF1,0x60,0x15,0x84,0xF6,0x67,
0x38,0xA9,0xDB,0x4A,0x3F,0xAE,0xDC,0x4D,0x36,0xA7,0xD5,0x44,0x31,0xA0,0xD2,0x43,
0x24,0xB5,0xC7,0x56,0x23,0xB2,0xC0,0x51,0x2A,0xBB,0xC9,0x58,0x2D,0xBC,0xCE,0x5F,
0x70,0xE1,0x93,0x02,0x77,0xE6,0x94,0x05,0x7E,0xEF,0x9D,0x0C,0x79,0xE8,0x9A,0x0B,
0x6C,0xFD,0x8F,0x1E,0x6B,0xFA,0x88,0x19,0x62,0xF3,0x81,0x10,0x65,0xF4,0x86,0x17,
0x48,0xD9,0xAB,0x3A,0x4F,0xDE,0xAC,0x3D,0x46,0xD7,0xA5,0x34,0x41,0xD0,0xA2,0x33,
0x54,0xC5,0xB7,0x26,0x53,0xC2,0xB0,0x21,0x5A,0xCB,0xB9,0x28,0x5D,0xCC,0xBE,0x2F,
0xE0,0x71,0x03,0x92,0xE7,0x76,0x04,0x95,0xEE,0x7F,0x0D,0x9C,0xE9,0x78,0x0A,0x9B,
0xFC,0x6D,0x1F,0x8E,0xFB,0x6A,0x18,0x89,0xF2,0x63,0x11,0x80,0xF5,0x64,0x16,0x87,
0xD8,0x49,0x3B,0xAA,0xDF,0x4E,0x3C,0xAD,0xD6,0x47,0x35,0xA4,0xD1,0x40,0x32,0xA3,
0xC4,0x55,0x27,0xB6,0xC3,0x52,0x20,0xB1,0xCA,0x5B,0x29,0xB8,0xCD,0x5C,0x2E,0xBF,
0x90,0x01,0x73,0xE2,0x97,0x06,0x74,0xE5,0x9E,0x0F,0x7D,0xEC,0x99,0x08,0x7A,0xEB,
0x8C,0x1D,0x6F,0xFE,0x8B,0x1A,0x68,0xF9,0x82,0x13,0x61,0xF0,0x85,0x14,0x66,0xF7,
0xA8,0x39,0x4B,0xDA,0xAF,0x3E,0x4C,0xDD,0xA6,0x37,0x45,0xD4,0xA1,0x30,0x42,0xD3,
0xB4,0x25,0x57,0xC6,0xB3,0x22,0x50,0xC1,0xBA,0x2B,0x59,0xC8,0xBD,0x2C,0x5E,0xCF
]

FLAG = 0xF9   # BOFC/EOFC on-wire byte used by many stacks (ETSI examples)
# control base values:
CTRL_SABM = 0x2F
CTRL_UA   = 0x63
CTRL_DM   = 0x0F  # not used here, shown for reference
CTRL_UIH  = 0xEF
# note: PF bit is bit 4 (0x10). control = base | (pf<<4)

def compute_fcs(byte_seq):
    """Compute GSM07.10 FCS using ETSI reversed lookup table."""
    f = 0xFF
    for b in byte_seq:
        f = CRCTABLE[f ^ (b & 0xFF)]
    return (0xFF - f) & 0xFF

def addr_byte(dlci, cr):
    return (((dlci & 0x3F) << 2) | ((cr & 1) << 1) | 1) & 0xFF

def control_byte(base, pf):
    return (base | ((pf & 1) << 4)) & 0xFF

def length_octet(length):
    # single octet length (EA=1)
    if length < 0 or length > 127:
        raise ValueError("length must be 0..127 for single-octet encoding")
    return ((length & 0x7F) << 1) | 1

def build_frame(dlci, cr, control_base, pf, info=b'', include_info_in_fcs=True):
    """Return a full on-wire frame (with flags and FCS).
       include_info_in_fcs: for UIH frames you should pass False (info excluded).
    """
    A = addr_byte(dlci, cr)
    C = control_byte(control_base, pf)
    L = length_octet(len(info))
    # FCS is computed over A,C,L and optionally info (UI frames include info; UIH excludes it)
    fcs_input = bytes([A, C, L])
    if include_info_in_fcs:
        fcs_input += bytes(info)
    fcs = compute_fcs(fcs_input)
    frame = bytes([FLAG]) + bytes([A, C, L]) + bytes(info) + bytes([fcs, FLAG])
    return frame

# convenience helpers
def build_sabm(dlci=0, cr=1, pf=1):
    return build_frame(dlci, cr, CTRL_SABM, pf, b'', include_info_in_fcs=True)

def build_ua(dlci=0, cr=1, pf=1):
    return build_frame(dlci, cr, CTRL_UA, pf, b'', include_info_in_fcs=True)

def build_uih(dlci, cr, pf, info_bytes):
    # UIH frames: FCS excludes info field (per ETSI)
    return build_frame(dlci, cr, CTRL_UIH, pf, info=bytes(info_bytes), include_info_in_fcs=False)

# Example: build the "disconnect" sample from kernel docs:
# bytes: f9 03 ef 03 c3 16 f9   (addr=0x03, ctrl=0xef, len=0x03, info=0xc3, fcs=0x16)
def example_disconnect_frame():
    return build_uih(dlci=0, cr=1, pf=0, info_bytes=b'\xC3')  # this should equal the kernel example

# Small helper to send a frame over TCP (host:port)
def send_frame_tcp(host, port, frame):
    with socket.create_connection((host, port), timeout=2.0) as s:
        s.sendall(frame)



def _bit_reverse8(x: int) -> int:
    return int(f"{x:08b}"[::-1], 2)

def _crc8_itu_reflected(data: bytes) -> int:
    # CRC-8/ITU: poly=0x07, refin=True, refout=True, init=0xFF, xorout=0xFF
    poly = 0x07
    crc = 0xFF
    for b in data:
        b = _bit_reverse8(b)  # reflect input
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) & 0xFF) ^ (poly if (crc & 0x80) else 0x00)
    crc = _bit_reverse8(crc) ^ 0xFF  # reflect output, xorout
    return crc

def split_cmux_frames(stream: bytes) -> List[bytes]:
    """Return a list of raw frames found between FLAG (0xF9) delimiters."""
    frames, i = [], 0
    while True:
        try:
            start = stream.index(bytes([FLAG]), i)
            end   = stream.index(bytes([FLAG]), start + 1)
        except ValueError:
            break
        frames.append(stream[start:end+1])
        i = end + 1
    return frames

def parse_cmux_frame(frame: bytes) -> dict:
    """Parse one CMUX frame and return fields; raises on format errors."""
    if len(frame) < 6 or frame[0] != FLAG or frame[-1] != FLAG:
        raise ValueError("Bad CMUX frame format")

    addr  = frame[1]
    ctrl  = frame[2]
    L1    = frame[3]  # single-length byte (EA=1 expected here)

    if (L1 & 0x01) == 0:
        raise ValueError("Extended length not supported in this helper")

    plen = L1 >> 1
    if len(frame) != 4 + plen + 1 + 1:  # hdr + payload + fcs + flag
        raise ValueError("Length mismatch")

    payload = frame[4:4+plen]
    fcs     = frame[4+plen]

    # For UIH, FCS is over address+control+length only
    if _crc8_itu_reflected(bytes([addr, ctrl, L1])) != fcs:
        raise ValueError("FCS check failed")

    ea  = addr & 0x01
    cr  = (addr >> 1) & 0x01
    dlci= (addr >> 2) & 0x3F

    return {
        "dlci": dlci,
        "cr": cr,
        "ctrl": ctrl,    # 0xEF for UIH (PF=0), 0xFF if PF=1
        "len": plen,
        "payload": payload,
        "fcs_ok": True,
        "ea": ea,
    }

def build_uih_frame(dlci: int, payload: bytes, *, cr: int = 0, pf: int = 0) -> bytes:
    """Build a UIH CMUX frame on DLCI with proper FCS."""
    addr = (dlci << 2) | ((cr & 1) << 1) | 1
    ctrl = 0xEF | ((pf & 1) << 4)   # UIH; PF bit if you really want it set
    L1   = (len(payload) << 1) | 1  # EA=1

    fcs = _crc8_itu_reflected(bytes([addr, ctrl, L1]))
    return bytes([FLAG, addr, ctrl, L1]) + payload + bytes([fcs, FLAG])
