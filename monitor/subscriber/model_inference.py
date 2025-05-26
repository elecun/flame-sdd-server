"""
Surface Defect Model Inference Subscru
@author Byunghun Hwang <bh.hwang@iae.re.kr>
"""

try:
    # using PyQt5
    from PyQt5.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
except ImportError:
    # using PyQt6
    from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal

import zmq
import zmq.utils.monitor as zmq_monitor
from util.logger.console import ConsoleLogger
import json
import threading
import time
from typing import Any, Dict
import torch
import onnxruntime as ort #cpu verson
import numpy as np
import os
from PIL import Image
import queue
import pathlib

from torchvision import transforms
from tqdm import tqdm
import onnxruntime as ort
import csv
import glob
import numpy as np
import torch
import cv2
import os
import shutil


class SDDModelInference(QThread):
    processing_result_signal = pyqtSignal(dict) #
    update_status_signal = pyqtSignal(dict) # signal for connection status message
    '''
    models = [{cam_ids":[1,2], "model_path:"/path/mode.onnx"}, ...}]
    '''

    def __init__(self, context:zmq.Context, connection:str, topic:str, model_config:dict, in_path_root:str, out_path_root:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"SDD Model Inference Connection : {connection} (topic:{topic})")

        # save paramters
        self.__model_config = model_config
        self.__images_root_path = pathlib.Path(in_path_root)
        self.__out_root_path = pathlib.Path(out_path_root)
        self.__job_queue = queue.Queue()

        # store parameters
        self.__connection = connection
        self.__topic = topic

        # initialize zmq
        self.__socket = context.socket(zmq.SUB)
        self.__socket.setsockopt(zmq.RCVBUF .RCVHWM, 1000)
        self.__socket.setsockopt(zmq.RCVTIMEO, 500)
        self.__socket.setsockopt(zmq.LINGER,0)
        self.__socket.connect(connection)
        self.__socket.subscribe(topic)

        self.__poller = zmq.Poller()
        self.__poller.register(self.__socket, zmq.POLLIN) # POLLIN, POLLOUT, POLLERR

        self.__inference_stop_event = threading.Event()
        self.__inference_job_worker = threading.Thread(target=self.__inference, daemon=True)
        self.__inference_job_worker.start()


        self.start()
        self.__console.info("* Start SDD Model Inference")

    
    def __delete_directory_background(self, path: str):
        def worker():
            if os.path.exists(path) and os.path.isdir(path):
                shutil.rmtree(path)
                self.__console.info(f"Deleted {path}")
            else:
                self.__console.error(f"{path} does not exist or is not a directory")

        thread = threading.Thread(target=worker)
        thread.start()

    def get_connection_info(self) -> str: # return connection address
        return self.__connection
    
    def get_topic(self) -> str: # return subscriber topic
        return self.__topic
    
    def run(self):
        """ Run the subscriber thread """
        while not self.isInterruptionRequested():
            try:
                events = dict(self.__poller.poll(1000)) # wait 1 sec
                if self.__socket in events:
                    if events[self.__socket] == zmq.POLLERR:
                        self.__console.error(f"<SDD Model Inference> Error: {self.__socket.getsockopt(zmq.LAST_ENDPOINT)}")

                    elif events[self.__socket] == zmq.POLLIN:
                        topic, data = self.__socket.recv_multipart()
                        if topic.decode() == self.__topic:
                            data = json.loads(data.decode('utf8').replace("'", '"'))

                            if "date" in data and "mt_stand_height" in data and "mt_stand_width" in data:
                                lv2_date = data["date"][0:8]  # YYYYMMDD
                                lv2_mt_h = data["mt_stand_height"]
                                lv2_mt_w = data["mt_stand_width"]
                                target_dir = pathlib.Path(lv2_date) / f"{data['date']}_{lv2_mt_h}x{lv2_mt_w}"
                                data["sdd_in_path"] = self.__images_root_path / target_dir
                                data["sdd_out_path"] = self.__out_root_path / target_dir
                                self.__job_queue.put(data)

                                self.__console.info(f"<SDD Model Inference> Adding job to queue... (Remaining {self.__job_queue.qsize()})")

            
            except json.JSONDecodeError as e:
                self.__console.critical(f"<SDD Model Inference>[DecodeError] {e}")
                continue
            except zmq.error.ZMQError as e:
                self.__console.critical(f"<SDD Model Inference>[ZMQError] {e}")
                break
            except Exception as e:
                self.__console.critical(f"<SDD Model Inference>[Exception] {e}")
                break

    def __inference(self):
        while not self.__inference_stop_event.is_set():
            time.sleep(0.5)

            # checl if there is a job in the queue
            if not self.__job_queue.empty():
                job_description = self.__job_queue.get()
                self.__console.debug(f"<SDD Model Inference> Do Inference... (Remaining {self.__job_queue.qsize()})")

                # update status signal
                self.update_status_signal.emit({"working":True})
                model_root = self.__model_config.get("model_root", "/home/dk-sdd/dev/flame-sdd-server/bin/model")
                if "sdd_in_path" in job_description and "sdd_out_path" in job_description:
                    self.__inference_all(model_root, job_description["sdd_in_path"], job_description["sdd_out_path"])

                self.update_status_signal.emit({"working":False})
                self.processing_result_signal.emit({"done":True})
                self.__delete_directory_background(job_description["sdd_in_path"])
                
    def __inference_all(self, model_root, in_path:str, out_path:str):
        # 카메라 ID 그룹별로 사용하는 ONNX 모델 경로 정의
        camera_to_model = {
            (1, 5, 6, 10): f"{model_root}/vae_group_1_10_5_6.onnx",
            (2, 4, 7, 9): f"{model_root}/vae_group_2_9_4_7.onnx",
            (3, 8): f"{model_root}/vae_group_3_8.onnx"
        }

        # PIL 이미지를 텐서로 변환 (크기 고정)
        transform = transforms.Compose([
            transforms.Resize((300, 480)),
            transforms.ToTensor()
        ])

        # 결과 CSV 저장용 배열
        result_rows = [['filename', 'MAE', 'SSIM', 'Grad_MAE', 'Laplacian_Diff', 'Pixel_Sum', 'result']]
        model_cache = {}  # ONNX 세션 캐싱

        # 이미지 파일 전체 수집 (camera_* 폴더 기준)
        all_image_info = []
        for cam_folder in glob.glob(os.path.join(in_path, 'camera_*')):
            cam_id = int(cam_folder.split('_')[-1])
            for ext in ('*.jpg', '*.jpeg', '*.JPG', '*.JPEG'):
                for img_path in glob.glob(os.path.join(cam_folder, ext)):
                    all_image_info.append((cam_id, img_path))

        SAVE_IMAGE = False  # ← 결과 이미지 저장 여부 토글 (True 시 저장됨)

        for cam_id, img_path in tqdm(all_image_info, desc="Inference Progress", unit="img"):
            # break processing
            if self.__inference_stop_event.is_set():
                break


            # 해당 카메라에 대응되는 ONNX 모델 찾기
            model_path = None
            for cams, path in camera_to_model.items():
                if cam_id in cams:
                    model_path = path
                    break
            if model_path is None or not os.path.exists(model_path):
                continue

            # ONNX 세션 캐싱 또는 생성
            if model_path not in model_cache:
                session = ort.InferenceSession(model_path, providers=['CUDAExecutionProvider'])
                model_cache[model_path] = session
            else:
                session = model_cache[model_path]

            # 이미지 전처리
            img = Image.open(img_path).convert('L')
            if cam_id in [6, 7, 8, 9, 10]:
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            img_tensor = transform(img).unsqueeze(0).numpy()  # shape: (1, 1, 300, 480)

            # 모델 추론 수행
            input_name = session.get_inputs()[0].name
            output = session.run(None, {input_name: img_tensor})[0]
            recon = output[0, 0]
            orig = img_tensor[0, 0]

            # 지표 계산
            mae = self.__compute_mae(orig, recon)
            ssim = self.__compute_ssim(orig, recon)
            grad_mae = self.__compute_grad_mae(orig, recon)
            lap_diff = self.__compute_laplacian_variance_diff(orig, recon)
            pix_sum = self.__compute_pixel_sum(orig, recon)
            result = self.__logistic_score([mae, ssim, grad_mae, lap_diff, pix_sum])

            # CSV 결과 저장
            result_rows.append([
                os.path.basename(img_path),
                mae,
                ssim,
                grad_mae,
                lap_diff,
                pix_sum,
                result
            ])

            # 시각화 이미지 저장
            if SAVE_IMAGE:
                orig_img = (orig * 255).astype(np.uint8)
                recon_img = (recon * 255).astype(np.uint8)
                diff_img = np.abs(orig_img.astype(np.int16) - recon_img.astype(np.int16)).astype(np.uint8)
                _, binary_diff = cv2.threshold(diff_img, 30, 255, cv2.THRESH_BINARY)

                # 이미지 회전 및 색상 변환
                orig_img = cv2.rotate(orig_img, cv2.ROTATE_90_CLOCKWISE)
                recon_img = cv2.rotate(recon_img, cv2.ROTATE_90_CLOCKWISE)
                binary_diff = cv2.rotate(binary_diff, cv2.ROTATE_90_CLOCKWISE)

                orig_color = cv2.cvtColor(orig_img, cv2.COLOR_GRAY2BGR)
                recon_color = cv2.cvtColor(recon_img, cv2.COLOR_GRAY2BGR)
                diff_color = cv2.cvtColor(binary_diff, cv2.COLOR_GRAY2BGR)

                # 이미지 상단 텍스트 박스 작성
                metrics_text = [
                    f"MAE: {mae:.4f}",
                    f"SSIM: {ssim:.4f}",
                    f"Grad_MAE: {grad_mae:.4f}",
                    f"Laplacian_Diff: {lap_diff:.4f}",
                    f"Pixel_Sum: {pix_sum}",
                    f"Result: {'Defect' if result else 'OK'}"
                ]
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.5
                thickness = 1
                line_height = 20
                header_h = line_height * len(metrics_text) + 10
                header = np.ones((header_h, orig_color.shape[1] * 3, 3), dtype=np.uint8) * 255

                for i, line in enumerate(metrics_text):
                    y = 10 + (i + 1) * line_height
                    cv2.putText(header, line, (10, y), font, font_scale, (0, 0, 0), thickness)

                combined = cv2.hconcat([orig_color, recon_color, diff_color])
                final_img = cv2.vconcat([header, combined])

                output_vis_dir = os.path.join(os.path.dirname(output_csv), "visual")
                os.makedirs(output_vis_dir, exist_ok=True)
                save_path = os.path.join(output_vis_dir, f"combined_{os.path.basename(img_path)}")
                cv2.imwrite(save_path, final_img)

        # CSV 결과 파일 저장
        output_csv = os.path.join(out_path, "result.csv")
        # os.makedirs(os.path.dirname(output_csv, exist_ok=True))
        with open(output_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(result_rows)

        self.__console.info(f"<SDD Model Inference> Inference results saved to: {output_csv}")

    # 평균 절대 오차
    def __compute_mae(self, orig, recon):
        return np.mean(np.abs(orig - recon))

    # 구조적 유사도(SSIM)
    # 구조적 유사도(SSIM)
    def __compute_ssim(self, orig, recon):
        import pytorch_ssim
        import torch
        orig_tensor = torch.tensor(orig).unsqueeze(0).unsqueeze(0).float()
        recon_tensor = torch.tensor(recon).unsqueeze(0).unsqueeze(0).float()
        
        # 패딩 오류 방지를 위해 window_size를 명시적으로 지정
        ssim_func = pytorch_ssim.SSIM(window_size=11)  # 기본값과 같지만 명시함
        return ssim_func(orig_tensor, recon_tensor).item()


    # Gradient 기반 평균 절대 오차
    def __compute_grad_mae(self, orig, recon):
        grad_orig = np.sqrt(cv2.Sobel(orig, cv2.CV_64F, 1, 0, ksize=3)**2 + cv2.Sobel(orig, cv2.CV_64F, 0, 1, ksize=3)**2)
        grad_recon = np.sqrt(cv2.Sobel(recon, cv2.CV_64F, 1, 0, ksize=3)**2 + cv2.Sobel(recon, cv2.CV_64F, 0, 1, ksize=3)**2)
        return np.mean(np.abs(grad_orig - grad_recon))

    # 라플라시안 기반 경계 선명도 차이
    def __compute_laplacian_variance_diff(self, orig, recon):
        orig = orig.astype(np.float64)
        recon = recon.astype(np.float64)
        var_orig = np.var(cv2.Laplacian(orig, cv2.CV_64F))
        var_recon = np.var(cv2.Laplacian(recon, cv2.CV_64F))
        return abs(var_orig - var_recon)

    # 차영상 기반 임계 픽셀 개수
    def __compute_pixel_sum(self, orig, recon):
        diff = np.abs((orig * 255).astype(np.uint8) - (recon * 255).astype(np.uint8))
        _, binary = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
        return np.sum(binary > 0)

    # ----------------------------
    # 로지스틱 회귀 기반 결함 판정 함수
    # ----------------------------
    def __logistic_score(self, metrics):
        mae, ssim, grad_mae, lap_diff, pix_sum = metrics
        score = (
            318.423821 * mae +
            21.601394 * ssim +
            -26.708228 * grad_mae +
            357.830399 * lap_diff +
            -0.000003 * pix_sum +
            -24.372392  # 바이어스 항
        )
        prob = 1 / (1 + np.exp(-score))
        return 1 if prob > 0.5 else 0

    def __get_all_jpg_files(self, root_dir):
        jpg_files = []
        for dirpath, _, filenames in os.walk(root_dir):
            for file in filenames:
                if file.lower().endswith('.jpg'):
                    jpg_files.append(os.path.abspath(os.path.join(dirpath, file)))
        return jpg_files
    
    def __preprocess_image(self, img):
        img = img.resize((224, 224))
        img = np.array(img).astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))  # HWC -> CHW
        img = np.expand_dims(img, axis=0)  # Add batch dim
        return torch.from_numpy(img) if self.model_path.endswith(".pt") else img

    def close(self):
        """ close the socket and context """

        self.requestInterruption()
        self.quit()
        self.wait()

        # clear job queue
        while not self.__job_queue.empty():
            self.__job_queue.get()
        self.__inference_stop_event.set()
        self.__console.info(f"<SDD Model Inference> Waiting for job done...")
        self.__inference_job_worker.join()

        try:
            self.__socket.setsockopt(zmq.LINGER, 0)
            self.__poller.unregister(self.__socket)
            self.__socket.close()
        except zmq.ZMQError as e:
            self.__console.error(f"<SDD Model Inference> {e}")