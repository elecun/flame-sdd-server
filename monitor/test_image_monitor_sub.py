
import zmq
import time
import json

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.setsockopt_string(zmq.SUBSCRIBE, "camera_1")
socket.connect("tcp://127.0.0.1:5102")

count = 0
try:
    while True:
        # 메시지 수신
        topic, id, image_data = socket.recv_multipart()
        print(f"recv({count}) camera id : {id.decode()}")
        count = count +1
        
except KeyboardInterrupt:
    print("exit")
finally:
    socket.close()
    context.term()