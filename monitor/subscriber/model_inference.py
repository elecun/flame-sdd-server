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

import re
import torch.nn as nn
from xgboost import XGBClassifier

# ===== NEW: onnxruntime =====
try:
    import onnxruntime as ort
except Exception as e:
    ort = None

# =========================
# Index range per camera (inclusive)
# =========================
# IDX_FROM = 0
# IDX_TO   = 9999

# =========================
# Global config (diff ¡æ mask ÀÏ°ü·ÎÁ÷)
# =========================
DIFF_THRESHOLD    = 70
MIN_AREA          = 100
USE_OPENING       = True
OPEN_KERNEL_SIZE  = (100, 1)
USE_PERCENTILE    = False
PERCENTILE_P      = 95
MIN_THRESH_FLOOR  = 50

USE_HIGHPASS      = False
HP_SIGMA          = 21


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

        # # add xgboost (25.07.17)
        self.xgb_model = None

        # store parameters
        self.__connection = connection
        self.__topic = topic
        self.__save_visual = save_visual
        self.__job_lv2_info = {}

        # initialize zmq
        self.__socket = context.socket(zmq.SUB)
        self.__socket.setsockopt(zmq.RCVBUF .RCVHWM, 100)
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
        # "date":"20250804095316",
        # "mt_stand_height":200,
        # "mt_stand_width":200,
        # "sdd_in_path":"/home/dk-sdd/local_storage/20250804/20250804095316_200x200",
        # "sdd_out_path":"/home/dk-sdd/nas_storage/20250804/20250804095316_200x200"
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
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    if os.path.exists(path) and os.path.isdir(path):
                        shutil.rmtree(path, onerror=self.__remove_readonly)
                        self.__console.info(f"Deleted {path}")
                        return
                    else:
                        self.__console.error(f"{path} does not exist or is not a directory")
                        return
                except Exception as e:
                    self.__console.error(f"Attempt {attempt}: Failed to remove {path} : {e}")
                    time.sleep(0.1) 
            self.__console.error(f"Failed to remove {path} after {max_attempts} attempts.")

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

            # check if there is a job in the queue
            if not self.__job_queue.empty():
                job_description = self.__job_queue.get()
                self.__console.debug(f"<SDD Model Inference> Do Inference... (Remaining {self.__job_queue.qsize()})")

                # update status signal
                self.update_status_signal.emit({"working":True})
                model_root = self.__model_config.get("model_root", "/home/dk-sdd/dev/flame-sdd-server/bin/model")
                if "sdd_in_path" in job_description and "sdd_out_path" in job_description:
                    self.__run_parallel_inference(model_root, job_description["sdd_in_path"], job_description["sdd_out_path"], job_desc=job_description)

                # status update & remove processed images
                self.update_status_signal.emit({"working":False})
                self.__delete_directory_background(job_description["sdd_in_path"])

    
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

        # end of inference & emit signal
        self.__console.info(f"<SDD Model Inference> Inference results saved to: {output_csv}")
        self.processing_result_signal.emit(output_csv, job_desc.get("fm_length",100))

        # rename the detected defect image from result.csv file
        rows = []
        with open(output_csv, 'r', newline='') as f:
            reader = csv.reader(f)
            header = next(reader) # skip header (first list)
            rows = [row for row in reader]
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda row: self.rename_file(row, out_path), rows))
        renamed = [r for r in results if r==True]
        self.__console.info(f"{len(renamed)}/{len(results)} file(s) are renamed for self-explanatory")


    def __infer_worker(self, cams, model_path, gpu_id, input_root, result_queue, output_csv, save_visual, progress, total):

        # # add xgboost model (25/07/24)
        self.xgb_model = XGBClassifier(tree_method='gpu_hist', predictor="gpu_predictor")
        self.xgb_model.load_model(f"{self.__model_config['model_root']}/xgboost_model.json")
        print(f"{self.__model_config['model_root']}/xgboost_model.json")

        if torch.cuda.is_available():
            torch.cuda.set_device(gpu_id)
        (sess, in_name, out_name), device, in_h, in_w = self.create_session_pth(model_path, gpu_id, in_h=300, in_w=480)
        sobel_x, sobel_y = self._make_sobel(device)

        # gather all images
        image_tasks = []
        for cam_id in cams:
            cam_folder = os.path.join(input_root, f"camera_{cam_id}")
            for ext in ('*.jpg', '*.jpeg', '*.JPG', '*.JPEG'):
                image_tasks.extend([(cam_id, img_path) for img_path in glob.glob(os.path.join(cam_folder, ext))])

        with ThreadPoolExecutor(max_workers=min(cpu_count(), 8)) as executor:
            futures = []
            for cam_id, img_path in image_tasks:
                futures.append(executor.submit(
                    self.process_image,
                    (sess, in_name, out_name), device, cam_id, img_path, result_queue, output_csv, save_visual,
                    sobel_x, sobel_y, in_h, in_w, progress
                ))
            for f in futures:
                f.result()

        result_queue.put(None)


    def process_image(self, sess_pack, device, cam_id, img_path, result_queue, output_csv, save_visual,
                  sobel_x, sobel_y, in_h, in_w, progress):
        try:
            sess, in_name, out_name = sess_pack
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                raise RuntimeError("Failed to read image")

            if cam_id in [6, 7, 8, 9, 10]:
                img = cv2.flip(img, 1)

            img = cv2.resize(img, (in_w, in_h)).astype(np.float32) / 255.0

            # ===== ONNX Ãß·Ð =====
            onnx_in = img[np.newaxis, np.newaxis, :, :]  # (1,1,H,W), float32
            onnx_out = sess.run([out_name], {in_name: onnx_in})[0]  # (1,1,H,W)

            # torch ÅÙ¼­·Î º¯È¯(¸ÞÆ®¸¯ °è»ê¿ë)
            recon = torch.from_numpy(onnx_out).to(device=device, dtype=torch.float32)  # (1,1,H,W)
            recon2d = recon[0, 0]
            orig_t = torch.from_numpy(img).to(device=device, dtype=torch.float32)      # (H,W)

            # Metrics
            mae = self.compute_mae(orig_t, recon2d)
            ssim = self.compute_ssim(orig_t[None, None], recon2d[None, None])
            grad_mae = self.compute_grad_mae(orig_t[None, None], recon2d[None, None], sobel_x, sobel_y)
            lap_diff = self.compute_laplacian_variance_diff_torch(orig_t, recon2d)

            orig_u8  = (orig_t.detach().cpu().numpy()  * 255).astype(np.uint8)
            recon_u8 = (recon2d.detach().cpu().numpy() * 255).astype(np.uint8)
            pix_sum = self.compute_pixel_sum(orig_u8, recon_u8)

            # XGBoost ¿¹Ãø (+ ÇÈ¼¿ÇÕ 0ÀÌ¸é ¹«Á¶°Ç ¾çÇ°)
            xgb_input = np.array([[mae, ssim, grad_mae, lap_diff, pix_sum]], dtype=np.float32)
            result = int(self.xgb_model.predict(xgb_input)[0])
            if pix_sum == 0:
                result = 0

            result_queue.put([
                os.path.basename(img_path),
                mae, ssim, grad_mae, lap_diff, pix_sum, result
            ])

        except Exception:
            result_queue.put([
                os.path.basename(img_path) if img_path else "unknown",
                np.nan, np.nan, np.nan, np.nan, np.nan, -1
            ])
        finally:
            with progress.get_lock():
                progress.value += 1

            if save_visual and 'orig_u8' in locals() and 'recon_u8' in locals():
                try:
                    mask255 = self.diff_to_mask(orig_u8, recon_u8, min_area=None, out_255=True)
                    orig_v   = cv2.rotate(orig_u8,  cv2.ROTATE_90_CLOCKWISE)
                    recon_v  = cv2.rotate(recon_u8, cv2.ROTATE_90_CLOCKWISE)
                    binary_v = cv2.rotate(mask255,  cv2.ROTATE_90_CLOCKWISE)
                    combined = cv2.hconcat([
                        cv2.cvtColor(orig_v,  cv2.COLOR_GRAY2BGR),
                        cv2.cvtColor(recon_v, cv2.COLOR_GRAY2BGR),
                        cv2.cvtColor(binary_v, cv2.COLOR_GRAY2BGR),
                    ])
                    vis_out_dir = os.path.join(os.path.dirname(output_csv), f"visual/camera_{cam_id}")
                    os.makedirs(vis_out_dir, exist_ok=True)
                    cv2.imwrite(os.path.join(vis_out_dir, os.path.basename(img_path)), combined)
                except Exception:
                    pass

    def create_session_pth(self, onnx_path, gpu_id, in_h=300, in_w=480):
        device = torch.device(f"cuda:{gpu_id}" if torch.cuda.is_available() else "cpu")
        sess, in_name, out_name = self.load_vae_from_onnx(onnx_path, gpu_id)
        return (sess, in_name, out_name), device, in_h, in_w
    
    def load_vae_from_onnx(self, onnx_path: str, gpu_id: int):
        assert ort is not None, "onnxruntime°¡ ¼³Ä¡µÇ¾î ÀÖÁö ¾Ê½À´Ï´Ù. (pip install onnxruntime-gpu ¶Ç´Â onnxruntime)"
        providers = []
        
        if torch.cuda.is_available():
            providers.append(('CUDAExecutionProvider', {'device_id': gpu_id}))
        providers.append('CPUExecutionProvider')
        sess = ort.InferenceSession(onnx_path, providers=providers)
        in_name = sess.get_inputs()[0].name
        out_name = sess.get_outputs()[0].name
        return sess, in_name, out_name
    
    def compute_mae(self, orig, recon):
        return torch.mean(torch.abs(orig - recon)).item()
    
    def compute_ssim(self, orig4d, recon4d):
        return pytorch_ssim.ssim(orig4d, recon4d).item()
    
    def compute_grad_mae(self, orig4d, recon4d, sobel_x, sobel_y):
        gox = torch.nn.functional.conv2d(orig4d, sobel_x, padding=1)
        goy = torch.nn.functional.conv2d(orig4d, sobel_y, padding=1)
        grx = torch.nn.functional.conv2d(recon4d, sobel_x, padding=1)
        gry = torch.nn.functional.conv2d(recon4d, sobel_y, padding=1)
        grad_orig = torch.sqrt(gox**2 + goy**2 + 1e-12)
        grad_recon = torch.sqrt(grx**2 + gry**2 + 1e-12)
        return torch.mean(torch.abs(grad_orig - grad_recon)).item()

    def compute_laplacian_variance_diff_torch(self, orig2d_t: torch.Tensor, recon2d_t: torch.Tensor):
        device = orig2d_t.device
        lap_k = torch.tensor([[0, 1, 0],
                            [1,-4, 1],
                            [0, 1, 0]], dtype=torch.float32, device=device).view(1,1,3,3)
        o = torch.nn.functional.conv2d(orig2d_t.view(1,1,*orig2d_t.shape), lap_k, padding=1)
        r = torch.nn.functional.conv2d(recon2d_t.view(1,1,*recon2d_t.shape), lap_k, padding=1)
        var_o = torch.var(o)
        var_r = torch.var(r)
        return float(torch.abs(var_o - var_r).item())

    def compute_pixel_sum(self, orig2d_u8, recon2d_u8):
        mask01 = self.diff_to_mask(orig2d_u8, recon2d_u8, min_area=MIN_AREA, out_255=False)
        return int(mask01.sum())
    
    def diff_to_mask(self, orig_u8, recon_u8, *,
                 use_percentile=USE_PERCENTILE, percentile_p=PERCENTILE_P,
                 fixed_thr=DIFF_THRESHOLD, opening=USE_OPENING, open_kernel_size=OPEN_KERNEL_SIZE,
                 min_area=None, out_255=True,
                 highpass=USE_HIGHPASS, hp_sigma=HP_SIGMA):
        img_o = orig_u8.astype(np.float32)
        img_r = recon_u8.astype(np.float32)

        if highpass:
            blur_o = cv2.GaussianBlur(img_o, (0, 0), hp_sigma)
            blur_r = cv2.GaussianBlur(img_r, (0, 0), hp_sigma)
            img_o = cv2.addWeighted(img_o, 1.0, blur_o, -1.0, 0)
            img_r = cv2.addWeighted(img_r, 1.0, blur_r, -1.0, 0)

        diff = np.abs(img_o - img_r).astype(np.uint8)

        thr = max(int(np.percentile(diff, percentile_p)), MIN_THRESH_FLOOR) if use_percentile else fixed_thr
        _, mask = cv2.threshold(diff, thr, 255, cv2.THRESH_BINARY)

        if opening:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, open_kernel_size)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=1)

        if min_area is not None:
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
            clean = np.zeros_like(mask, dtype=np.uint8)
            for i in range(1, num_labels):
                if stats[i, cv2.CC_STAT_AREA] >= min_area:
                    clean[labels == i] = 255
            mask = clean

        return mask if out_255 else (mask > 0).astype(np.uint8)

    def __diff_to_binary(self, orig_u8, recon_u8):
        return self.diff_to_mask(orig_u8, recon_u8, min_area=None, out_255=True)


    def rename_file(self, row, base_dir):
        """ rename the filename by SDD result"""
        filename = row[0].strip()
        defect = row[-1].strip() # last column is defect flag

        if defect != '1':
            return False

        if '_' not in filename:
            return False

        prefix = filename.split('_')[0]
        subdir = f"camera_{prefix}"
        src_path = os.path.join(base_dir, subdir, filename)

        if not os.path.isfile(src_path):
            return False

        name, ext = os.path.splitext(filename)
        dst_path = os.path.join(base_dir, subdir, f"{name}_x{ext}")

        if os.path.exists(dst_path):
            return False

        try:
            os.rename(src_path, dst_path)
            return True
        except Exception as e:
            return False

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
    
    def _make_sobel(self, device):
        sobel_x = torch.tensor([[-1, 0, 1],
                                [-2, 0, 2],
                                [-1, 0, 1]], dtype=torch.float32, device=device).view(1,1,3,3)
        sobel_y = torch.tensor([[-1, -2, -1],
                                [ 0,  0,  0],
                                [ 1,  2,  1]], dtype=torch.float32, device=device).view(1,1,3,3)
        return sobel_x, sobel_y