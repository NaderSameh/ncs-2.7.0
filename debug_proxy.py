import socket
import threading
import sys
import time

def hexdump(data):
    return ' '.join(f'{b:02x}' for b in data)

def forward(src, dst, direction):
    try:
        while True:
            data = src.recv(4096)
            if not data:
                print(f"{direction}: Connection closed")
                break
            print(f"{direction}: Forwarding {len(data)} bytes: {hexdump(data)}")
            dst.send(data)
    except Exception as e:
        print(f"{direction}: Error: {e}")
    finally:
        try:
            src.close()
            dst.close()
        except:
            pass

def proxy(local_port, remote_host, remote_port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', local_port))  # Listen on all interfaces
    server.listen(1)
    
    print(f"Debug proxy listening on 0.0.0.0:{local_port}")
    print(f"Forwarding to {remote_host}:{remote_port}")
    
    while True:
        try:
            local_conn, local_addr = server.accept()
            print(f"New connection from {local_addr}")
            
            # Set longer timeout for debugging
            local_conn.settimeout(30)
            
            remote_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote_conn.settimeout(30)  # Same timeout for remote
            print(f"Attempting to connect to {remote_host}:{remote_port}...")
            remote_conn.connect((remote_host, remote_port))
            print(f"Connected to remote {remote_host}:{remote_port}")
            
            threading.Thread(target=forward, args=(local_conn, remote_conn, "→"), daemon=True).start()
            threading.Thread(target=forward, args=(remote_conn, local_conn, "←"), daemon=True).start()
            
        except Exception as e:
            print(f"Error handling connection: {e}")
            time.sleep(1)  # Prevent tight loop on repeated errors

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} local_port remote_host remote_port")
        sys.exit(1)
    
    local_port = int(sys.argv[1])
    remote_host = sys.argv[2]
    remote_port = int(sys.argv[3])
    
    proxy(local_port, remote_host, remote_port)