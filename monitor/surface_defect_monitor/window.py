'''
Steel Surface Defect Detectpr Application Window class
@Author Byunghun Hwang<bh.hwang@iae.re.kr>
'''

import os, sys
import cv2
import pathlib

try:
    # using PyQt5
    from PyQt5.QtGui import QImage, QPixmap, QCloseEvent, QStandardItem, QStandardItemModel
    from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QMessageBox, QProgressBar, QFileDialog, QComboBox, QLineEdit, QSlider
    from PyQt5.uic import loadUi
    from PyQt5.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
except ImportError:
    # using PyQt6
    from PyQt6.QtGui import QImage, QPixmap, QCloseEvent, QStandardItem, QStandardItemModel
    from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QMessageBox, QProgressBar, QFileDialog, QComboBox, QLineEdit, QSlider
    from PyQt6.uic import loadUi
    from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
    
import numpy as np
from datetime import datetime

from vision.camera.multi_gige import Controller as GigEMultiCameraController
from vision.camera.multi_gige import gige_camera_discovery
from util.logger.video import VideoRecorder
from util.monitor.system import SystemStatusMonitor
from util.monitor.gpu import GPUStatusMonitor
from util.logger.console import ConsoleLogger
from vision.SDD.ResNet import ResNet9 as SDDModel

# for TransUNET Segmentaiton
import torch
from vision.SDD.TransUNET_Seg.inference import SegInference


import threading
import queue
import time
import serial

'''
Main window
'''

class image_writer(threading.Thread):
    def __init__(self, prefix:str, save_path:pathlib.Path):
        super().__init__()

        self.initial_save_path = save_path
        self.current_save_path = save_path
        self.prefix = prefix
        self.queue = queue.Queue()
        self.stop_event = threading.Event()

        self.__is_running = False
    
    def save(self, class_name:str, image:np.ndarray):
        if self.__is_running:
            postfix = datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')[:23]

            self.image_out_path_current = self.image_out_path / self.prefix / pathlib.Path(f"{class_name}")
            self.image_out_path_current.mkdir(parents=True, exist_ok=True)

            self.current_save_path = pathlib.Path(f"{self.image_out_path_current}") / pathlib.Path(f"{postfix}.jpg")
            self.queue.put(image)


    def run(self):
        while not self.stop_event.is_set():
            if not self.queue.empty():
                image_data = self.queue.get()
                cv2.imwrite(self.current_save_path.as_posix(), image_data)
            time.sleep(0.001)

    def begin(self):
        # create directory
        record_start_datetime = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        self.image_out_path = self.initial_save_path / record_start_datetime
        self.image_out_path.mkdir(parents=True, exist_ok=True)

        self.__is_running = True

    def stop(self):
        self.__is_running = False

    def terminate(self):
        self.stop_event.set()


