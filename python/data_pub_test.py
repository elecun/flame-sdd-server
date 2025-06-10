
import zmq
import time
import json

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.setsockopt(zmq.RCVBUF .RCVHWM, 1000)
socket.setsockopt(zmq.LINGER, 0)
socket.bind("tcp://*:5401")

time.sleep(10)

topic = "ni_daq_controller/line_signal"  # 구독 주제
msg = {
    "date":"20250401182801",
    "mt_stand_height":350,
    "mt_stand_width":350,
    "sdd_in_path":"/home/dev/local_storage/20250401/20250401182801_350x350",
    "sdd_out_path":"/home/dev/nas_storage/20250401/20250401182801_350x350"
}
j_string = json.dumps(msg)
multipart_data = [topic.encode(), j_string.encode()]
socket.send_multipart(multipart_data)  # 멀티파트 데이터 전송
print("try 1")

    


# 소켓 및 컨텍스트 종료
socket.close()
context.term()