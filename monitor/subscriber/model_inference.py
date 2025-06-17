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
import pytorch_ssim
import stat


class SDDModelInference(QThread):
    processing_result_signal = pyqtSignal(str, int) #result file path, fm_length
    update_status_signal = pyqtSignal(dict) # signal for connection status message
    '''
    models = [{cam_ids":[1,2], "model_path:"/path/mode.onnx"}, ...}]
    '''

    def __init__(self, context:zmq.Context, connection:str, topic:str, model_config:dict, in_path_root:str, out_path_root:str, save_visual:bool):
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
        self.__save_visual = save_visual
        self.__job_lv2_info = {}

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

        # for test in local
        # test_data = {
        # "date":"20250527123558",
        # "mt_stand_height":200,
        # "mt_stand_width":200,
        # "sdd_in_path":"/home/dk-sdd/local_storage/20250527/20250527123558_200x200",
        # "sdd_out_path":"/home/dk-sdd/nas_storage/20250527/20250527123558_200x200"
        # }
        # self.__job_queue.put(test_data)

    def add_job_lv2_info(self, date:str, mt_stand_height:int, mt_stand_width:int):
        self.__job_lv2_info["date"] = date
        self.__job_lv2_info["mt_stand_width"] = mt_stand_width
        self.__job_lv2_info["mt_stand_height"] = mt_stand_height
        self.__console.info(f"Updated the job desc to process the SDD (waiting for start)")
    
    def __remove_readonly(self, func, path, exc_info):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    def __delete_directory_background(self, path: str):
        def worker():
            try:
                if os.path.exists(path) and os.path.isdir(path):
                    shutil.rmtree(path, onerror=self.__remove_readonly)
                    self.__console.info(f"Deleted {path}")
                else:
                    self.__console.error(f"{path} does not exist or is not a directory")
            except Exception as e:
                self.__console.error(f"Failed to remove {path} : {e}")

        thread = threading.Thread(target=worker, daemon=True)
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
                    topic, data = self.__socket.recv_multipart()
                    if topic.decode() == self.__topic:
                        data = json.loads(data.decode('utf8').replace("'", '"'))

                        if "hmd_signal_1_on" in data and "hmd_signal_2_on" in data and "online_signal_on" in data:
                            self.__console.info(f"<SDD Model Inference> ready : {data}")
                            if not data["hmd_signal_1_on"] and not data["hmd_signal_2_on"] and data["online_signal_on"]:
                                if "date" in self.__job_lv2_info and "mt_stand_height" in self.__job_lv2_info:
                                    lv2_date = self.__job_lv2_info["date"][0:8]  # YYYYMMDD
                                    lv2_mt_h = self.__job_lv2_info["mt_stand_height"]
                                    lv2_mt_w = self.__job_lv2_info["mt_stand_width"]
                                    target_dir = pathlib.Path(lv2_date) / f"{self.__job_lv2_info['date']}_{lv2_mt_w}x{lv2_mt_h}"
                                    data["sdd_in_path"] = self.__images_root_path / target_dir
                                    data["sdd_out_path"] = self.__out_root_path / target_dir
                                    data["save_visual"] = self.__save_visual
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
                    self.__run_parallel_inference(model_root, job_description["sdd_in_path"], job_description["sdd_out_path"], job_desc=job_description)

                self.update_status_signal.emit({"working":False})
                self.__delete_directory_background(job_description["sdd_in_path"])

    def __create_session(self, model_path, gpu_id):
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        return ort.InferenceSession(model_path, sess_options=so, providers=[("CUDAExecutionProvider", {"device_id": gpu_id})])
    
    def __process_image(self, session, input_name, cam_id, img_path, result_queue, output_csv, save_visual, progress):
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if cam_id in [6, 7, 8, 9, 10]:
            img = cv2.flip(img, 1)
        img = cv2.resize(img, (480, 300)).astype(np.float32) / 255.0
        img_tensor = torch.tensor(img).unsqueeze(0).unsqueeze(0).to('cuda')  # GPU 텐서로 올림

        # ONNX는 numpy만 받으므로 다시 CPU 텐서로 전송
        output = session.run(None, {input_name: img_tensor.cpu().numpy()})[0]
        recon = torch.tensor(output[0, 0]).to('cuda')
        orig = img_tensor[0, 0].to(recon.device)

        # 각종 메트릭 계산. GPU에서 가능하면 다 실행
        mae = self.__compute_mae(orig, recon)
        ssim = self.__compute_ssim(orig.unsqueeze(0).unsqueeze(0), recon.unsqueeze(0).unsqueeze(0))
        grad_mae = self.__compute_grad_mae(orig.unsqueeze(0).unsqueeze(0), recon.unsqueeze(0).unsqueeze(0))
        lap_diff = self.__compute_laplacian_variance_diff(orig, recon)
        pix_sum = self.__compute_pixel_sum(orig, recon)
        result = self.__logistic_score([mae, ssim, grad_mae, lap_diff, pix_sum])

        result_queue.put([
            os.path.basename(img_path),
            mae, ssim, grad_mae, lap_diff, pix_sum, result
        ])

        with progress.get_lock():
            progress.value += 1

        if save_visual:
            # 시각화 저장
            orig_img = (orig.cpu().numpy() * 255).astype(np.uint8)
            recon_img = (recon.cpu().numpy() * 255).astype(np.uint8)
            diff_img = np.abs(orig_img.astype(np.int16) - recon_img.astype(np.int16)).astype(np.uint8)
            _, binary_diff = cv2.threshold(diff_img, 30, 255, cv2.THRESH_BINARY)
            orig_img = cv2.rotate(orig_img, cv2.ROTATE_90_CLOCKWISE)
            recon_img = cv2.rotate(recon_img, cv2.ROTATE_90_CLOCKWISE)
            binary_diff = cv2.rotate(binary_diff, cv2.ROTATE_90_CLOCKWISE)
            combined = cv2.hconcat([
                cv2.cvtColor(orig_img, cv2.COLOR_GRAY2BGR),
                cv2.cvtColor(recon_img, cv2.COLOR_GRAY2BGR),
                cv2.cvtColor(binary_diff, cv2.COLOR_GRAY2BGR)
            ])
            vis_out_dir = os.path.join(os.path.dirname(output_csv), f"visual/camera_{cam_id}")
            os.makedirs(vis_out_dir, exist_ok=True)
            cv2.imwrite(os.path.join(vis_out_dir, os.path.basename(img_path)), combined)


    def __infer_worker(self, cams, model_path, gpu_id, input_root, result_queue, output_csv, save_visual, progress, total):
        session = self.__create_session(model_path, gpu_id)
        input_name = session.get_inputs()[0].name

        # 이미지 경로 수집
        image_tasks = []
        for cam_id in cams:
            cam_folder = os.path.join(input_root, f"camera_{cam_id}")
            for ext in ('*.jpg', '*.jpeg', '*.JPG', '*.JPEG'):
                image_tasks.extend([(cam_id, img_path) for img_path in glob.glob(os.path.join(cam_folder, ext))])

        # 이 프로세스 안에서 멀티스레드 돌려서 이미지 개별 처리
        with ThreadPoolExecutor(max_workers=min(cpu_count(), 8)) as executor:
            futures = []
            for cam_id, img_path in image_tasks:
                futures.append(executor.submit(self.__process_image, session, input_name, cam_id, img_path, result_queue, output_csv, save_visual, progress))
            for f in futures:
                f.result()

        result_queue.put(None)  # 처리 끝났다고 알림

    def __run_parallel_inference(self, model_root:str, in_path:str, out_path:str, job_desc:dict):
        camera_groups = {
            "vae_group_1_10_5_6.onnx_part1": {"model": f"{model_root}/vae_group_1_10_5_6.onnx", "cams": [1, 5], "gpu": 0},
            "vae_group_1_10_5_6.onnx_part2": {"model": f"{model_root}/vae_group_1_10_5_6.onnx", "cams": [6, 10], "gpu": 0},
            "vae_group_2_9_4_7.onnx_part1": {"model": f"{model_root}/vae_group_2_9_4_7.onnx", "cams": [2, 4], "gpu": 1},
            "vae_group_2_9_4_7.onnx_part2": {"model": f"{model_root}/vae_group_2_9_4_7.onnx", "cams": [7, 9], "gpu": 1},
            "vae_group_3_8.onnx": {"model": f"{model_root}/vae_group_3_8.onnx", "cams": [3, 8], "gpu": 0}
        }
        
        start_time = time.time()

        processes = []
        result_queue = Queue()
        total_images = 0

        # 총 이미지 수 미리 세서 tqdm에 사용
        for config in camera_groups.values():
            for cam_id in config['cams']:
                cam_folder = os.path.join(in_path, f"camera_{cam_id}")
                for ext in ('*.jpg', '*.jpeg', '*.JPG', '*.JPEG'):
                    total_images += len(glob.glob(os.path.join(cam_folder, ext)))

        progress = Value('i', 0)
        pbar = tqdm(total=total_images, desc="Total Progress", position=0)

        # 카메라 그룹별로 프로세스 생성
        output_csv = os.path.join(out_path, "result.csv")
        save_visual = job_desc.get("save_visual", False)
        for config in camera_groups.values():
            p = Process(
                target=self.__infer_worker,
                args=(config['cams'], config['model'], config['gpu'], in_path, result_queue, output_csv, save_visual, progress, total_images)
            )
            processes.append(p)
            p.start()

        end_signals = 0
        results = [['filename', 'MAE', 'SSIM', 'Grad_MAE', 'Laplacian_Diff', 'Pixel_Sum', 'result']]
        while end_signals < len(processes):
            item = result_queue.get()
            if item is None:
                end_signals += 1
            else:
                results.append(item)
                pbar.n = progress.value
                pbar.refresh()

        for p in processes:
            p.join()

        result_queue.close()
        result_queue.join_thread()

        pbar.close()

        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
        with open(output_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(results)

        elapsed = time.time() - start_time
        print(f"\nTotal Inference Time: {elapsed:.2f} seconds")

        self.__console.info(f"<SDD Model Inference> Inference results saved to: {output_csv}")
        self.processing_result_signal.emit(output_csv, job_desc.get("fm_length",100))

    def __compute_mae(self, orig, recon):
        return torch.mean(torch.abs(orig - recon)).item()

    def __compute_ssim(self, orig, recon):
        return pytorch_ssim.ssim(orig, recon).item()
    
    def __compute_grad_mae(self, orig, recon):
        sobel_x = torch.tensor([[[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]]], dtype=torch.float32, device=orig.device).unsqueeze(0)
        sobel_y = torch.tensor([[[-1, -2, -1], [0, 0, 0], [1, 2, 1]]], dtype=torch.float32, device=orig.device).unsqueeze(0)
        grad_orig = torch.sqrt(
            torch.nn.functional.conv2d(orig, sobel_x, padding=1)**2 +
            torch.nn.functional.conv2d(orig, sobel_y, padding=1)**2
        )
        grad_recon = torch.sqrt(
            torch.nn.functional.conv2d(recon, sobel_x, padding=1)**2 +
            torch.nn.functional.conv2d(recon, sobel_y, padding=1)**2
        )
        return torch.mean(torch.abs(grad_orig - grad_recon)).item()

    def __compute_laplacian_variance_diff(self, orig, recon):
        var_orig = np.var(cv2.Laplacian(orig.cpu().numpy().astype(np.float64), cv2.CV_64F))
        var_recon = np.var(cv2.Laplacian(recon.cpu().numpy().astype(np.float64), cv2.CV_64F))
        return abs(var_orig - var_recon)

    def __compute_pixel_sum(self, orig, recon):
        diff = torch.abs(orig - recon) * 255
        binary = (diff > 30).int()
        return binary.sum().item()
    
    def __logistic_score(self, metrics):
        mae, ssim, grad_mae, lap_diff, pix_sum = metrics
        score = (
            318.423821 * mae +
            21.601394 * ssim +
            -26.708228 * grad_mae +
            357.830399 * lap_diff +
            -0.000003 * pix_sum +
            -24.372392
        )
        prob = 1 / (1 + np.exp(-score))
        return 1 if prob > 0.5 else 0

    def close(self):
        """ close the socket and context """

        self.requestInterruption()
        self.quit()
        self.wait()

        try:
            self.__socket.setsockopt(zmq.LINGER, 0)
            self.__poller.unregister(self.__socket)
            self.__socket.close()
        except zmq.ZMQError as e:
            self.__console.error(f"<SDD Model Inference> {e}")

        # clear job queue
        while not self.__job_queue.empty():
            self.__job_queue.get()
        self.__inference_stop_event.set()
        self.__console.info(f"<SDD Model Inference> Waiting for job done...")
        self.__inference_job_worker.join()