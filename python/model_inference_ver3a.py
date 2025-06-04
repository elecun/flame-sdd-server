import os
import pathlib
import glob
import cv2
import csv
import json
import torch
import numpy as np
import onnxruntime as ort
import pytorch_ssim
from PIL import Image
from tqdm import tqdm
from typing import Dict
from torchvision import transforms
from multiprocessing import Process, Queue, Value, cpu_count
from concurrent.futures import ThreadPoolExecutor
from PyQt5.QtCore import QThread, pyqtSignal
import zmq
import threading
import time
from util.logger.console import ConsoleLogger


class SDDModelInference(QThread):
    processing_result_signal = pyqtSignal(str, int)
    update_status_signal = pyqtSignal(dict)

    def __init__(self, context: zmq.Context, connection: str, topic: str, model_config: dict, in_path_root: str, out_path_root: str):
        super().__init__()
        self.__console = ConsoleLogger.get_logger()
        self.__console.info(f"SDD Model Inference Connection : {connection} (topic:{topic})")

        self.__model_config = model_config
        self.__images_root_path = pathlib.Path(in_path_root)
        self.__out_root_path = pathlib.Path(out_path_root)
        self.__job_queue = Queue()

        self.__connection = connection
        self.__topic = topic

        self.__socket = context.socket(zmq.SUB)
        self.__socket.setsockopt(zmq.RCVBUF, 0)
        self.__socket.setsockopt(zmq.RCVTIMEO, 500)
        self.__socket.setsockopt(zmq.LINGER, 0)
        self.__socket.connect(connection)
        self.__socket.subscribe(topic)

        self.__poller = zmq.Poller()
        self.__poller.register(self.__socket, zmq.POLLIN)

        self.__inference_stop_event = threading.Event()
        self.__inference_job_worker = threading.Thread(target=self.__inference, daemon=True)
        self.__inference_job_worker.start()

        self.start()
        self.__console.info("* Start SDD Model Inference")

    def get_connection_info(self):
        return self.__connection

    def get_topic(self):
        return self.__topic

    def run(self):
        while not self.isInterruptionRequested():
            try:
                events = dict(self.__poller.poll(1000))
                if self.__socket in events:
                    if events[self.__socket] == zmq.POLLERR:
                        self.__console.error("<SDD Model Inference> ZMQ Error")
                    elif events[self.__socket] == zmq.POLLIN:
                        topic, data = self.__socket.recv_multipart()
                        if topic.decode() == self.__topic:
                            data = json.loads(data.decode('utf8').replace("'", '"'))
                            if "date" in data and "mt_stand_height" in data and "mt_stand_width" in data:
                                lv2_date = data["date"][0:8]
                                lv2_mt_h = data["mt_stand_height"]
                                lv2_mt_w = data["mt_stand_width"]
                                target_dir = pathlib.Path(lv2_date) / f"{data['date']}_{lv2_mt_h}x{lv2_mt_w}"
                                data["sdd_in_path"] = self.__images_root_path / target_dir
                                data["sdd_out_path"] = self.__out_root_path / target_dir
                                self.__job_queue.put(data)
                                self.__console.info(f"<SDD Model Inference> Added job to queue ({self.__job_queue.qsize()})")
            except Exception as e:
                self.__console.error(f"<SDD Model Inference> Exception: {e}")
                break

    def __inference(self):
        while not self.__inference_stop_event.is_set():
            time.sleep(0.5)
            if not self.__job_queue.empty():
                job_description = self.__job_queue.get()
                self.update_status_signal.emit({"working": True})
                model_root = self.__model_config.get("model_root", "/path/to/models")
                if "sdd_in_path" in job_description and "sdd_out_path" in job_description:
                    self.__inference_all(model_root, job_description["sdd_in_path"], job_description["sdd_out_path"], job_description)
                self.update_status_signal.emit({"working": False})

    def __inference_all(self, model_root: str, in_path: str, out_path: str, job_desc: Dict):
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

        self.__console.info(f"<SDD Model Inference> Parallel inference completed: {output_csv}")
        self.processing_result_signal.emit(output_csv, job_desc.get("fm_length", 0))

    def close(self):
        self.requestInterruption()
        self.quit()
        self.wait()
        self.__inference_stop_event.set()
        self.__inference_job_worker.join()
        self.__socket.setsockopt(zmq.LINGER, 0)
        self.__poller.unregister(self.__socket)
        self.__socket.close()
