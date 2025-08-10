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


zephyr_base = Path(os.environ["ZEPHYR_BASE"])

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


def wait_for_port(port, host="localhost", timeout=5.0):
    """Wait until a TCP port is open."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"Port {port} on {host} not available after {timeout}s")


@pytest.fixture(scope="module")
def qemu(elf_path):
    """Start QEMU for Zephyr ELF and tear it down after tests."""
    qemu_cmd = [
        "qemu-system-arm",
        "-M", "lm3s6965evb",
        "-cpu", "cortex-m3",
        "-kernel", str(elf_path),
        "-serial", "mon:stdio",
        "-serial", "tcp::1234,server,nowait",
        "-serial", "tcp::1235,server,nowait,nodelay",
        "-display", "none"
    ]
    logfile = None
    logfile_path = Path("qemu_logs.txt")
    try:
        logfile = open(logfile_path, "a", buffering=1, encoding="utf-8", errors="replace")
    except Exception:
        logfile = None
    print(f"Starting QEMU with: {elf_path}")

    popen_kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE
    }

    # Set Windows-specific flag if running on Windows
    if platform.system() == "Windows":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    proc = subprocess.Popen(qemu_cmd, **popen_kwargs)

    stdout_t = threading.Thread(target=_stream_reader, args=(proc.stdout, sys.stdout, logfile), daemon=True)
    stderr_t = threading.Thread(target=_stream_reader, args=(proc.stderr, sys.stderr, logfile), daemon=True)
    stdout_t.start()
    stderr_t.start()

    wait_for_port(1234)
    wait_for_port(1235)

    time.sleep(1.0)  # give QEMU time to boot

    yield proc  # test runs here

    # Teardown: kill QEMU
    if platform.system() == "Windows":
        proc.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        proc.send_signal(signal.SIGTERM)

        stdout_t = threading.Thread(target=_stream_reader, args=(proc.stdout, sys.stdout, logfile), daemon=True)
    stderr_t = threading.Thread(target=_stream_reader, args=(proc.stderr, sys.stderr, logfile), daemon=True)
    stdout_t.start()
    stderr_t.start()