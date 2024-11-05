
import zmq
import time
import json

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://127.0.0.1:5009")

message = {
    "LOT":"L00000"
}

# request
request_string = json.dumps(message)
socket.send_string(request_string)
print(f"send message : {request_string}")

# response
response = socket.recv_string()
print(response)
#response_json = json.loads(response)
#print(f"response : {json.dumps(response_json, indent=4)}")
