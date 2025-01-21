
import zmq
import time
import json

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.connect("tcp://192.168.0.90:5104")
socket.setsockopt_string(zmq.PUBLISH, "focus_control")


topic = "topic1"  # 구독 주제
message = "Hello, C++ subscriber!"
multipart_data = [topic.encode(), message.encode()]

socket.send_multipart(multipart_data)  # 멀티파트 데이터 전송
print(f"Published: {topic} {message}")
    
    time.sleep(1)

# 소켓 및 컨텍스트 종료
socket.close()
context.term()