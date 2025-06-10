
import zmq
import time
import json

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.setsockopt(zmq.RCVBUF .RCVHWM, 1000)
# socket.setsockopt(zmq.RCVTIMEO, 500)
socket.setsockopt(zmq.LINGER, 0)
socket.setsockopt(zmq.RECONNECT_IVL, 500)
socket.connect("tcp://127.0.0.1:5401")
socket.setsockopt_string(zmq.SUBSCRIBE, "test")


try:
    while True:
        try:
            # 메시지 수신
            topic, message = socket.recv_multipart()
            print(topic, message)
        except zmq.error.ZMQError as e:
            pass
except KeyboardInterrupt:
    print("\n구독 종료")
finally:

    # 소켓 및 컨텍스트 종료
    socket.close()
    context.term()