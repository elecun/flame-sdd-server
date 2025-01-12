import zmq
import numpy as np
import cv2  # OpenCV 사용 (이미지 데이터를 다룰 때 유용)
import time

# 서버 설정
def publisher():
    context = zmq.Context()
    socket = context.socket(zmq.PUB)

    # inproc 바인딩
    socket.bind("ipc:///tmp/image_stream_monitor")
    print("Publisher bound to ipc:///tmp/image_stream_monitor")

    # 예시 이미지 데이터 생성 (OpenCV를 사용해 NumPy 배열로 이미지 로드)
    image = cv2.imread('1920_1200_test_image.jpg')  # 이미지 경로를 넣으세요.
    _, buffer = cv2.imencode('.jpg', image)  # 이미지를 JPEG 형식으로 인코딩
    image_bytes = buffer.tobytes()  # 바이너리 데이터로 변환

    # 주기적으로 이미지 데이터를 Publish
    while True:
        # 토픽과 데이터 전송
        topic = "basler_gige_cam_grabber/image_stream_monitor_1"
        id = 1
        socket.send_multipart([topic.encode('utf-8'), str(id).encode('utf-8'), image_bytes])  # [토픽, 데이터]
        print(f"Published image on topic: {topic}")

        time.sleep(1)

if __name__ == "__main__":
    publisher()