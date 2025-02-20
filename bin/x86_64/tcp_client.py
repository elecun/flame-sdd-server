import socket
import time
# 서버 주소 및 포트 설정
SERVER_IP = "127.0.0.1"  # 로컬 테스트를 위해 localhost 사용
SERVER_PORT = 5402       # 서버의 포트 번호

# 소켓 생성
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    # 서버에 연결
    client_socket.connect((SERVER_IP, SERVER_PORT))
    print(f"서버 {SERVER_IP}:{SERVER_PORT} 에 연결됨")

    message = "10992025022010323800005012300000000000000000000000"
    client_socket.sendall(message.encode())  # 문자열을 바이트로 변환하여 송신
    time.sleep(1)

    message = "100120250220103238000512S269440003     S26945501      BL250 99999999999SHH 250 x 150 x 9/14            SS400           EN S235JR                     999999999999999999999999.90H1200110099999999999999999999999999990                                                                                                                                                                                                                                                                                                          "
    client_socket.sendall(message.encode())  # 문자열을 바이트로 변환하여 송신

    # 서버로부터 응답 수신
    response = client_socket.recv(1024)  # 최대 1024바이트 수신
    print(f"서버 응답: {response.decode()}")

except Exception as e:
    print(f"오류 발생: {e}")

finally:
    # 소켓 종료
    client_socket.close()
    print("연결 종료")