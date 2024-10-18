'''
Steel Surface Defect Detectpr Application Window class
@Author Byunghun Hwang<bh.hwang@iae.re.kr>
'''

import os, sys
import cv2
import pathlib
import nrt

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
        self.__light_controller = None

        # Neurocle parameter setting
        self.base_path = "C://Users/iae/Desktop/Neurocle_model"
        self.model_path = os.path.join(self.base_path, "ano_1.net")
        self.predictor_path = os.path.join(self.base_path, "ano_1.nrpd")
        self.batch_size = 1
        self.fp16_flag = True
        self.threshold_flag = False
        self.device_idx = 0
        self.predictor = self.load_predictor()
        self.inference = True

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
                self.table_camera_list.doubleClicked.connect(self.on_dbclick_camera_list)
                self.btn_inference.clicked.connect(self.on_click_inference)
                
                # serial for light control
                for idx, ch in enumerate(config["light_channel"]):
                    label_light = self.findChild(QLabel, f"label_light_ch{idx+1}")
                    label_light.setText(f"Ch. {ch}")
                
                # serial port
                edit_port = self.findChild(QLineEdit, "edit_light_port")
                edit_port.setText(config["light_default_port"])
                self.btn_light_connect.clicked.connect(self.on_click_light_connect)
                self.btn_light_disconnect.clicked.connect(self.on_click_light_disconnect)
                
                # sereial baudrate
                edit_baud = self.findChild(QLineEdit, "edit_light_baudrate")
                edit_baud.setText(str(config["light_default_baudrate"]))
                
                # slider
                for idx, ch in enumerate(config["light_channel"]):
                    slider = self.findChild(QSlider, f"slide_ch{idx+1}")
                    slider.setValue(0)
                    label_light_value = self.findChild(QLabel, f"label_value_slide_ch{idx+1}")
                    label_light_value.setText(f"{slider.value()}")

                    slider.sliderReleased.connect(self.on_released_slider_value)
                    slider.valueChanged.connect(self.on_changed_slider_value)
                
                self.__model_selection = self.findChild(QComboBox, name="cmbbox_inference_model")
                self.__model_selection.currentIndexChanged.connect(self.on_changed_model_selection_index)
                self.__model_selection.addItems(["luxteel defect binary class", "luxteel defect multi class"])
                
                # define camera list table model
                _talbe_camera_columns = ["ID", "Camera Name", "Address"]
                self.__table_camlist_model = QStandardItemModel()
                self.__table_camlist_model.setColumnCount(len(_talbe_camera_columns))
                self.__table_camlist_model.setHorizontalHeaderLabels(_talbe_camera_columns)
                self.table_camera_list.setModel(self.__table_camlist_model)
                self.table_camera_list.resizeColumnsToContents()
                
                # frame window mapping
                self.__frame_window_map = {}
                for idx, id in enumerate(config["camera_id"]):
                    self.__frame_window_map[id] = config["camera_window"][idx]
                    self.__image_recorder[id] = image_writer(prefix=str(f"camera_{id}"), save_path=(config["app_path"] / config["image_out_path"]))
                    self.__image_recorder[id].start()
                    
                
                
                # apply monitoring
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
            self.__console.critical(f"{e}")
        
        # member variables
        self.__configure = config   # configure parameters
        self.__sdd_model_container = {}   # SDD classification model container
        self.__camera_container = {}
        self.__recorder_container = {}
        
        self.__camera:GigEMultiCameraController = None # camera device controller
        #self.__recorder:VideoRecorder = None # video recorder
        
        # find GigE Cameras & update camera list
        __cam_found = gige_camera_discovery()
        self.__update_camera_list(__cam_found)

    # Create Predictor or Load Predictor (1 Time)
    def load_predictor(self):
        if self.device_idx >= 0 and os.path.isfile(self.predictor_path):
            print("Load the Predictor using the previously optimized Predictor file.")
            predictor = nrt.Predictor(self.device_idx, self.predictor_path)
        else:
            print(
                "Optimizing the Predictor for the Model and Device... It may take a few minutes."
            )
            # The default device setting for the Predictor is CPU(-1).
            # If you want more diverse options, you can use it as shown in the comment below.
            # predictor = nrt.Predictor(model_path)
            predictor = nrt.Predictor(
                self.model_path,
                nrt.Model.MODELIO_OUT_CAM,
                self.device_idx,
                self.batch_size,
                self.fp16_flag,
                self.threshold_flag,
            )

            # Save the predictor information optimized for this device,
            # so if the same model is used in the same device environment later, the optimized predictor can be reused.
            if self.device_idx >= 0:
                print("Save the information of the optimized Prediuctor to a file(.nrpd)")
                status = predictor.save_predictor(self.predictor_path)
                if status != nrt.STATUS_SUCCESS:
                    raise Exception(
                        "Model initialization failed. : " + nrt.get_last_error_msg()
                    )
        if predictor.get_status() != nrt.STATUS_SUCCESS:
            raise Exception("Predictor save failed. : " + nrt.get_last_error_msg())
        print("Predictor initialization complete...\n")

        return predictor
    
    '''
    slider changed event
    '''
    def on_changed_slider_value(self):
        slider = self.sender()
        label_light_value = self.findChild(QLabel, f"label_value_{slider.objectName()}")
        label_light_value.setText(f"{slider.value()}")
    
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
            dmx_data =  [0]*1+[int(ch1)]*1+ \
                        [0]*3+[int(ch5)]*1+ \
                        [0]*3+[int(ch9)]*1+ \
                        [0]*3+[int(ch13)]*1+[0]*2
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
        self.cameras = GigEMultiCameraController()
        
        # recorder
        '''
        for id in range(self.cameras.get_num_camera()):
            self.__recorder_container[id] = VideoRecorder(dirpath=(self.__configure["app_path"] / self.__configure["video_out_path"]), 
                                                              filename=f"camera_{id}",
                                                              ext=self.__configure["video_extension"],
                                                              resolution=(int(self.__configure["camera_width"]), int(self.__configure["camera_height"])),
                                                              fps=float(self.__configure["camera_fps"]))
        '''
        
        self.cameras.frame_update_signal.connect(self.show_updated_frame) # connect to frame grab signal
        #self.cameras.frame_update_signal.connect(self.write_frame)
        #self.cameras.frame_write_signal.connect(self.write_frame) # connect to frame write
        self.cameras.begin_thread()
    
    # click event callback function
    def on_click_inference(self):
        selected_model = self.__model_selection.currentText()
        _label_result = self.findChild(QLabel, "label_inference_result")
        
    
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
    
    # model selection
    def on_changed_model_selection_index(self, index):
        try:
            model = self.__model_selection.currentText()
            self.__console.info(f"Selected Model : {model}")
        except Exception as e:
            self.__console.critical(f"{e}")
    
    # re-discover cameras
    def on_click_camera_discovery(self):
        # clear camera table
        self.__table_camlist_model.setRowCount(0)
        
        # find & update
        __cam_found = gige_camera_discovery()
        self.__update_camera_list(__cam_found)
        
    # double clicked on camera list
    def on_dbclick_camera_list(self):
        row = self.table_camera_list.currentIndex().row()
        col = self.table_camera_list.currentIndex().column()
        
        # get camera id from tableview
        id = self.__table_camlist_model.index(row, 0).data()
        
        self.__console.info(f"Selected camera ID : {id}")
        
        # if camera is working, close it
        if self.__camera!=None:
            self.__camera.close()
        
        # set camera controller with id
        self.__camera = GigEMultiCameraController(id)
        if self.__camera.open():
            self.__camera.frame_update_signal.connect(self.show_updated_frame)
            self.__camera.begin()
        else:
            self.__camera.close()
            self.__camera = None
            QMessageBox.warning(self, "Camera open failed", "Failed to open camera device")
            

    # show message on status bar
    def show_on_statusbar(self, text):
        self.statusBar().showMessage(text)

    # write frame
    def write_frame(self, id:int, image:np.ndarray, fps:float):
        #rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        self.__recorder_container[id].write_frame(image, fps)
        
    # show updated image frame on GUI window
    def show_updated_frame(self, id:int, image:np.ndarray, fps:float):

        # converting color format
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        if self.inference:
        
            # Neurocle code
            ######################################################################################################
            # Input images
            inputs = nrt.Input()
            image_buff = nrt.NDBuffer.from_numpy(rgb_image)
            status = inputs.extend(image_buff)
            if status != nrt.STATUS_SUCCESS:
                raise Exception("Extend the input failed. : " + nrt.get_last_error_msg())
            
            # If the inputs have reached the batch size, start the prediction.
            start = time.time()
            results = self.predictor.predict(inputs)
            end = time.time()
            if results.get_status() != nrt.STATUS_SUCCESS:
                raise Exception("Predict failed. : " + nrt.get_last_error_msg())
            # print(
            #     f"duration per batch ({self.batch_size} images) : {round((end - start) * 1000, 2)} ms"
            # )
            inputs.clear()

            #cv2.imwrite(f"camera_{id}_{self.__write_counter}.png", rgb_image)
            #self.__write_counter = self.__write_counter+1
            
            # draw information
            t_start = datetime.now()
            # id = self.sender().get_camera_id()
            
            # Classification results(CAM)
            for i in range(results.classes.get_count()):
                cla = results.classes.get(i)
                class_name = self.predictor.get_class_name(cla.idx)
                score = results.probs.get(i, 0)
                #print(f"class name : {class_name} | probability : {round(score,2)}")

                if class_name =="Anomaly":
                    self.__image_recorder[id].save("NG", image)
                else:
                    self.__image_recorder[id].save("Good", image)

                # if not results.cams.empty():
                #     alpha = 0.3
                #     cam = results.cams.get(i)
                #     mat_cam = cam.cam_to_numpy()
                #     mat_cam = mat_cam.reshape([cam.get_height(), cam.get_width(), 3])
                #     mat_cam = cv2.applyColorMap(mat_cam, cv2.COLORMAP_JET)
                #     cv2.addWeighted(rgb_image, alpha, mat_cam, 1-alpha, 0, rgb_image)
                cv2.putText(rgb_image, f"Camera #{id}(fps:{int(fps)})", (10,50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,255,0), 2, cv2.LINE_AA)
                cv2.putText(rgb_image, t_start.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3], (10, 1070), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,255,0), 2, cv2.LINE_AA)
                if class_name == "Anomaly":
                    cv2.putText(rgb_image, "NG", (900, 50), cv2.FONT_HERSHEY_SIMPLEX, 2.5, (255,0,0), 2, cv2.LINE_AA)
                else:
                    cv2.putText(rgb_image, "Good", (900, 50), cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0,255,0), 2, cv2.LINE_AA)
            #############################################################################################
                
        # self.__console.info(f"{id}")
        
        #converting ndarray to qt image
        _h, _w, _ch = rgb_image.shape
        _bpl = _ch*_w # bytes per line
        #qt_image = QImage(rgb_cam_image.data, _w, _h, _bpl, QImage.Format.Format_RGB888) # CAM image
        qt_image = QImage(rgb_image.data, _w, _h, _bpl, QImage.Format.Format_RGB888)  # original image

        # converting qt image to QPixmap
        pixmap = QPixmap.fromImage(qt_image)

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

        if self.cameras.get_num_camera()>0:
            self.cameras.close() # multi camera controller closed

        # image recoder stop
        for idx in self.__image_recorder:
            self.__image_recorder[idx].terminate()
        
        # camera close
        for camera in self.__camera_container.values():
            camera.close()
        
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
        
        