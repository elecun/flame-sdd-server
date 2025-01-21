
import zmq
import time
import json

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://*:5104")
# socket.setsockopt_string(zmq.PUBLISH, "focus_control")

time.sleep(3)

topic = "focus_control"  # 구독 주제
msg = {
    "function":"move_focus",
    "id":1,
    "value":1000
}
j_string = json.dumps(msg)

multipart_data = [topic.encode('utf-8'), j_string.encode('utf-8')]

socket.send_multipart(multipart_data)  # 멀티파트 데이터 전송
print(f"Published")
    


# 소켓 및 컨텍스트 종료
socket.close()
context.term()