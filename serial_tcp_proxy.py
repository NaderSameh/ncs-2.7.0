import socket
import threading
import sys
import time
import select

def log_data(direction, data):
    print(f"{direction}: {len(data)} bytes: {data.hex()[:60]}...")

def forward_serial_to_tcp(sock, data):
    try:
        sock.send(data)
        log_data("Serial->TCP", data)
    except Exception as e:
        print(f"Error forwarding to TCP: {e}")

def forward_tcp_to_serial(tcp_data, serial_sock):
    try:
        serial_sock.send(tcp_data)
        log_data("TCP->Serial", tcp_data)
    except Exception as e:
        print(f"Error forwarding to serial: {e}")

def handle_tcp_connection(local_sock, remote_host, remote_port, serial_sock):
    print(f"New TCP connection, connecting to {remote_host}:{remote_port}")
    try:
        remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_sock.connect((remote_host, remote_port))
        print("Connected to remote broker")
        
        while True:
            # Wait for data from either socket
            readable, _, _ = select.select([local_sock, remote_sock, serial_sock], [], [], 1.0)
            
            for sock in readable:
                if sock == local_sock:
                    # Data from local TCP (QEMU) to remote TCP (broker)
                    data = sock.recv(4096)
                    if not data:
                        print("Local connection closed")
                        return
                    forward_serial_to_tcp(remote_sock, data)
                
                elif sock == remote_sock:
                    # Data from remote TCP (broker) to local TCP (QEMU)
                    data = sock.recv(4096)
                    if not data:
                        print("Remote connection closed")
                        return
                    forward_tcp_to_serial(data, local_sock)
                
                elif sock == serial_sock:
                    # Data from serial port, forward to remote TCP
                    data = sock.recv(4096)
                    if not data:
                        print("Serial connection closed")
                        continue
                    forward_serial_to_tcp(remote_sock, data)
    
    except Exception as e:
        print(f"Connection handler error: {e}")
    finally:
        try:
            remote_sock.close()
            local_sock.close()
        except:
            pass

def main(serial_port, remote_host, remote_port):
    # Connect to the TCP serial port first
    serial_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serial_sock.connect(('localhost', serial_port))
    print(f"Connected to serial port on localhost:{serial_port}")
    
    # Create TCP listening socket for MQTT
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', 1884))
    server.listen(1)
    print("MQTT Proxy listening on 127.0.0.1:1884")
    
    while True:
        try:
            print("Waiting for MQTT connection...")
            local_conn, addr = server.accept()
            print(f"Accepted connection from {addr}")
            
            # Handle this connection in a new thread
            threading.Thread(
                target=handle_tcp_connection,
                args=(local_conn, remote_host, remote_port, serial_sock)
            ).start()
            
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(1)

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} serial_port remote_host remote_port")
        print("Example: python proxy.py 5678 104.218.120.246 1884")
        sys.exit(1)
        
    serial_port = int(sys.argv[1])
    remote_host = sys.argv[2]
    remote_port = int(sys.argv[3])
    
    main(serial_port, remote_host, remote_port)