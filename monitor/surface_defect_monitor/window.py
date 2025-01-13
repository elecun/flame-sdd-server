'''
Steel Surface Defect Detectpr Application Window class
@Author Byunghun Hwang<bh.hwang@iae.re.kr>
'''

import os, sys
import cv2
import pathlib
import threading
import queue
import time
import numpy as np
from datetime import datetime
import pyqtgraph as graph
import random
import zmq
import zmq.asyncio
import json
import cv2
from functools import partial

try:
    # using PyQt5
    from PyQt5.QtGui import QImage, QPixmap, QCloseEvent, QStandardItem, QStandardItemModel
    from PyQt5.QtWidgets import QApplication, QFrame, QMainWindow, QLabel, QPushButton, QMessageBox
    from PyQt5.QtWidget import QProgressBar, QFileDialog, QComboBox, QLineEdit, QSlider, QCheckBox
    from PyQt5.uic import loadUi
    from PyQt5.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
except ImportError:
    # using PyQt6
    from PyQt6.QtGui import QImage, QPixmap, QCloseEvent, QStandardItem, QStandardItemModel
    from PyQt6.QtWidgets import QApplication, QFrame, QMainWindow, QLabel, QPushButton, QCheckBox
    from PyQt6.QtWidgets import QMessageBox, QProgressBar, QFileDialog, QComboBox, QLineEdit, QSlider, QVBoxLayout
    from PyQt6.uic import loadUi
    from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
    
from util.logger.console import ConsoleLogger
from . import trigger
from . import light
from subscriber.temperature import TemperatureMonitorSubscriber
from requester.lens_control import LensControlRequester
from requester.light_control import LightControlRequester
#from requester.trigger_control import TriggerControlRequester
from requester.pulse_generator import PulseGeneratorRequester
from subscriber.camera import CameraMonitorSubscriber


'''
Main window
'''

