
import zmq
import time
import json

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://127.0.0.1:5604")

time.sleep(5)

topic = "dk_level2_interface/lv2_dispatch"  # 구독 주제
msg = {
    "lot_no":"test_lot_no",
    "mt_stand_height":300,
    "mt_stand_width":300,
    "mt_stand_t1":9,
    "mt_stand_t2":12,
    "mt_stand":"H 300x300x9/12",
    "fm_length":"100"
}
j_string = json.dumps(msg)

multipart_data = [topic.encode('utf-8'), j_string.encode('utf-8')]

socket.send_multipart(multipart_data)  # 멀티파트 데이터 전송
print(f"Published")
    


# 소켓 및 컨텍스트 종료
socket.close()
context.term()