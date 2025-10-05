import subprocess
import time
import pytest
import os
import signal
import platform
from pathlib import Path
import socket
import threading
import sys
import shutil
import contextlib


zephyr_base = Path(os.environ["ZEPHYR_BASE"]) if "ZEPHYR_BASE" in os.environ else Path.cwd()

def _stream_reader(stream, target, logfile=None):
    """Read bytes from stream and write decoded lines to target (stdout/stderr) and logfile."""
    try:
        while True:
            chunk = stream.readline()
            if not chunk:
                break
            # chunk is bytes; decode defensively
            try:
                text = chunk.decode(errors='replace')
            except Exception:
                text = str(chunk)
            target.write(text)
            target.flush()
            if logfile:
                logfile.write(text)
                logfile.flush()
    except Exception:
        pass


def wait_for_port(port, host="localhost", timeout=15.0):
    """Wait until a TCP port is open."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"Port {port} on {host} not available after {timeout}s")


def _find_qemu_system_arm() -> str:
    """Locate qemu-system-arm executable across typical Windows installs."""
    # Env override first
    override = os.environ.get("QEMU_SYSTEM_ARM")
    exe = "qemu-system-arm.exe" if platform.system() == "Windows" else "qemu-system-arm"
    if override:
        p = Path(override)
        # If override points to a directory, append the executable name
        if p.is_dir():
            cand = p / exe
            if cand.exists():
                return str(cand)
        # If override points directly to the executable, return it
        if p.exists():
            return str(p)
    # 1) PATH
    p = shutil.which(exe) or shutil.which("qemu-system-arm")
    if p:
        return p
    # 2) Zephyr SDK
    sdk = os.environ.get("ZEPHYR_SDK_INSTALL_DIR")
    if sdk:
        cand = Path(sdk) / "qemu" / "bin" / exe
        if cand.exists():
            return str(cand)
    # 3) NCS toolchain typical path
    candidates = []
    ncs_root = Path("C:/ncs")
    if ncs_root.exists():
        for toolchains in ncs_root.glob("toolchains/*"):
            candidates.append(toolchains / "opt" / "zephyr-sdk" / "qemu" / "bin" / exe)
            for sdkdir in toolchains.glob("opt/zephyr-sdk-*"):
                candidates.append(sdkdir / "qemu" / "bin" / exe)
    # 4) Program Files common qemu install
    candidates.append(Path("C:/Program Files/qemu") / exe)
    candidates.append(Path("C:/Program Files (x86)/qemu") / exe)
    for c in candidates:
        if c.exists():
            return str(c)
    # 5) Fallback to name (will error later)
    return exe


@pytest.fixture(scope="module")
def qemu(elf_path):
    """Start QEMU for Zephyr ELF and tear it down after tests."""
    elf_path = Path(elf_path)
    if not elf_path.exists():
        pytest.fail(f"ELF not found: {elf_path}. Build it first, e.g.: west build -b qemu_cortex_m3 samples/modem_test -d samples/modem_test/build")

    qemu_exe = _find_qemu_system_arm()

    qemu_cmd = [
        qemu_exe,
        "-M", "lm3s6965evb",
        "-cpu", "cortex-m3",
        "-kernel", str(elf_path),
        "-serial", "mon:stdio",
        "-serial", "tcp::1234,server,nowait",
        "-serial", "tcp::1235,server,nowait,nodelay",
        "-display", "none",
        "-nic", "none" # Disable all network interfaces
        # "-netdev", "user,id=net0",
        # "-device", "stellaris-enet,netdev=net0"
    ]
    logfile = None
    logfile_path = Path("qemu_logs.txt")
    try:
        logfile = open(logfile_path, "a", buffering=1, encoding="utf-8", errors="replace")
    except Exception:
        logfile = None
    print(f"Starting QEMU with: {elf_path}\nUsing QEMU: {qemu_exe}")

    popen_kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE
    }

    # Set Windows-specific flag if running on Windows
    if platform.system() == "Windows":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    try:
        proc = subprocess.Popen(qemu_cmd, **popen_kwargs)
    except FileNotFoundError as e:
        pytest.fail(f"Failed to launch QEMU: {e}. Ensure QEMU is installed and in PATH or set ZEPHYR_SDK_INSTALL_DIR.")

    stdout_t = threading.Thread(target=_stream_reader, args=(proc.stdout, sys.stdout, logfile), daemon=True)
    stderr_t = threading.Thread(target=_stream_reader, args=(proc.stderr, sys.stderr, logfile), daemon=True)
    stdout_t.start()
    stderr_t.start()

    wait_for_port(1234)
    wait_for_port(1235)

    time.sleep(1.0)  # give QEMU time to boot

    try:
        yield proc  # test runs here
    finally:
        # Teardown: kill QEMU
        if platform.system() == "Windows":
            with contextlib.suppress(Exception):
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            with contextlib.suppress(Exception):
                proc.terminate()
        else:
            with contextlib.suppress(Exception):
                proc.send_signal(signal.SIGTERM)
            with contextlib.suppress(Exception):
                proc.terminate()


@pytest.fixture(scope="module")
def uart_sock(qemu):
    """Persistent TCP connection to the modem UART (QEMU serial on 1235)."""
    s = socket.create_connection(("localhost", 1235), timeout=10)
    try:
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except Exception:
        pass
    s.settimeout(2.0)
    try:
        yield s
    finally:
        with contextlib.suppress(Exception):
            s.close()