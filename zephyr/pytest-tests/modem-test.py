import socket
import time
import pytest
from conftest import zephyr_base

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
    send_only(host, port, "+CREG: 0,5\r\n")
    send_only(host, port, "OK\r\n")
    # assert response == "AT+CEREG?", f"Expected 'AT+CEREG?', got '{response}'"
    time.sleep(0.1)
    send_only(host, port, "+CEREG: 0,5\r\n")
    send_only(host, port, "OK\r\n")
    # assert response == "AT+CGREG?", f"Expected 'AT+CGREG?', got '{response}'"
    time.sleep(0.1)
    send_only(host, port, "+CGREG: 0,5\r\n")
    send_only(host, port, "OK\r\n")
    if response == "AT+CREG?":
        response = recieve_only(host,port,5)
    assert response == "AT+CMUX=0,0,5,127,10,3,30,10,2", f"Expected 'AT+CMUX=0,0,5,127,10,3,30,10,2', got '{response}'"
    time.sleep(0.1)
    # send_only(host, port, "OK\r\n")
    response = recieve_only_any(host,port,30)
    assert bytes(response) == bytes(b'\xf9\x03?\x01\x1c\xf9')
    # send_only(host, port, b'\xF9\x01\x73\x01\xCE\xF9',bytes=True)
    response = recieve_only_any(host,port,30)
    assert bytes(response) == bytes(b'\xf9\x03?\x01\x1c\xf9')
    # print(f"Response: {response}")
    send_only(host, port, "OK\r\n")
    time.sleep(30)
    # assert expected_response in response, f"Expected '{expected_response}', got '{response}'"
