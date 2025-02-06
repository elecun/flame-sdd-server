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
from concurrent.futures import ThreadPoolExecutor

try:
    # using PyQt5
    from PyQt5.QtGui import QImage, QPixmap, QCloseEvent, QStandardItem, QStandardItemModel
    from PyQt5.QtWidgets import QApplication, QFrame, QMainWindow, QLabel, QPushButton, QMessageBox
    from PyQt5.QtWidget import QProgressBar, QFileDialog, QComboBox, QLineEdit, QSlider, QCheckBox, QComboBox
    from PyQt5.uic import loadUi
    from PyQt5.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
except ImportError:
    # using PyQt6
    from PyQt6.QtGui import QImage, QPixmap, QCloseEvent, QStandardItem, QStandardItemModel
    from PyQt6.QtWidgets import QApplication, QFrame, QMainWindow, QLabel, QPushButton, QCheckBox, QComboBox
    from PyQt6.QtWidgets import QMessageBox, QProgressBar, QFileDialog, QComboBox, QLineEdit, QSlider, QVBoxLayout
    from PyQt6.uic import loadUi
    from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
    
from util.logger.console import ConsoleLogger
from subscriber.temperature import TemperatureMonitorSubscriber
from publisher.lens_control import LensControlPublisher
from requester.light_control import LightControlRequester
from requester.pulse_generator import PulseGeneratorRequester
from subscriber.camera import CameraMonitorSubscriber


