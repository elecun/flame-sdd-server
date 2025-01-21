
import zmq
import time
import json

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.setsockopt_string(zmq.SUBSCRIBE, "focus_control")
socket.connect("tcp://192.168.0.90:5104")

try:
    while True:
        time.sleep(3)
        # 메시지 수신
        topic, message = socket.recv_multipart()
        print(topic, message)

        
except KeyboardInterrupt:
    print("\n구독 종료")

# 소켓 및 컨텍스트 종료
socket.close()
context.term()