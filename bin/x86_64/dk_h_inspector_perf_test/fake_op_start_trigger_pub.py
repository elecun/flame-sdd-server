
import zmq
import time
import json

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://127.0.0.1:5008")

time.sleep(1)
topic = "manual_control"
message = {
    "op_trigger":False
}
message_string = json.dumps(message)
socket.send_multipart([topic.encode('utf-8'), message_string.encode('utf-8')])
