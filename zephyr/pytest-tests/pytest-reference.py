import socket
import time
import pynmea2
import json
import pytest
from conftest import zephyr_base

@pytest.fixture(scope="module")
def elf_path():
    return zephyr_base / "samples/hello_world/build/zephyr/zephyr.elf"  # adjust as needed

def send_on_one_port_receive_on_another(
    host, send_port, recv_port, message, timeout=2.0
):
    """Send a message to one TCP port and receive the response from another."""

    # with socket.create_connection((host, send_port), timeout=timeout) as sock:
    sock = socket.create_connection((host, send_port), timeout=timeout)
    sock.settimeout(timeout)
    sock.sendall(message.encode())
    print("HEREEEE")
    # 1. Connect to receive port first (some systems block if listener isn't ready)
    recv_sock = socket.create_connection((host, recv_port), timeout=timeout)
    recv_sock.settimeout(timeout)

    # 3. Give some time for QEMU to process and reply
    time.sleep(0.1)

    try:
        response = recv_sock.recv(1024).decode()
    except socket.timeout:
        print("Timeout while waiting for response")
        response = ""
    finally:
        recv_sock.close()
        # send_sock.close()

    return response.strip()


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

def send_only(host, port, message, timeout=1.0):
    """Connect to UART over TCP, send a message"""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(message.encode())
        return b''


def test_uart_echo(qemu):
    # host = "localhost"
    # port = 1234
    # message = "echo test\r\n"
    # expected_response = "OK"  # Assuming Zephyr echoes line back as-is
    # response = send_and_receive(host, port, message)
    # assert expected_response in response, f"Expected '{expected_response}', got '{response}'"

    host = "localhost"
    port = 1234
    message = "$GNRMC,125109.816,A,3007.3177,S,03121.9516,E,0.99,13.52,060725,,,A*61\r\n"
    # message = "$GPGGA, 125118.000 3007.3167 N 03121.9537 E 1 7 1.24 279.2 M 16.8 M   5D\r\n"
    expected_response = "OK"  # Assuming Zephyr echoes line back as-is
    res = send_only(host, port, message)
    assert res == b'', f"Expected no response, got '{res}'"
    message = "$GPGGA,125109.816,3007.3177,S,03121.9516,E,1,07,1.24,275.6,M,16.8,M,,*75\r\n"
    response = send_on_one_port_receive_on_another(host, 1234,1235, message)

    print(response)
    data = json.loads(response)
    print(data)
    msg = pynmea2.parse(message)
    assert float(msg.latitude) == pytest.approx(data["lat"], rel=1e-6)
    assert float(msg.longitude) == pytest.approx(data["lng"])
    assert int(msg.num_sats) == data["no_sat"]
    assert float(msg.altitude) == pytest.approx(data["alt"], rel=1e-6)
    
    # assert expected_response in response, f"Expected '{expected_response}', got '{response}'"
