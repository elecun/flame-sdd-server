
import zmq
import time
import json

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect("tcp://127.0.0.1:5556")
socket.setsockopt_string(zmq.SUBSCRIBE, "basler_gige_cam_grabber/status")

try:
    while True:
        # 메시지 수신
        message = socket.recv_string()
        print(f"받은 메시지: {message}")
except KeyboardInterrupt:
    print("\n구독 종료")

# 소켓 및 컨텍스트 종료
socket.close()
context.term()