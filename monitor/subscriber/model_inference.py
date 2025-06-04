"""
Surface Defect Model Inference Subscriber
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
import cv2
import queue
import pathlib
from multiprocessing import Process, Queue, Value, cpu_count
from concurrent.futures import ThreadPoolExecutor

from torchvision import transforms
from tqdm import tqdm
import csv
import glob
import shutil


class SDDModelInference(QThread):
    processing_result_signal = pyqtSignal(str, int) #result file path, fm_length
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
                self.__delete_directory_background(job_description["sdd_in_path"])
                
    def __inference_all(self, model_root, in_path:str, out_path:str, job_desc:dict):
        camera_groups = {
            "vae_group_1_10_5_6.onnx_part1": {"model": f"{model_root}/vae_group_1_10_5_6.onnx", "cams": [1, 5], "gpu": 0},
            "vae_group_1_10_5_6.onnx_part2": {"model": f"{model_root}/vae_group_1_10_5_6.onnx", "cams": [6, 10], "gpu": 0},
            "vae_group_2_9_4_7.onnx_part1": {"model": f"{model_root}/vae_group_2_9_4_7.onnx", "cams": [2, 4], "gpu": 1},
            "vae_group_2_9_4_7.onnx_part2": {"model": f"{model_root}/vae_group_2_9_4_7.onnx", "cams": [7, 9], "gpu": 1},
            "vae_group_3_8.onnx": {"model": f"{model_root}/vae_group_3_8.onnx", "cams": [3, 8], "gpu": 0}
        }

        def infer_worker(cams, model_path, gpu_id, input_root, result_queue, output_csv, progress):
            session = ort.InferenceSession(model_path, providers=[("CUDAExecutionProvider", {"device_id": gpu_id})])
            input_name = session.get_inputs()[0].name
            image_tasks = []
            for cam_id in cams:
                cam_folder = os.path.join(input_root, f"camera_{cam_id}")
                for ext in ('*.jpg', '*.jpeg', '*.JPG', '*.JPEG'):
                    image_tasks.extend([(cam_id, img) for img in glob.glob(os.path.join(cam_folder, ext))])
            
            def process_image(cam_id, img_path):
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if cam_id in [6,7,8,9,10]:
                    img = cv2.flip(img, 1)
                img = cv2.resize(img, (480, 300)).astype(np.float32) / 255.0
                tensor = torch.tensor(img).unsqueeze(0).unsqueeze(0).to('cuda')
                output = session.run(None, {input_name: tensor.cpu().numpy()})[0]
                recon = torch.tensor(output[0, 0]).to('cuda')
                orig = tensor[0, 0].to('cuda')

                mae = torch.mean(torch.abs(orig - recon)).item()
                ssim = pytorch_ssim.ssim(orig.unsqueeze(0).unsqueeze(0), recon.unsqueeze(0).unsqueeze(0)).item()
                grad_mae = torch.mean(torch.abs(torch.gradient(orig)[0] - torch.gradient(recon)[0])).item()
                lap_diff = abs(np.var(cv2.Laplacian(orig.cpu().numpy(), cv2.CV_64F)) - np.var(cv2.Laplacian(recon.cpu().numpy(), cv2.CV_64F)))
                pix_sum = torch.sum(torch.abs(orig - recon) * 255 > 30).item()
                result = 1 if 1 / (1 + np.exp(-(318.42 * mae + 21.60 * ssim - 26.70 * grad_mae + 357.83 * lap_diff - 0.000003 * pix_sum - 24.37))) > 0.5 else 0

                result_queue.put([os.path.basename(img_path), mae, ssim, grad_mae, lap_diff, pix_sum, result])
                with progress.get_lock():
                    progress.value += 1

            with ThreadPoolExecutor(max_workers=cpu_count()) as executor:
                for cam_id, img_path in image_tasks:
                    executor.submit(process_image, cam_id, img_path)
            result_queue.put(None)

        output_csv = os.path.join(out_path, "result.csv")
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
        result_queue = Queue()
        progress = Value('i', 0)

        processes = []
        for config in camera_groups.values():
            p = Process(target=infer_worker, args=(config['cams'], config['model'], config['gpu'], str(in_path), result_queue, output_csv, progress))
            p.start()
            processes.append(p)

        results = [['filename', 'MAE', 'SSIM', 'Grad_MAE', 'Laplacian_Diff', 'Pixel_Sum', 'result']]
        finished = 0
        while finished < len(processes):
            item = result_queue.get()
            if item is None:
                finished += 1
            else:
                results.append(item)

        for p in processes:
            p.join()

        with open(output_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(results)

        self.__console.info(f"<SDD Model Inference> Inference results saved to: {output_csv}")
        self.processing_result_signal.emit(output_csv, job_desc.get("fm_length",0))

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