class AppWindow(QMainWindow):
    def __init__(self, config:dict):
        super().__init__()
        
        self.__console = ConsoleLogger.get_logger()
        self.__image_recorder = {}
        self.__light_controller = None # light controller
        self.__camera_controller = None # camera array controller
        self.__configure = config   # save configure parameters
        self.__sdd_model_container = {}   # SDD classification model container
        self.__camera_container = {}
        self.__recorder_container = {}
        self.__table_camlist_model = None # camera table model

        self.__model_dir = pathlib.Path(__file__).parent / "model"
        self.__sdd_model:SegInference = None
        self.__do_inference = False

        try:            
            if "gui" in config:
                
                # load gui file
                ui_path = pathlib.Path(config["app_path"]) / config["gui"]
                if os.path.isfile(ui_path):
                    loadUi(ui_path, self)
                else:
                    raise Exception(f"Cannot found UI file : {ui_path}")
                
                # menu event callback function connection
                self.actionOpen.triggered.connect(self.on_select_camera_open)
                self.actionDiscovery.triggered.connect(self.on_select_camera_discovery)
                self.actionStartStopDataRecording.triggered.connect(self.on_select_start_stop_data_recording)
                self.actionCapture_to_Image_png.triggered.connect(self.on_select_capture_image)
                
                # GUI component event callback function connection
                self.btn_camera_discovery.clicked.connect(self.on_click_camera_discovery)
                self.btn_inference.clicked.connect(self.on_click_inference)
                self.btn_model_load.clicked.connect(self.on_click_model_load)
                
                # update light control gui from configuration file
                for idx, ch in enumerate(config["light_channel"]):
                    label_light = self.findChild(QLabel, f"label_light_ch{idx+1}")
                    label_light.setText(f"Ch. {ch}")
                
                # update serial port and baudrate for light control from configuration file
                edit_port = self.findChild(QLineEdit, "edit_light_port")
                edit_port.setText(config["light_default_port"])
                edit_baud = self.findChild(QLineEdit, "edit_light_baudrate")
                edit_baud.setText(str(config["light_default_baudrate"]))
                self.btn_light_connect.clicked.connect(self.on_click_light_connect)
                self.btn_light_disconnect.clicked.connect(self.on_click_light_disconnect)
                
                # image cache slider setting with default value
                cache_slider = self.findChild(QSlider, "slide_image_cache")
                cache_slider_pos = self.findChild(QLabel, "label_image_cache_pos")
                cache_slider_num = self.findChild(QLabel, "label_image_cache_num")
                cache_slider.setValue(0)
                cache_slider_pos.setText("0")
                cache_slider_num.setText("0")
                
                # external trigger control
                # edit_trigger_freq
                # edit_trigger_count
                # btn_start_capture_trigger
                
                
                
                # update slider gui component for light control
                for idx, ch in enumerate(config["light_channel"]):
                    slider = self.findChild(QSlider, f"slide_ch{idx+1}")
                    slider.setValue(0)
                    label_light_value = self.findChild(QLabel, f"label_value_slide_ch{idx+1}")
                    label_light_value.setText(f"{slider.value()}")

                    slider.sliderReleased.connect(self.on_released_slider_value)
                    slider.valueChanged.connect(self.on_changed_slider_value)

                ui_model_dropdown = self.findChild(QComboBox, name="cmbbox_inference_model")
                if len(config["sdd_model_name"]) == len(config["sdd_model"]) and len(config["sdd_model_name"])>0 and len(config["sdd_model"]):
                    for idx, modelname in enumerate(config["sdd_model_name"]):
                        ui_model_dropdown.addItems(config["sdd_model_name"])
                        self.__sdd_model_container[modelname] = config["sdd_model"][idx]
                
                # frame window mapping
                self.__frame_window_map = {}
                for idx, id in enumerate(config["camera_id"]):
                    self.__frame_window_map[id] = config["camera_window"][idx]
                    self.__image_recorder[id] = image_writer(prefix=str(f"camera_{id}"), save_path=(config["app_path"] / config["image_out_path"]))
                    self.__image_recorder[id].start()

                # for inference with SDD Model
                self.__accel_device = 'cpu:0'
                if torch.cuda.is_available():
                    self.__accel_device = 'cuda:0'
                print(f"Selected inference Acceleration : {self.__accel_device}")
                
                
                # apply monitoring
                # bad performance!!
                '''
                self.__sys_monitor = SystemStatusMonitor(interval_ms=1000)
                self.__sys_monitor.usage_update_signal.connect(self.update_system_status)
                self.__sys_monitor.start()
                
                # apply gpu monitoring
                try:
                    self.__gpu_monitor = GPUStatusMonitor(interval_ms=1000)
                    self.__gpu_monitor.usage_update_signal.connect(self.update_gpu_status)
                    self.__gpu_monitor.start()
                except Exception as e:
                    self.__console.critical("GPU may not be available")
                    pass
                '''
                
            else:
                raise Exception("GUI definition must be contained in the configuration file.")

        except Exception as e:
            self.__console.critical(f"Load config error : {e}")

        
        self.__camera:GigEMultiCameraController = None # camera device controller (remove)
        self.__camera_controller:GigEMultiCameraController = None # camera device controller
        self.__recorder:VideoRecorder = None # video recorder
        
        # find GigE Cameras & update camera list
        __cam_found = gige_camera_discovery()

        # update camera list 
        _table_camera_columns = ["ID", "Camera Name", "Address"]
        self.__table_camlist_model = QStandardItemModel()
        self.__table_camlist_model.setColumnCount(len(_table_camera_columns))
        self.__table_camlist_model.setHorizontalHeaderLabels(_table_camera_columns)
        self.table_camera_list.setModel(self.__table_camlist_model)
        self.table_camera_list.resizeColumnsToContents()

        self.__update_camera_list(__cam_found)

    '''
    slider changed event
    '''
    def on_changed_slider_value(self):
        slider = self.sender()
        label_light_value = self.findChild(QLabel, f"label_value_{slider.objectName()}")
        label_light_value.setText(f"{slider.value()}")
        
    '''
    slider release event
    '''
    def on_released_slider_value2(self):
        slider = self.sender()
        self.__console.info(f"{slider.value()}")
        
        if self.__light_controller != None:
            dmx_data =  [0]*3+[int(slider.value())]*1+[0]*2
            dmx_length = len(dmx_data) + 1
            data_length_lsb = dmx_length & 0xFF  # 데이터 길이 LSB
            data_length_msb = (dmx_length >> 8) & 0xFF  # 데이터 길이 
            message = [0x7E, 6, data_length_lsb, data_length_msb, 0] + dmx_data + [0xE7]
            self.__light_controller.write(bytearray(message))
    
    '''
    slider relased event
    '''
    def on_released_slider_value(self):
        slider = self.sender()
        self.__console.info(f"{slider.value()}")
        
        if self.__light_controller != None:
            start_code = 0x7E
            label = 6  # Output Only Send DMX Packet Request
            end_code = 0xE7
            Num=slider.value()
            ch1=Num
            ch5=Num
            ch9=Num
            ch13=Num
            ch17=Num
            ch21=Num
            dmx_data =  [0]*1+[int(ch1)]*1+ \
                        [0]*3+[int(ch5)]*1+ \
                        [0]*3+[int(ch9)]*1+ \
                        [0]*3+[int(ch13)]*1+ \
                        [0]*3+[int(ch17)]*1+ \
                        [0]*3+[int(ch21)]*1+[0]*2
            dmx_length = len(dmx_data) + 1  # DMX 데이터 길이 + 1 (스타트 코드 포함)
            data_length_lsb = dmx_length & 0xFF  # 데이터 길이 LSB
            data_length_msb = (dmx_length >> 8) & 0xFF  # 데이터 길이 

            message = [start_code, label, data_length_lsb, data_length_msb, 0] + dmx_data + [end_code]
            self.__light_controller.write(bytearray(message))
        
    '''
    light control
    '''
    def on_click_light_connect(self):
        edit_port = self.findChild(QLineEdit, "edit_light_port")
        edit_baud = self.findChild(QLineEdit, "edit_light_baudrate")
        
        if self.__light_controller == None:
            self.__light_controller = serial.Serial(port=edit_port.text(), baudrate=int(edit_baud.text()))
            if self.__light_controller.is_open:
                self.btn_light_connect.setEnabled(False)
                self.btn_light_disconnect.setEnabled(True)
    
    def on_click_light_disconnect(self):
        if self.__light_controller.is_open:
            self.__light_controller.close()
            self.btn_light_connect.setEnabled(True)
            self.btn_light_disconnect.setEnabled(False)

    '''
    Private Member functions
    '''    
    def __update_camera_list(self, cameras:list):
        label_n_cam = self.findChild(QLabel, "label_num_camera")
        label_n_cam.setText(str(len(cameras)))
        
        # clear tableview
        self.__table_camlist_model.setRowCount(0)
        
        # add row
        for idx, (id, name, address) in enumerate(cameras):
            self.__table_camlist_model.appendRow([QStandardItem(str(id)), QStandardItem(str(name)), QStandardItem(str(address))])
        self.table_camera_list.resizeColumnsToContents()
        
    '''
    GUI Event Callback functions
    '''
    # selected camera to open
    def on_select_camera_open(self):
        
        # create camera instance
        try:
            if self.__camera_controller is None:
                self.__camera_controller = GigEMultiCameraController()
                self.__camera_controller.frame_update_signal.connect(self.show_updated_frame) # connect to frame grab signal
                self.__camera_controller.frame_update_signal_multi.connect(self.show_updated_frame_multi) # connect to multi frame
                self.__camera_controller.start_grab()
        except Exception as e:
            self.__console.critical(f"Camera controller cannot be open. It may already be opened.")
        
        # recorder
        '''
        for id in range(self.cameras.get_num_camera()):
            self.__recorder_container[id] = VideoRecorder(dirpath=(self.__configure["app_path"] / self.__configure["video_out_path"]), 
                                                              filename=f"camera_{id}",
                                                              ext=self.__configure["video_extension"],
                                                              resolution=(int(self.__configure["camera_width"]), int(self.__configure["camera_height"])),
                                                              fps=float(self.__configure["camera_fps"]))
        '''
    
    # click event callback function
    def on_click_inference(self):
        
        if self.__sdd_model != None:
            self.__do_inference = True

        

        # single process with selected model in thread
        # code here

        #_label_result = self.findChild(QLabel, "label_inference_result")
        
    '''
    inference model load
    '''
    def on_click_model_load(self):
        ui_model_dropdown = self.findChild(QComboBox, name="cmbbox_inference_model")
        selected = ui_model_dropdown.currentText()
        print(f"selected : {selected}")
        #print(f"selected model file : {self.__sdd_model_container[selected]}")
        abs_path = self.__model_dir / self.__sdd_model_container[selected]
        print(f"load model path : {abs_path.as_posix()}")

        self.__sdd_model = SegInference(model_path=abs_path.as_posix() ,device=self.__accel_device)
        
    
    # re-discover all gige network camera
    def on_select_camera_discovery(self):
        __cam_found = gige_camera_discovery()
        self.__update_camera_list(__cam_found)
    
    # data recording
    def on_select_start_stop_data_recording(self):
        if self.sender().isChecked(): #start recording
            for recorder in self.__image_recorder.values():
                recorder.begin() # image recording
                self.__console.info("Start image writing...")
            # video recording
            #for recorder in self.__recorder_container.values():
            #    recorder.start()
        else:   # stop recording
            for recorder in self.__image_recorder.values():
                recorder.stop() # image recording
                self.__console.info("Stop image writing...")

            #for recorder in self.__recorder_container.values():
            #    recorder.stop()
    
    # start image capture
    def on_select_capture_image(self):
        pass
    
    # re-discover cameras
    def on_click_camera_discovery(self):
        # clear camera table
        self.__table_camlist_model.setRowCount(0)
        
        # find & update
        __cam_found = gige_camera_discovery()
        self.__update_camera_list(__cam_found)
            

    # show message on status bar
    def show_on_statusbar(self, text):
        self.statusBar().showMessage(text)

    # write frame
    def write_frame(self, id:int, image:np.ndarray, fps:float):
        #rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        self.__recorder_container[id].write_frame(image, fps)
    
    # show updated multi image frame on GIO window
    def show_updated_frame_multi(self, id:int, images:dict, fps:float):
        t_start = datetime.now()

        perf_count = 0
        for idx, key in enumerate(images):
            perf_count = perf_count+1
            rgb_image = cv2.cvtColor(images[key], cv2.COLOR_BGR2RGB)
            rgb_image = cv2.resize(rgb_image, dsize=(480, 300), interpolation=cv2.INTER_AREA)

            ## SDD inference
            if self.__do_inference and self.__sdd_model!=None:
                pred_mask = self.__sdd_model.infer_image(rgb_image)
                pred_mask = pred_mask * 255
                pred_mask = pred_mask.astype(np.uint8)
                #pred_mask_squeezed = np.squeeze(pred_mask).reshape(640,640,1) # check dimension
                pred_mask_squeezed = pred_mask.reshape(640,640,1) # check dimension
                pred_mask_color = cv2.cvtColor(pred_mask_squeezed, cv2.COLOR_GRAY2RGB)
                mask_rgb_image = cv2.resize(pred_mask_color, dsize=(480, 300), interpolation=cv2.INTER_AREA)

                # mask
                lower_white = np.array([10, 10, 10], dtype=np.uint8)
                upper_white = np.array([250, 250, 250], dtype=np.uint8)
                mask = cv2.inRange(mask_rgb_image, lower_white, upper_white)
                mask_rgb_image[mask!=0] = [255, 0, 0]

                rgb_image = cv2.addWeighted(rgb_image, 0.5, mask_rgb_image, 0.5, 0)
        
            cv2.putText(rgb_image, f"Camera #{id}(fps:{int(fps)})", (10,50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1, cv2.LINE_AA)
            cv2.putText(rgb_image, t_start.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3], (10, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1, cv2.LINE_AA)

            #converting ndarray to qt image
            _h, _w, _ch = rgb_image.shape
            # print("Output image shape : {_h},{_w},{_ch}")
            _bpl = _ch*_w # bytes per line
            #qt_image = QImage(rgb_cam_image.data, _w, _h, _bpl, QImage.Format.Format_RGB888) # CAM image
            qt_image = QImage(rgb_image.data, _w, _h, _bpl, QImage.Format.Format_RGB888)  # original image

            # converting qt image to QPixmap
            pixmap = QPixmap.fromImage(qt_image)

            # draw on window
            try:
                window = self.findChild(QLabel, self.__frame_window_map[key])
                window.setPixmap(pixmap.scaled(window.size(), Qt.AspectRatioMode.KeepAspectRatio))
                window.repaint()
            except Exception as e:
                self.__console.critical(f"camera {e}")
    
        self.__console.info("processed")
        #self.__do_inference = False
        

    # show updated image frame on GUI window
    def show_updated_frame(self, id:int, image:np.ndarray, fps:float):

        t_start = datetime.now()
        start_time = time.perf_counter()

        # converting color format
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        rgb_image = cv2.resize(rgb_image, dsize=(480, 300), interpolation=cv2.INTER_AREA)
        

        ## SDD inference
        if self.__do_inference and self.__sdd_model!=None:
            pred_mask = self.__sdd_model.infer_image(rgb_image)
            pred_mask = pred_mask * 255
            pred_mask = pred_mask.astype(np.uint8)
            #pred_mask_squeezed = np.squeeze(pred_mask).reshape(640,640,1) # check dimension
            pred_mask_squeezed = pred_mask.reshape(640,640,1) # check dimension
            pred_mask_color = cv2.cvtColor(pred_mask_squeezed, cv2.COLOR_GRAY2RGB)
            mask_rgb_image = cv2.resize(pred_mask_color, dsize=(480, 300), interpolation=cv2.INTER_AREA)

            # mask
            lower_white = np.array([10, 10, 10], dtype=np.uint8)
            upper_white = np.array([250, 250, 250], dtype=np.uint8)
            mask = cv2.inRange(mask_rgb_image, lower_white, upper_white)
            mask_rgb_image[mask!=0] = [255, 0, 0]

            rgb_image = cv2.addWeighted(rgb_image, 0.5, mask_rgb_image, 0.5, 0)


        cv2.putText(rgb_image, f"Camera #{id}(fps:{int(fps)})", (10,50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1, cv2.LINE_AA)
        cv2.putText(rgb_image, t_start.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3], (10, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1, cv2.LINE_AA)
        
        #converting ndarray to qt image
        _h, _w, _ch = rgb_image.shape
        # print("Output image shape : {_h},{_w},{_ch}")
        _bpl = _ch*_w # bytes per line
        #qt_image = QImage(rgb_cam_image.data, _w, _h, _bpl, QImage.Format.Format_RGB888) # CAM image
        qt_image = QImage(rgb_image.data, _w, _h, _bpl, QImage.Format.Format_RGB888)  # original image

        # converting qt image to QPixmap
        pixmap = QPixmap.fromImage(qt_image)

        # check performance
        end_time = time.perf_counter()
        elapsed_time = (end_time - start_time) * 1000
        formatted_time = "{:.2f}".format(elapsed_time)
        print(f"Process took {formatted_time} milliseconds")

        self.__do_inference = False

        # draw on window
        try:
            window = self.findChild(QLabel, self.__frame_window_map[id])
            window.setPixmap(pixmap.scaled(window.size(), Qt.AspectRatioMode.KeepAspectRatio))
        except Exception as e:
            self.__console.critical(f"camera {e}")
        
        
    # close event callback function by user
    def closeEvent(self, a0: QCloseEvent) -> None:
        
        # recorder stop
        for rec in self.__recorder_container.values():
            rec.stop()

        # remove camera controller
        if self.__camera_controller:
            if self.__camera_controller.get_num_camera()>0:
                self.__camera_controller.close()

        # image recoder stop
        for idx in self.__image_recorder:
            self.__image_recorder[idx].terminate()
        
        # close monitoring thread
        try:
            pass
            #self.__sys_monitor.close()
            #self.__gpu_monitor.close()
        except AttributeError as e:
            self.__console.critical(f"{e}")
            
        self.__console.info("Terminated Successfully")
        
        return super().closeEvent(a0)    
    
    # show update system monitoring on GUI window
    def update_system_status(self, status:dict):
        cpu_usage_window = self.findChild(QProgressBar, "progress_cpu_usage")
        mem_usage_window = self.findChild(QProgressBar, "progress_mem_usage")
        storage_usage_window = self.findChild(QProgressBar, "progress_storage_usage")
        cpu_usage_window.setValue(int(status["cpu"]))
        mem_usage_window.setValue(int(status["memory"]))
        storage_usage_window.setValue(int(status["storage"]))
        
    # show update gpu monitoring on GUI window
    def update_gpu_status(self, status:dict):
        if "gpu_count" in status:
            if status["gpu_count"]>0:
                gpu_usage_window = self.findChild(QProgressBar, "progress_gpu_usage")
                gpu_mem_usage_window = self.findChild(QProgressBar, "progress_gpu_mem_usage")
                gpu_usage_window.setValue(int(status["gpu_0"]))
                gpu_mem_usage_window.setValue(int(status["memory_0"]))
        
        