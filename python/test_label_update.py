import json
import time
import zmq

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.setsockopt(zmq.RCVHWM, 1000)
socket.setsockopt(zmq.LINGER, 0)
socket.bind("tcp://*:5605")

try:
    time.sleep(1)
    topic = "labeling_job_dispatch"
    message = {
        "date": "20260106132044",
        "mea_image1": "20260106131810_H298x201_S78752002_1_25_WBR.jpg",
        "mea_image10": "",
        "mea_image11": "",
        "mea_image12": "",
        "mea_image13": "",
        "mea_image14": "",
        "mea_image15": "",
        "mea_image2": "",
        "mea_image3": "",
        "mea_image4": "",
        "mea_image5": "",
        "mea_image6": "",
        "mea_image7": "",
        "mea_image8": "",
        "mea_image9": "",
        "mt_no": "S78752002",
    }
    message_string = json.dumps(message)
    socket.send_multipart([topic.encode("utf-8"), message_string.encode("utf-8")])
    print("sent labeling_job_dispatch")
finally:
    socket.close()
    context.term()
