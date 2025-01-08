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
import json

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
from subscriber.temperature import TemperatureSubscriber


'''
Main window
'''

class AppWindow(QMainWindow):
    def __init__(self, config:dict):
        """ initialization """
        super().__init__()
        
        self.__console = ConsoleLogger.get_logger()
        self.__config = config
        self.__trigger = trigger.Trigger() # Trigger Controller
        self.__light = light.LightController() # Light Controller

        self.__frame_defect_grid_layout = QVBoxLayout(self)
        self.__frame_defect_grid_plot = graph.PlotWidget()

        # map between camera device and windows
        self.__frame_window_map = {}
        for idx, id in enumerate(config["camera_ids"]):
            self.__frame_window_map[id] = self.findChild(QLabel, config["camera_windows"][idx])

        # zmq subscribe for camera monitoring
        self.__camera_monitor_context = zmq.Context()
        self.__camera_monitor_socket = self.__camera_monitor_context.socket(zmq.SUB)
        self.__camera_monitor_socket.connect(f"tcp://{config['camera_monitoring_ip']}:{config['camera_monitoring_port']}")
        self.__camera_monitor_socket.setsockopt_string(zmq.SUBSCRIBE, "image_stream_monitor")
        self.__image_stream_thread = threading.Thread(target=self.__image_stream_subscribe)
        self.__image_stream_thread.start()

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
                #self.__frame_defect_grid_plot.setTitle(f"{ch} Spectogram(Linear)", color="k", size="25pt")
                styles = {"color": "#000", "font-size": "15px"}
                self.__frame_defect_grid_plot.setLabel("left", "Camera Channels", **styles)
                self.__frame_defect_grid_plot.setLabel("bottom", "Frame Counts", **styles)
                self.__frame_defect_grid_plot.addLegend()
                #self.__frame_defect_grid_plot.addItem(image)
                
                # register event callback function
                self.btn_trigger_start.clicked.connect(self.on_btn_trigger_start)
                self.btn_trigger_stop.clicked.connect(self.on_btn_trigger_stop)
                self.btn_defect_visualization_test.clicked.connect(self.on_btn_defect_visualization_test)
                self.btn_light_on.clicked.connect(self.on_btn_light_on)
                self.btn_light_off.clicked.connect(self.on_btn_light_off)

                # create temperature monitoring subscriber
                if config["temperature_stream_source"] and config["temperature_stream_topic"]:
                    self.__temperature_subscriber = TemperatureSubscriber(connection=config["temperature_stream_source"], topic=config["temperature_stream_topic"])
                    self.__temperature_subscriber.temperature_update_signal.connect(self.on_update_temperature)
                    self.__temperature_subscriber.start() # run in thread


        except Exception as e:
            self.__console.error(f"{e}")

    def clear_all(self):
        """ clear graphic view """
        try:
            self.__frame_defect_grid_plot.clear()
        except Exception as e:
            self.__console.error(f"{e}")
                
    def closeEvent(self, event:QCloseEvent) -> None: 
        """ terminate main window """
        self.__console.info("Window is now terminated")

        # code here
        self.__trigger.stop_trigger()
            
        return super().closeEvent(event)

    def on_update_temperature(self, values:dict):
        self.label_temperature_value_1.setText(str(values["1"]))
        self.label_temperature_value_2.setText(str(values["2"]))
    

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

    def on_btn_light_on(self):
        """ event callback : light on """
        if "dmx_ip" in self.__config and "dmx_port" in self.__config:
            self.__light.light_on(self.__config["dmx_ip"], self.__config["dmx_port"])
            self.__console.info(f"Light ON")
        else:
            QMessageBox.critical(self, "Error", f"DMX IP and Port is not defined")
        

    def on_btn_light_off(self):
        """ event callback : light off """
        if "dmx_ip" in self.__config and "dmx_port" in self.__config:
            self.__light.light_off(self.__config["dmx_ip"], self.__config["dmx_port"])
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