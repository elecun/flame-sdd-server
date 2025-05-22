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


class SDDModelInference(QThread):
    processing_result_signal = pyqtSignal(dict) # signal for level2 data update
    '''
    models = [{cam_ids":[1,2], "model_path:"/path/mode.onnx"}, ...}]
    '''

    def __init__(self, context:zmq.Context, connection:str, topic:str, models:dict, in_path:str, out_path:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"SDD Model Inference Connection : {connection} (topic:{topic})")

        # save paramters
        self.__models = models
        self.__images_root_path = pathlib.Path(in_path)
        self.__out_root_path = pathlib.Path(out_path)
        self.__job_queue = queue.Queue()
        self.__session = []

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

        self.__console.info("* Start SDD Model Inference")

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

                            data["in_path"] = self.__images_root_path
                            data["out_path"] = self.__out_root_path
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
            time.sleep(1)

        # listup input files
        image_paths = self.__get_all_jpg_files(self.__image_root_path)
        model_type = os.path.splitext(self.__model_path)[1].lower()

        # model load
        if model_type == ".pt":
            model = torch.load(self.__model_path, map_location='cuda')
            model.eval()
        elif model_type == ".onnx":
            session = ort.InferenceSession(self.__model_path)
        else:
            print(f"Unsupported model format: {self.__model_path}")
            return
        
        # inference
        for img_path in image_paths:
            img = Image.open(img_path).convert("RGB")
            input_tensor = self.__preprocess_image(img)

            if model_type == ".pt":
                with torch.no_grad():
                    output = model(input_tensor)
                    result = bool(torch.argmax(output, dim=1).item())
            else:  # onnx
                ort_input = {session.get_inputs()[0].name: input_tensor.numpy()}
                ort_output = session.run(None, ort_input)
                result = bool(np.argmax(ort_output[0], axis=1)[0])

            # result
            self.processing_result_signal.emit(result, os.path.basename(img_path))

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
        # clear job queue
        while not self.__job_queue.empty():
            self.__job_queue.get()
        self.__inference_stop_event.set()
        self.__console.info(f"<SDD Model Inference> Waiting for job done...")
        self.__inference_job_worker.join()

        self.requestInterruption()
        self.quit()
        self.wait()

        try:
            self.__socket.setsockopt(zmq.LINGER, 0)
            self.__poller.unregister(self.__socket)
            self.__socket.close()
        except zmq.ZMQError as e:
            self.__console.error(f"<Level2 Data Monitor> {e}")