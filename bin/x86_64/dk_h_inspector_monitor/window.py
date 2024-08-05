'''
DK H Inspetor Monitor
@author Byunghun Hwang<bh.hwang@iae.re.kr>
'''

import sys, os
import pathlib
try:
    # using PyQt5
    from PyQt5.QtGui import QImage, QPixmap, QCloseEvent, QStandardItemModel, QStandardItem
    from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QMessageBox, QFileDialog, QFrame, QVBoxLayout, QComboBox, QLineEdit, QCheckBox
    from PyQt5.uic import loadUi
    from PyQt5.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
except ImportError:
    # using PyQt6
    from PyQt6.QtGui import QImage, QPixmap, QCloseEvent, QStandardItemModel, QStandardItem
    from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QMessageBox, QFileDialog, QFrame, QVBoxLayout, QComboBox, QLineEdit, QCheckBox
    from PyQt6.uic import loadUi
    from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
    
from datetime import datetime
from PIL import ImageQt, Image
from sys import platform
import pyqtgraph as graph
import zmq
import json
import threading
import numpy as np
import cv2
import time

from console import ConsoleLogger


'''
Main Window
'''

SERVER_IP_ADDRESS = "192.168.0.50"

class AppWindow(QMainWindow):
    def __init__(self, config:dict):
        super().__init__()
        
        self.__console = ConsoleLogger.get_logger() # logger
        
        self.__frame_win_defect_layout = QVBoxLayout()
        self.__frame_win_defect_plot = graph.PlotWidget()

        # definitions for data pipeline
        self.op_trigger_context = zmq.Context()
        self.op_trigger_socket = self.op_trigger_context.socket(zmq.PUB)
        self.op_trigger_socket.setsockopt(zmq.SNDHWM, 1000)
        self.op_trigger_socket.bind("tcp://*:5008")

        self.camera_status_monitor_event = threading.Event()
        self.camera_status_monitor_thread = threading.Thread(target=self.__camera_status_update, args =(self.camera_status_monitor_event, ))
        self.camera_status_monitor_thread.start()

        # camera monitoring worker thread
        self.camera_monitor_event = threading.Event()
        self.camera_monitor_thread = threading.Thread(target=self.__cam_view_monitoring, args =(self.camera_monitor_event, ))
        self.camera_monitor_thread.start()
        
        try:            
            if "gui" in config:
                
                # load gui file
                ui_path = pathlib.Path(config["app_path"]) / config["gui"]
                if os.path.isfile(ui_path):
                    loadUi(ui_path, self)
                else:
                    raise Exception(f"Cannot found UI file : {ui_path}")
                
                # frame window components preparation
                self.__frame_win_defect = self.findChild(QFrame, name="frame_defect_view")
                self.__frame_win_defect_layout.addWidget(self.__frame_win_defect_plot)
                self.__frame_win_defect_layout.setContentsMargins(0, 0, 0, 0)
                self.__frame_win_defect_plot.setBackground('w')
                self.__frame_win_defect_plot.showGrid(x=True, y=True)
                self.__frame_win_defect.setLayout(self.__frame_win_defect_layout)

                # button component connection
                self.btn_op_trigger_on.clicked.connect(self.on_click_op_trigger_on)
                self.btn_op_trigger_off.clicked.connect(self.on_click_op_trigger_off)

                # camera status monitoring
                _table_camera_status_columns = ["Camera S/N", "Address", "Frames", "Status"]
                self.__table_camera_status_model = QStandardItemModel()
                self.__table_camera_status_model.setColumnCount(len(_table_camera_status_columns))
                self.__table_camera_status_model.setHorizontalHeaderLabels(_table_camera_status_columns)
                self.table_camera_status.setModel(self.__table_camera_status_model)
                #self.table_camera_status.resizeColumnsToContents()

                self.__frame_window_map = {}
                for idx, id in enumerate(config["camera_id"]):
                    self.__frame_window_map[id] = config["camera_window"][idx]

                
        except Exception as e:
            self.__console.critical(f"{e}")
            
        # member variables
        self.__configure = config   # configure parameters

    '''
    camera status table update function
    '''
    def __camera_status_update(self, event):
        # data pipeline for camera status monitoring
        camera_status_pipe_context = zmq.Context()
        camera_status_pipe_socket = camera_status_pipe_context.socket(zmq.SUB)
        camera_status_pipe_socket.setsockopt(zmq.RCVHWM, 100)
        camera_status_pipe_socket.setsockopt(zmq.RCVTIMEO, 1000) # timeout
        camera_status_pipe_socket.setsockopt_string(zmq.SUBSCRIBE, "basler_gige_cam_linker/status")
        camera_status_pipe_socket.connect(f"tcp://{SERVER_IP_ADDRESS}:5556")

        while True:
            # if self.isInterruptionRequested():
            #     break
            try:
                message = camera_status_pipe_socket.recv_string()
                if len(message)>0:
                    parsed_data = json.loads(message)
                    self.__table_camera_status_model.setRowCount(0)
                    for idx, camera in enumerate(parsed_data):
                        self.__table_camera_status_model.appendRow([QStandardItem(camera["sn"]), QStandardItem(camera["ip"]), QStandardItem(str(camera["frames"])),QStandardItem(camera["status"])])
            except json.JSONDecodeError:
                pass
            except zmq.Again: # timeout event
                pass
            
            time.sleep(0.001)
            if event.is_set():
                break
        
    
        camera_status_pipe_socket.close()
        camera_status_pipe_context.term()
        
    # clear all guis
    def clear_all(self):
        try:
            self.__frame_win_defect_plot.clear()

            self.op_trigger_socket.close()
            self.op_trigger_context.term()
            
        except Exception as e:
            self.__console.critical(f"{e}")

    
    '''
    Close event
    '''
    def closeEvent(self, a0: QCloseEvent | None) -> None:
        # self.requestInterruption() # to quit for thread

        self.camera_status_monitor_thread.set()
        self.camera_monitor_thread.set()

        self.camera_status_monitor_thread.join()
        self.camera_monitor_thread.join()

        self.__console.info("Terminated Successfully")
        return super().closeEvent(a0)
    

    def __send_op_trigger_request(self, topic:str, msgdata:dict) -> None:
        try:
            json_data = json.dumps(msgdata)
            self.op_trigger_socket.send_multipart([topic.encode(), json_data.encode()])
        except json.JSONDecodeError as e:
            print(f"json parse error : {e}")
        

    '''
    OP Trigger Manual Control : ON
    '''
    def on_click_op_trigger_on(self):
        msg = {"op_trigger": True }
        self.__send_op_trigger_request("manual_control", msg)
        print("Trigger ON")

    '''
    OP Trigger Manual Control : OFF
    '''
    def on_click_op_trigger_off(self):
        msg = {"op_trigger": False }
        json_data = json.dumps(msg)
        self.__send_op_trigger_request("manual_control", msg)
        print("Trigger OFF")

    
    # camera monitoring thread function
    def __cam_view_monitoring(self, event):
        camera_monitor_context = zmq.Context()
        camera_monitor_socket = camera_monitor_context.socket(zmq.SUB)
        camera_monitor_socket.setsockopt(zmq.RCVHWM, 5000)
        # camera_monitor_socket.setsockopt_string(zmq.SUBSCRIBE, "basler_gige_cam_linker/image_stream_monitor")
        camera_monitor_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        camera_monitor_socket.connect(f"tcp://{SERVER_IP_ADDRESS}:5557")

        while True:
            # if self.isInterruptionRequested():
            #     break

            camera_info = camera_monitor_socket.recv_string()
            try:
                camera = json.loads(camera_info)
                print(f"camera id : {camera["camera_id"]}")
            except json.JSONDecodeError:
                print("json decode error")

                image_recv = camera_monitor_socket.recv()
                np_array = np.frombuffer(image_recv, np.uint8)
                frame = cv2.imdecode(np_array, cv2.IMREAD_GRAYSCALE)
                print(frame.shape)
            # _h, _w, _ch = frame.shape
            # _bpl = _ch*_w # bytes per line
            # print(f"resolution : {_h}, {_w}, {_ch}")
            # qt_image = QImage(frame.data, _w, _h, _bpl, QImage.Format.Format_Grayscale8)
            # pixmap = QPixmap.fromImage(qt_image)

            # draw
            # try:
            #     window = self.findChild(QLabel, self.__frame_window_map[camera_id])
            #     window.setPixmap(pixmap.scaled(window.size(), Qt.AspectRatioMode.KeepAspectRatio))
            # except Exception as e:
            #     self.__console.critical(f"camera {e}")

            time.sleep(0.001)
            if event.is_set():
                break


        camera_monitor_socket.close()
        camera_monitor_context.term()

        