class AppWindow(QMainWindow):
    def __init__(self, config:dict):
        """ initialization """
        super().__init__()
        
        self.__console = ConsoleLogger.get_logger() # logger
        self.__config = config  # copy configuration data
        self.__pipeline_context = zmq.Context(14) # zmq context

        self.__frame_defect_grid_layout = QVBoxLayout()
        self.__frame_defect_grid_plot = graph.PlotWidget()

        # device control interfaces
        self.__temp_monitor_subscriber = None
        self.__lens_control_publisher = None
        self.__light_control_requester = None
        self.__pulse_generator_requester = None

        try:            
            if "gui" in config:

                # load UI File
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
                styles = {"color": "#000", "font-size": "15px"}
                self.__frame_defect_grid_plot.setLabel("left", "Camera Channels", **styles)
                self.__frame_defect_grid_plot.setLabel("bottom", "Frame Counts", **styles)
                self.__frame_defect_grid_plot.addLegend()
                
                # register button event callback function
                self.btn_trigger_start.clicked.connect(self.on_btn_trigger_start)
                self.btn_trigger_stop.clicked.connect(self.on_btn_trigger_stop)
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
                self.btn_focus_initialize_all.clicked.connect(self.on_btn_focus_initialize_all)
                self.btn_focus_preset_set_all.clicked.connect(self.on_btn_focus_preset_set_all)

                # register dial event callback function
                self.dial_light_control.valueChanged.connect(self.on_change_light_control)
                self.dial_light_control.sliderReleased.connect(self.on_set_light_control)

                # find focus preset files in preset directory
                #self.focus_preset_ctrl = self.findChild(QComboBox, name="combobox_focus_preset")
                preset_path = pathlib.Path(config["app_path"])/pathlib.Path(config["preset_path"])
                self.__config["preset_path"] = preset_path.as_posix()
                self.__console.info(f"+ Preset Path : {preset_path}")
                if os.path.exists(pathlib.Path(config["app_path"])):
                    preset_files = [f for f in os.listdir(preset_path)]
                    for preset in preset_files:
                        self.combobox_focus_preset.addItem(preset)

                

                # create temperature monitoring subscriber
                if "use_temperature_monitor" in config and config["use_temperature_monitor"]:
                    if "temp_stream_source" in config and "temp_stream_topic" in config:
                        self.__console.info("+ Create Temperature Monitoring Subscriber...")
                        self.__temp_monitor_subscriber = TemperatureMonitorSubscriber(self.__pipeline_context, connection=config["temp_stream_source"], topic=config["temp_stream_topic"])
                        self.__temp_monitor_subscriber.temperature_update_signal.connect(self.on_update_temperature)
                        self.__temp_monitor_subscriber.start() # run in thread
                else:
                    self.__console.warning("Temperature Monitor is not enabled")

                # create lens control publisher
                if "use_lens_control" in config and config["use_lens_control"]:
                    if "lens_control_source" in config:
                        self.__console.info("+ Create Lens Control Publisher...")
                        self.__lens_control_publisher = LensControlPublisher(self.__pipeline_context, connection=config["lens_control_source"])
                        #self.__lens_control_publisher.focus_read_update_signal.connect(self.on_update_focus)
                else:
                    self.__console.warning("Lens Control is not enabled")

                # create light control requester
                if "use_light_control" in config and config["use_light_control"]:
                    if "light_control_source" in config:
                        self.__console.info("+ Create Light Control Requester")
                        self.__light_control_requester = LightControlRequester(self.__pipeline_context, connection=config["light_control_source"])
                else:
                    self.__console.warning("Light Control is not enabled")

                # map between camera device and windows
                self.__frame_window_map = {}
                self.__camera_image_subscriber_map = {}

                for idx, id in enumerate(config["camera_ids"]):
                    self.__frame_window_map[id] = self.findChild(QLabel, config["camera_windows"][idx])
                    self.__console.info(f"Ready for camera grabber #{id} monitoring")
                    portname = f"image_stream_monitor_source_{id}"
                    self.__console.info("+ Create Camera #{id} Monitoring Subscriber...")
                    self.__camera_image_subscriber_map[id] = CameraMonitorSubscriber(self.__pipeline_context,connection=config[portname],
                                                                                     topic=f"{config['image_stream_monitor_topic_prefix']}{id}")
                    self.__camera_image_subscriber_map[id].frame_update_signal.connect(self.on_update_camera_image)
                    self.__camera_image_subscriber_map[id].start()

                # create trigger control requester
                if "use_trigger_control" in config and config["use_trigger_control"]:
                    if "trigger_control_source":
                        self.__console.info("+ Create Trigger Control Requester")
                        self.__pulse_generator_requester = PulseGeneratorRequester(self.__pipeline_context, connection=config["trigger_control_source"])
                else:
                    self.__console.warning("Trigger Control is not enabled")

        except Exception as e:
            self.__console.error(f"{e}")

    def clear_all(self):
        """ clear graphic view """
        try:
            self.__frame_defect_grid_plot.clear()
        except Exception as e:
            self.__console.error(f"{e}")

    def on_btn_focus_initialize_all(self):
        """ initialize all """
        self.__lens_control_publisher.focus_init_all()
    
    def on_btn_focus_preset_set_all(self):
        """ set focus preset for all lens """
        # focus_preset_ctrl = self.findChild(QComboBox, name="combobox_focus_preset")
        selected_preset = self.combobox_focus_preset.currentText()

        if selected_preset:
            absolute_path = pathlib.Path(self.__config["preset_path"])/selected_preset
            self.__console.info(f"Selected Focus Lens Control preset : {absolute_path}")

            try:
                # file load (json format)
                preset_file = open(absolute_path, encoding='utf-8')
                focus_preset = json.load(preset_file)

                # move focus
                for lens_id in focus_preset["focus_value"]:
                    edit_focus = self.findChild(QLineEdit, name=f"edit_focus_value_{lens_id}")
                    if edit_focus !=  None:
                        edit_focus.setText(str(focus_preset["focus_value"][lens_id]))
                        if self.__lens_control_publisher:
                            self.__lens_control_publisher.focus_move(int(lens_id), focus_preset["focus_value"][lens_id])
                        else:
                            self.__console.error("Lens Control Publisher is not initialized")

            except json.JSONDecodeError as e:
                self.__console.error(f"Focus Preset Load Error : {e}")
            except FileNotFoundError as e:
                self.__console.error(f"{absolute_path} File not found")


    def on_change_light_control(self, value):
        """ control value update """
        self.label_light_control_value.setText(str(value))
        

    def on_btn_focus_set(self, id:int):
        """ focus move control """
        focus_value = self.findChild(QLineEdit, name=f"edit_focus_value_{id}").text()
        self.__lens_control_publisher.focus_move(user_id=id, value=int(focus_value))
        self.__console.info(f"Focus Move : {id} -> {focus_value}")
    
    def on_btn_focus_read_all(self):
        """ call all focus value read (async) """
        self.__lens_control_publisher.read_focus()

    def on_update_focus(self, data:dict):
        """ update focus value for all lens """
        for id, value in data.items():
            component = self.findChild(QLineEdit, name=f"edit_focus_value_{id}")
            if component !=  None:
                component.setText(str(value))
        

    def on_update_lens_control_status(self, msg:str): # update lens control pipeline status
        self.label_lens_control_pipeline_message.setText(msg)

    def on_update_camera_image(self, camera_id:int, image:np.ndarray):
        """ show image on window for each camera id """
        h, w, ch = image.shape
        check = self.findChild(QCheckBox, "chk_show_alignment_line")
        if check and check.isChecked():
            cx = w//2
            cy = h//2
            cv2.line(image, (cx, 0), (cx, h), (0, 255, 0), 5) #(960, 0) (960, 1920)
            cv2.line(image, (0, cy), (w, cy), (0, 255, 0), 5) # 

        qt_image = QImage(image.data, w, h, ch*w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        try:
            self.__frame_window_map[camera_id].setPixmap(pixmap.scaled(self.__frame_window_map[camera_id].size(), Qt.AspectRatioMode.KeepAspectRatio))
            self.__frame_window_map[camera_id].show()
        except Exception as e:
            self.__console.error(e)
    
                
    def closeEvent(self, event:QCloseEvent) -> None: 
        """ terminate main window """      

        # clear instance explicitly
        if self.__light_control_requester:
            self.__light_control_requester.close()
            self.__console.info("Close light control requester")
        if self.__lens_control_publisher:
            self.__lens_control_publisher.close()
            self.__console.info("Close lens control requester")
        if self.__pulse_generator_requester:
            self.__pulse_generator_requester.close()
            self.__console.info("Close Pulse Generator Requester")
        if self.__temp_monitor_subscriber:
            self.__temp_monitor_subscriber.close()
            self.__console.info("Close temperature subscriber")

        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(lambda subscriber: subscriber.close(), self.__camera_image_subscriber_map.values())

        # for id, subscriber in self.__camera_image_subscriber_map.items():
        #     subscriber.close()
        #     self.__console.info(f"Close Camera #{id} Monitor subscriber")

        # context termination with linger=0
        self.__pipeline_context.destroy(0)
            
        return super().closeEvent(event)

    def on_update_temperature(self, values:dict):
        """ update temperature value in GUI """
        try:        
            self.label_temperature_value_1.setText(str(int(values["1"])*0.1))
            self.label_temperature_value_2.setText(str(int(values["2"])*0.1))
            self.label_temperature_value_3.setText(str(int(values["3"])*0.1))
            self.label_temperature_value_4.setText(str(int(values["4"])*0.1))
            self.label_temperature_value_5.setText(str(int(values["5"])*0.1))
            self.label_temperature_value_6.setText(str(int(values["6"])*0.1))
            self.label_temperature_value_7.setText(str(int(values["7"])*0.1))
            self.label_temperature_value_8.setText(str(int(values["8"])*0.1))
        except Exception as e:
            pass

    def on_update_temperature_status(self, msg:str): # update temperature control monitoring pipeline status
        self.label_temp_monitor_pipeline_message.setText(msg)

    

    def on_btn_trigger_start(self):
        """ event callback : trigger start """
        freq = self.findChild(QLineEdit, name="edit_trigger_frequency").text()
        duty = self.findChild(QLineEdit, name="edit_trigger_duty").text()
        

        # if continuous_mode:
        #     self.__pulse_generator_requester.start_generation(float(freq), float(duty))
        # else:
        #     self.__trigger.start_trigger_finite("Dev1/ctr0", float(freq), int(samples), float(duty))
            
        self.statusBar().showMessage(f"Trigger is now started")

    def on_btn_trigger_stop(self):
        """ event callback : trigger stop """
        self.__pulse_generator_requester.stop_generation()
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

    def on_set_light_control(self):
        """ event callback : light control """
        if "use_light_control" in self.__config and self.__config["use_light_control"]:
            if "dmx_ip" in self.__config and "dmx_port" in self.__config:
                value = int(self.label_light_control_value.text())
                self.__light_control_requester.set_control(self.__config["dmx_ip"], self.__config["dmx_port"], self.__config["light_ids"], value)
            else:
                QMessageBox.critical(self, "Error", f"DMX IP and Port is not defined")
        else:
            value = int(self.label_light_control_value.text())
            QMessageBox.critical(self, "Error", f"Light control did not activated. value is {value}")
        