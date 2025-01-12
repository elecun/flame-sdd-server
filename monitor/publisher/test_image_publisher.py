import zmq
import cv2
import numpy as np

def main():
    # ZeroMQ context와 PUB 소켓 생성
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:5555")  # 포트 바인딩

    # 주기적으로 이미지를 읽어 전송
    while True:
        # 이미지 읽기 (여기서 이미지 경로를 지정)
        img = cv2.imread("example.jpg")
        if img is None:
            print("이미지를 읽을 수 없습니다.")
            break

        # 이미지를 직렬화 (jpg로 인코딩 후 전송)
        _, buffer = cv2.imencode(".jpg", img)
        socket.send_multipart([b"send_image", buffer.tobytes()])

if __name__ == "__main__":
    main()