class AppWindow(QMainWindow):
    def __init__(self, config:dict):
        """ initialization """
        super().__init__()
        
        self.__console = ConsoleLogger.get_logger() # logger
        self.__config = config  # copy configuration data

        self.__frame_defect_grid_layout = QVBoxLayout()
        self.__frame_defect_grid_plot = graph.PlotWidget()

        try:            
            if "gui" in config:

                # load gui file
                ui_path = pathlib.Path(config["app_path"]) / config["gui"]
                if os.path.isfile(ui_path):
                    loadUi(ui_path, self)
                else:
                    raise Exception(f"Cannot found UI file : {ui_path}")
                
                # defect graphic view frame
                self.__frame_defect_grid_frame = self.findChild(QFrame, name="frame_defect_grid_frame")
                self.__frame_defect_grid_layout.addWidget(self.__frame_defect_grid_plot)
                self.__frame_defect_grid_layout.setContentsMargins(0, 0, 0, 0)
                self.__frame_defect_grid_plot.setBackground('w')
                self.__frame_defect_grid_plot.showGrid(x=True, y=True)
                self.__frame_defect_grid_plot.setLimits(xMin=0, xMax=10000, yMin=0, yMax=11)
                self.__frame_defect_grid_plot.setRange(yRange=(0,10), xRange=(0,100))
                self.__frame_defect_grid_plot.setMouseEnabled(x=True, y=False)
                self.__frame_defect_grid_frame.setLayout(self.__frame_defect_grid_layout)

                # grid plot style
                #self.__frame_defect_grid_plot.setTitle(f"Defect Visualization", color="k", size="25pt")
                styles = {"color": "#000", "font-size": "15px"}
                self.__frame_defect_grid_plot.setLabel("left", "Camera Channels", **styles)
                self.__frame_defect_grid_plot.setLabel("bottom", "Frame Counts", **styles)
                self.__frame_defect_grid_plot.addLegend()
                
                # register button event callback function
                self.btn_trigger_start.clicked.connect(self.on_btn_trigger_start)
                self.btn_trigger_stop.clicked.connect(self.on_btn_trigger_stop)
                self.btn_light_control_set.clicked.connect(self.on_btn_light_control_set)
                self.btn_light_control_off.clicked.connect(self.on_btn_light_control_off)
                self.btn_focus_set_1.clicked.connect(partial(self.on_btn_focus_set, 1))
                self.btn_focus_set_2.clicked.connect(partial(self.on_btn_focus_set, 2))
                self.btn_focus_set_3.clicked.connect(partial(self.on_btn_focus_set, 3))
                self.btn_focus_set_4.clicked.connect(partial(self.on_btn_focus_set, 4))
                self.btn_focus_set_5.clicked.connect(partial(self.on_btn_focus_set, 5))
                self.btn_focus_set_6.clicked.connect(partial(self.on_btn_focus_set, 6))
                self.btn_focus_set_7.clicked.connect(partial(self.on_btn_focus_set, 7))
                self.btn_focus_set_8.clicked.connect(partial(self.on_btn_focus_set, 8))
                self.btn_focus_set_9.clicked.connect(partial(self.on_btn_focus_set, 9))
                self.btn_focus_set_10.clicked.connect(partial(self.on_btn_focus_set, 10))
                self.btn_focus_read_all.clicked.connect(self.on_btn_focus_read_all)
                self.btn_defect_visualization_test.clicked.connect(self.on_btn_defect_visualization_test)
                self.btn_camera_view_test.clicked.connect(self.on_btn_camera_view_test)

                # register dial event callback function
                self.dial_light_control.valueChanged.connect(self.on_change_light_control)

                # create temperature monitoring subscriber
                self.__temp_monitor_subscriber = None
                if "temp_stream_source" in config and "temp_stream_topic" in config:
                    self.__console.info("+ Create Temperature Monitoring Subscriber...")
                    self.__temp_monitor_subscriber = TemperatureMonitorSubscriber(connection=config["temp_stream_source"], topic=config["temp_stream_topic"])
                    self.__temp_monitor_subscriber.temperature_update_signal.connect(self.on_update_temperature)
                    self.__temp_monitor_subscriber.start() # run in thread

                self.__lens_control_requester = None
                if "lens_control_source" in config:
                    self.__console.info("+ Create Lens Control Requester...")
                    self.__lens_control_requester = LensControlRequester(connection=config["lens_control_source"])
                    self.__lens_control_requester.focus_read_update_signal.connect(self.on_update_focus)

                self.__light_control_requester = None
                if "light_control_source" in config:
                    self.__console.info("+ Create Light Control Requester")
                    self.__light_control_requester = LightControlRequester(connection=config["light_control_source"])

                self.__pulse_generator_requester = None
                if "trigger_control_source":
                    self.__console.info("+ Create Trigger Control Requester")
                    self.__pulse_generator_requester = PulseGeneratorRequester(connection=config["trigger_control_source"])

                # map between camera device and windows
                self.__frame_window_map = {}
                self.__camera_image_subscriber_map = {}
                for idx, id in enumerate(config["camera_ids"]):
                    self.__frame_window_map[id] = self.findChild(QLabel, config["camera_windows"][idx])
                    self.__console.info(f"Ready for camera grabber #{id} monitoring")
                    self.__camera_image_subscriber_map[id] = CameraMonitorSubscriber(connection=config["image_stream_monitor_source"],
                                                                                     topic=config["image_stream_monitor_topic"][idx])
                    self.__camera_image_subscriber_map[id].frame_update_signal.connect(self.on_update_camera_image)
                    self.__camera_image_subscriber_map[id].start() # start thread for each


        except Exception as e:
            self.__console.error(f"{e}")

    def clear_all(self):
        """ clear graphic view """
        try:
            self.__frame_defect_grid_plot.clear()
        except Exception as e:
            self.__console.error(f"{e}")

    def on_change_light_control(self, value):
        """ control value update """
        self.label_light_control_value.setText(str(value))
        

    def on_btn_focus_set(self, id:int):
        """ focus move control """
        focus_value = self.findChild(QLineEdit, name=f"edit_focus_value_{id}").text()
        self.__lens_control_requester.focus_move(id=id, value=int(focus_value))
    
    def on_btn_focus_read_all(self):
        """ call all focus value read (async) """
        self.__lens_control_requester.read_focus()

    def on_update_focus(self, data:dict):
        """ update focus value for all lens """
        for id, value in data.items():
            component = self.findChild(QLineEdit, name=f"edit_focus_value_{id}")
            if component !=  None:
                component.setText(str(value))
        

    def on_update_lens_control_status(self, msg:str): # update lens control pipeline status
        self.label_lens_control_pipeline_message.setText(msg)

    def on_update_camera_image(self, camera_id:int, w:int, h:int, c:int, image:np.ndarray):
        """ show image on window for each camera id """
        self.__console.info("update image")
        guided_image = image.copy()
        cx = w//2
        cy = h//2
        cv2.line(guided_image, (cx, 0), (cx, h), (0, 255, 0), 5) #(960, 0) (960, 1920)
        cv2.line(guided_image, (0, cy), (w, cy), (0, 255, 0), 5) # 

        qt_image = QImage(guided_image.data, w, h, c*w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        try:
            self.__frame_window_map[camera_id].setPixmap(pixmap.scaled(self.__frame_window_map[camera_id].size(), Qt.AspectRatioMode.KeepAspectRatio))
        except Exception as e:
            self.__console.error(e)


    def on_btn_camera_view_test(self):
        frame_image = cv2.imread("./resource/1920_1200_test_image.jpg")
        camera_id = 1
        #frame_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # t = datetime.now()

        # cv2.putText(frame_image, t.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3], (10, 1070), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0,255,0), 2, cv2.LINE_AA)
        # cv2.putText(frame_image, f"Camera #{camera_id}(fps:{fps:.1f})", (10,50), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (1,255,0), 2, cv2.LINE_AA)

        h, w, ch = frame_image.shape

        cx = w//2
        cy = h//2
        cv2.line(frame_image, (cx, 0), (cx, h), (0, 255, 0), 5) #(960, 0) (960, 1920)
        cv2.line(frame_image, (0, cy), (w, cy), (0, 255, 0), 5) # 
        
        qt_image = QImage(frame_image.data, w, h, ch*w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        try:
            print(type(self.__frame_window_map[camera_id]))
            self.__frame_window_map[camera_id].setPixmap(pixmap.scaled(self.__frame_window_map[camera_id].size(), Qt.AspectRatioMode.KeepAspectRatio))
        except Exception as e:
            self.__console.error(e)

    
                
    def closeEvent(self, event:QCloseEvent) -> None: 
        """ terminate main window """

        # code here
        

        # clear instance explicitly
        if self.__lens_control_requester:
            self.__console.info("Close lens control requester")
            self.__lens_control_requester.close()
        if self.__temp_monitor_subscriber:
            self.__console.info("Close temperature subscriber")
            self.__temp_monitor_subscriber.close()
        if self.__pulse_generator_requester:
            self.__console.info("Close Pulse Generator Requester")
            self.__pulse_generator_requester.close()
            
        return super().closeEvent(event)

    def on_update_temperature(self, values:dict):
        """ update temperature value in GUI """
        try:        
            self.label_temperature_value_1.setText(str(values["1"]))
            self.label_temperature_value_2.setText(str(values["2"]))
            self.label_temperature_value_3.setText(str(values["3"]))
            self.label_temperature_value_4.setText(str(values["4"]))
            self.label_temperature_value_5.setText(str(values["5"]))
            self.label_temperature_value_6.setText(str(values["6"]))
            self.label_temperature_value_7.setText(str(values["7"]))
            self.label_temperature_value_8.setText(str(values["8"]))
        except Exception as e:
            pass

    def on_update_temperature_status(self, msg:str): # update temperature control monitoring pipeline status
        self.label_temp_monitor_pipeline_message.setText(msg)

    

    def on_btn_trigger_start(self):
        """ event callback : trigger start """
        freq = self.findChild(QLineEdit, name="edit_trigger_frequency").text()
        samples = self.findChild(QLineEdit, name="edit_trigger_samples").text()
        duty = self.findChild(QLineEdit, name="edit_trigger_duty").text()
        continuous_mode = self.findChild(QCheckBox, name="chk_trigger_mode_continuous").isChecked()

        if continuous_mode:
            if not self.__trigger.start_trigger_continuous("Dev1/ctr0", float(freq), float(duty)):
                QMessageBox.critical(self, "Error", f"Trigger is already running..")
        else:
            self.__trigger.start_trigger_finite("Dev1/ctr0", float(freq), int(samples), float(duty))
            
        self.statusBar().showMessage(f"Trigger is now started")

    def on_btn_trigger_stop(self):
        """ event callback : trigger stop """
        self.__trigger.stop_trigger()
        self.statusBar().showMessage(f"Trigger is now stopped")
        
    
    def on_btn_defect_visualization_test(self):
        """ visualization test function"""

        self.__frame_defect_grid_plot.clear()
        
        n_sample = 10
        y = [random.randint(1, 10) for _ in range(n_sample)]
        x = [random.randint(0, 4000) for _ in range(n_sample)]
        c = [random.choice(['r', 'g', 'b']) for _ in range(n_sample)]

        points = []
        for idx in range(n_sample):
            points.append({'pos': (x[idx], y[idx]), 'brush': c[idx], 'size': 10, 'symbol':'s'})

        scatter = graph.ScatterPlotItem()
        scatter.addPoints(points)
        self.__frame_defect_grid_plot.addItem(scatter)
        self.__frame_defect_grid_plot.enableAutoRange(axis=graph.ViewBox.XAxis)
        self.__frame_defect_grid_plot.show()

    def on_btn_light_control_set(self):
        """ event callback : light on """
        if "dmx_ip" in self.__config and "dmx_port" in self.__config:
            value = int(self.label_light_control_value.text())
            self.__light_control_requester.set_control(self.__config["dmx_ip"], self.__config["dmx_port"], self.__config["light_ids"], value)
        else:
            QMessageBox.critical(self, "Error", f"DMX IP and Port is not defined")
        

    def on_btn_light_control_off(self):
        """ event callback : light on """
        if "dmx_ip" in self.__config and "dmx_port" in self.__config:
            self.__light_control_requester.set_control(self.__config["dmx_ip"], self.__config["dmx_port"], self.__config["light_ids"], 0)
        else:
            QMessageBox.critical(self, "Error", f"DMX IP and Port is not defined")

    def __image_stream_subscribe(self):
        """ zmq subscribe for camera monitoring """
        while True:
            try:

                parts = self.__camera_monitor_socket.recv_multipart()
                self.__console.info(f"Received data part {parts}")

                if len(parts) < 3:
                    self.__console.error(f"Invalid multipart message received")
                else:
                    topic = parts[0].decode("utf-8")
                    camera_id = int(json.loads(parts[1].decode("utf-8"))["camera_id"])
                    image_data = parts[2]
                    self.__console.info(f"Received data from Camera ID : {camera_id}")

                if topic == "image_stream_monitor" and image_data is not None:
                    np_array = np.frombuffer(image_data, np.uint8)
                    image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
                    # display image
                    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb_image.shape
                    bytes_per_line = ch * w
                    qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(qt_image)

                    try:
                        self.__frame_window_map[camera_id].setPixmap(pixmap.scaled(self.__frame_window_map[camera_id].size(), Qt.KeepAspectRatio))
                    except Exception as e:
                        self.__console.error(f"Frame display error : {e}")
                else:
                    self.__console.error(f"Invalid topic received: {topic}")

            except Exception as e:
                self.__console.critical(f"Error receiving image: {e}")

            time.sleep(0.1) # for context switching

    # show camera grabbed image
    def __camera_frame_update(self, camera_id, frame, fps):
        """ show camera image from subscriber"""
        frame_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        t = datetime.now()
        cv2.putText(frame_image, t.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3], (10, 1070), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0,255,0), 2, cv2.LINE_AA)
        cv2.putText(frame_image, f"Camera #{camera_id}(fps:{fps:.1f})", (10,50), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (1,255,0), 2, cv2.LINE_AA)

        h, w, ch = frame_image.shape
        qt_image = QImage(frame_image.data, w, h, ch*w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        try:
            self.__frame_window_map[camera_id].setPixmap(pixmap.scaled(self.__frame_window_map[camera_id].size(), Qt.AspectRatioMode.KeepAspectRatio))
        except Exception as e:
            self.__console.error(e)