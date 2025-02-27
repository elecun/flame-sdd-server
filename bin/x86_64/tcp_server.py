import socket
import struct

HOST = '127.0.0.1'  # 모든 인터페이스에서 수신
PORT = 7571       # 원하는 포트 번호

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        linger_struct = struct.pack('ii', 1, 0)  # l_onoff=1, l_linger=0
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger_struct)
        server_socket.bind((HOST, PORT))
        server_socket.listen()

        print(f"[*] Listening on {HOST}:{PORT}...")

        while True:
            client_socket, addr = server_socket.accept()
            print(f"[+] Connection from {addr}")

            with client_socket:
                while True:
                    data = client_socket.recv(1024)  # 최대 1024 바이트 수신
                    if not data:
                        print("[-] Connection closed")
                        break

                    # 문자열 또는 바이트로 출력
                    try:
                        message = data.decode('utf-8')  # 문자열로 변환
                        print(f"[Received String] {message}")
                    except UnicodeDecodeError:
                        print(f"[Received Bytes] {data}")  # 바이트 배열 출력

                    client_socket.sendall(b"ACK")  # 클라이언트에 응답

if __name__ == "__main__":
    start_server()