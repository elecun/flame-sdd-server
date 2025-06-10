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
import datetime
import pyqtgraph as graph
import random
import zmq
import zmq.asyncio
import json
import cv2
from functools import partial
from concurrent.futures import ThreadPoolExecutor
import platform
from collections import deque
import re
from typing import List, Tuple
import csv
import re

try:
    # using PyQt5
    from PyQt5.QtGui import QImage, QPixmap, QCloseEvent, QStandardItem, QStandardItemModel
    from PyQt5.QtWidgets import QApplication, QFrame, QMainWindow, QLabel, QPushButton, QMessageBox, QDialog
    from PyQt5.QtWidgets import QProgressBar, QFileDialog, QComboBox, QLineEdit, QSlider, QCheckBox, QComboBox
    from PyQt5.uic import loadUi
    from PyQt5.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
except ImportError:
    # using PyQt6
    from PyQt6.QtGui import QImage, QPixmap, QCloseEvent, QStandardItem, QStandardItemModel
    from PyQt6.QtWidgets import QApplication, QFrame, QMainWindow, QLabel, QPushButton, QCheckBox, QComboBox, QDialog
    from PyQt6.QtWidgets import QMessageBox, QProgressBar, QFileDialog, QComboBox, QLineEdit, QSlider, QVBoxLayout
    from PyQt6.uic import loadUi
    from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
    
from util.logger.console import ConsoleLogger
from subscriber.temperature import TemperatureMonitorSubscriber
from publisher.lens_control import LensControlPublisher
from observer.network_storage import NASStatusObserver
from monitor.observer.network_device import NetworkDeviceObserver
from publisher.camera_control import CameraControlPublisher
from subscriber.camera_status import CameraStatusMonitorSubscriber
from subscriber.line_signal import LineSignalSubscriber
from subscriber.dmx_light_control import DMXLightControlSubscriber
from subscriber.camera import CameraMonitorSubscriber
from subscriber.dk_level2 import DKLevel2DataSubscriber
from subscriber.dk_level2_status import DKLevel2StatusSubscriber
from requester.system_echo import SystemEchoRequester

class DateTimeAxis(graph.DateAxisItem):
    def __init__(self, spacing=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.time_spacing = spacing

    def tickStrings(self, values, scale, spacing):
        return [datetime.datetime.fromtimestamp(v).strftime('%Y.%m.%d %H:%M:%S') for v in values]
    
    def tickValues(self, minVal, maxVal, size):
        start = int(minVal // self.time_spacing) * self.time_spacing
        values = []
        v = start
        while v <= maxVal:
            values.append(v)
            v += self.time_spacing
        return [(self.time_spacing, values)]

class AppWindow(QMainWindow):
    def __init__(self, config:dict):
        """ initialization """
        super().__init__()
        
        self.__console = ConsoleLogger.get_logger() # logger
        self.__config = config  # copy configuration data

        ### configure zmq context
        n_ctx_value = config.get("n_io_context", 14)
        self.__pipeline_context = zmq.Context(n_ctx_value) # zmq context

        ### chart & graph view layout
        self.__frame_defect_grid_layout = QVBoxLayout()
        self.__frame_defect_grid_plot = graph.PlotWidget()
        self.__frame_temperature_grid_layout = QVBoxLayout()
        self.__frame_temperature_grid_plot = graph.PlotWidget(axisItems={'bottom': DateTimeAxis(orientation='bottom', spacing=config.get("temperature_time_spacing",1))})
        self.__frame_temperature_x = deque(maxlen=config["temperature_max_data_size"])
        self.__frame_temperature_y = [deque(maxlen=config["temperature_max_data_size"]) for _ in range(len(config["temperature_ids"]))]
        self.__frame_temperature_curves = []

        ### device/service control interfaces
        self.__temperature_monitor_subscriber = None        # temperature monitor subscriber
        self.__camera_status_monitor_subscriber = None      # camera status monitor subscriber
        self.__line_signal_monitor_subscriber = None        # line signal status monitor subscriber
        self.__light_control_subscriber = None              # light control subscriber
        self.__dk_level2_data_subscriber = None             # level2 data subscriber
        self.__dk_level2_status_subscriber = None           # level2 status subscriber
        self.__sdd_inference_subscriber = None              # sdd inference subscriber
        self.__camera_image_subscriber_map = {}             # camera image subscriber
        self.__lens_control_publisher = None                # lens control publisher
        self.__camera_control_publisher_map = {}            # camera control publishers
        self.__system_echo_requester_map = {}               # system echo(alive check) requester
        self.__nas_status_observer = None                   # nas status observer  
        self.__dmx_status_observer = None                   # dmx status observer 

        # variables
        self.__last_preset_file = "" # last preset file
        self.__system_online = False # system is on-line

        try:            
            if "gui" in config:

                # load UI File
                ui_path = pathlib.Path(config["app_path"]) / config["gui"]
                if os.path.isfile(ui_path):
                    loadUi(ui_path, self)
                else:
                    raise Exception(f"Cannot found UI file : {ui_path}")
                
                # defect graphic view frame
                self.__frame_defect_grid = self.findChild(QFrame, name="frame_defect_grid")
                self.__frame_defect_grid_layout.addWidget(self.__frame_defect_grid_plot)
                self.__frame_defect_grid_layout.setContentsMargins(5,5,5,5)
                self.__frame_defect_grid_plot.setBackground('white')
                self.__frame_defect_grid_plot.showGrid(x=True, y=True)
                self.__frame_defect_grid_plot.setLimits(xMin=0, xMax=10000, yMin=0, yMax=11)
                self.__frame_defect_grid_plot.setRange(yRange=(0,len(config["camera_ids"])), xRange=(0,100))
                self.__frame_defect_grid_plot.setMouseEnabled(x=True, y=False)
                self.__frame_defect_grid.setLayout(self.__frame_defect_grid_layout)
                styles = {"color": "#000", "font-size": "15px"}
                self.__frame_defect_grid_plot.setLabel("left", "Camera IDs", **styles)
                self.__frame_defect_grid_plot.setLabel("bottom", "Length", **styles)
                self.__frame_defect_grid_plot.addLegend()

                # temperature graphic view frame
                self.__frame_temperature_grid = self.findChild(QFrame, name="frame_temperature_grid")
                self.__frame_temperature_grid_layout.addWidget(self.__frame_temperature_grid_plot)
                self.__frame_temperature_grid_layout.setContentsMargins(5,5,5,5)
                self.__frame_temperature_grid_plot.setBackground('white')
                self.__frame_temperature_grid_plot.showGrid(x=True, y=True)
                self.__frame_temperature_grid_plot.setLimits(yMin=0, yMax=200)
                self.__frame_temperature_grid_plot.setYRange(0, 100)
                self.__frame_temperature_grid_plot.setMouseEnabled(x=True, y=False)
                self.__frame_temperature_grid.setLayout(self.__frame_temperature_grid_layout)
                styles = {"color": "#000", "font-size": "15px"}
                self.__frame_temperature_grid_plot.setLabel("left", "Temperature", **styles)
                self.__frame_temperature_grid_plot.setLabel("bottom", "Time", **styles)
                colors = ['red', 'green', 'blue', 'cyan', 'magenta', 'yellow', 'orange', 'purple']
                for idx, id in enumerate(config["temperature_ids"]):
                    curve = self.__frame_temperature_grid_plot.plot([],[],pen=graph.mkPen(colors[idx % len(colors)], width=2))
                    self.__frame_temperature_curves.append(curve)
                    legend = graph.LegendItem(offset=(130*id, 1)) # show on top
                    legend.setParentItem(self.__frame_temperature_grid_plot.getPlotItem())
                    legend.addItem(curve, f"Temperature {id}")
                
                
                # register button event callback function
                self.btn_preset_load.clicked.connect(self.on_btn_preset_load)
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
                self.btn_focus_preset_set_all.clicked.connect(self.on_btn_focus_preset_set_all)     # set focus all
                self.btn_exposure_time_set_all.clicked.connect(self.on_btn_exposure_time_set_all)   # set exposure time all
                self.btn_light_level_set_all.clicked.connect(self.on_btn_light_level_set_all)       # set light level all
                self.btn_light_off.clicked.connect(self.on_btn_light_off)                           # light off

                # default status indication
                self.set_status_inactive("label_onsite_controller_status")
                self.set_status_inactive("label_server_status")
                self.set_status_inactive("label_level2_status")
                self.set_status_inactive("label_dmx_status")
                self.set_status_inactive("label_nas_status")
                self.set_status_inactive("label_line_signal_status")
                self.set_status_inactive("label_hmd_signal_1_status")
                self.set_status_inactive("label_hmd_signal_2_status")
                self.set_status_inactive("label_sdd_processing_status")               

                # find preset files in preset directory (default : ./bin/preset)
                self.__preset_files = []
                self.__config["preset_path"] = (pathlib.Path(self.__config["root_path"]) / "bin" / "preset").as_posix()
                if os.path.exists(pathlib.Path(self.__config["preset_path"])):
                    self.__preset_files = [f for f in os.listdir(self.__config["preset_path"])]
                    for preset in self.__preset_files:
                        self.combobox_preset.addItem(preset)

                # create temperature monitoring subscriber
                use_temperature_monitor = self.__config.get("use_temperature_monitor", False)
                if use_temperature_monitor:
                    if "temp_stream_source" in config and "temp_stream_sub_topic" in config:
                        try:
                            _log_config = {
                                "option_save_temperature_log":config.get("option_save_temperature_log", False),
                                "option_save_temperature_log_path":config.get("option_save_temperature_log_path", ""),
                            }
                            self.__temperature_monitor_subscriber = TemperatureMonitorSubscriber(self.__pipeline_context, 
                                                                                                 connection=config["temp_stream_source"], 
                                                                                                 topic=config["temp_stream_sub_topic"],log_config=_log_config)
                            self.__temperature_monitor_subscriber.temperature_update_signal.connect(self.on_update_temperature)
                            self.__temperature_monitor_subscriber.start() # run in thread
                        except Exception as e:
                            self.__console.warning(f"Temperature Monitor has problem : {e}")
                else:
                    self.__console.warning("Temperature Monitor is not enabled")
                
                # camera status monitoring subscriber
                if "use_camera_status_monitor" in config and config["use_camera_status_monitor"]:
                    if "camera_status_monitor_source" in config and "camera_status_monitor_topic" in config:
                        self.__console.info("+ Create Camera Status Monitoring Subscriber...")
                        self.__camera_status_monitor_subscriber = CameraStatusMonitorSubscriber(self.__pipeline_context, connection=config["camera_status_monitor_source"], topic=config["camera_status_monitor_topic"])
                        self.__camera_status_monitor_subscriber.status_update_signal.connect(self.on_update_camera_status)

                # dk level2 data monitoring subscriber
                use_dk_level2_interface = self.__config.get("use_dk_level2_interface", False)
                if use_dk_level2_interface:
                    if "dk_level2_interface_source" in config and "dk_level2_interface_sub_topic" in config:
                        self.__dk_level2_data_subscriber = DKLevel2DataSubscriber(self.__pipeline_context, 
                                                                                  connection=config["dk_level2_interface_source"], 
                                                                                  topic=config["dk_level2_interface_sub_topic"])
                        self.__dk_level2_data_subscriber.level2_data_update_signal.connect(self.on_update_dk_level2_data)
                        self.__dk_level2_data_subscriber.start()

                        self.__dk_level2_status_subscriber = DKLevel2StatusSubscriber(self.__pipeline_context,
                                                                                      connection=config["dk_level2_status_source"],
                                                                                      topic=config["dk_level2_status_sub_topic"])
                        self.__dk_level2_status_subscriber.level2_status_update_signal.connect(self.on_update_dk_level2_status)
                        self.__dk_level2_status_subscriber.start()
                        
                else:
                    self.__console.warning("DK Level2 Data Interface is not enabled")

                # create lens control publisher
                use_lens_control = self.__config.get("use_lens_control", False)
                if use_lens_control:
                    if "lens_control_source" in config:
                        try:
                            self.__lens_control_publisher = LensControlPublisher(self.__pipeline_context, 
                                                                                 connection=config["lens_control_source"])
                        except Exception as e:
                            self.__console.warning(f"Lens Control Publisher has problem : {e}")
                else:
                    self.__console.warning("Lens Control is not enabled")
                
                # create line signal monitoring subscriber
                use_line_signal_monitor = self.__config.get("use_line_signal_monitor", False)
                if use_line_signal_monitor:
                    if "line_signal_monitor_source" in config and "line_signal_monitor_topic" in config:
                        self.__line_signal_monitor_subscriber = LineSignalSubscriber(self.__pipeline_context, 
                                                                                     connection=config["line_signal_monitor_source"], 
                                                                                     topic=config["line_signal_monitor_topic"])
                        self.__line_signal_monitor_subscriber.line_signal.connect(self.on_update_line_signal)
                        self.__line_signal_monitor_subscriber.start()
                else:
                    self.__console.warning("Line Signal Monitor is not enabled")

                # create nas status observer
                use_nas_status_monitor = self.__config.get("use_nas_status_monitor", False)
                if use_nas_status_monitor:
                    self.__nas_status_observer = NASStatusObserver(config["nas_status_file_path"])
                    self.__nas_status_observer.status_update_signal.connect(self.on_update_nas_status)

                # create dmx status observer
                use_dmx_status_monitor = self.__config.get("use_dmx_status_monitor", False)
                if use_dmx_status_monitor:
                    self.__dmx_status_observer = NetworkDeviceObserver(config["dmx_ip"])
                    self.__dmx_status_observer.status_update_signal.connect(self.on_update_dmx_status)
                else:
                    self.__console.warning("DMX Status Monitor is not enabled")
                        
                # create camera control publisher
                use_camera_control = self.__config.get("use_camera_control", False)
                if use_camera_control:
                    for idx, id in enumerate(config["camera_ids"]):
                        portname = f"camera_control_source_{id}"
                        self.__console.info("- Start Camera #{id} Control...")
                        self.__camera_control_publisher_map[id] = CameraControlPublisher(self.__pipeline_context, 
                                                                                         connection=config[portname])
                else:
                    self.__console.warning("Camera Control is not enabled.")

                # create light control with DMX
                use_light_control = self.__config.get("use_light_control", False)
                if use_light_control:
                    if "line_signal_monitor_source" in config:
                        try:
                            self.__light_control_subscriber = DMXLightControlSubscriber(self.__pipeline_context, 
                                                                                        connection=config["line_signal_monitor_source"], 
                                                                                        dmx_ip=config["dmx_ip"], dmx_port=config["dmx_port"], 
                                                                                        light_ids=config["light_ids"], topic=config["line_signal_monitor_topic"])
                            self.__light_control_subscriber.start()
                        except Exception as e:
                            self.__console.warning(f"DMX Light Control Subscriber has problem : {e}")
                else:
                    self.__console.warning("Light Control is not enabled")

                # map between camera device and windows
                self.__frame_window_map = {}
                for idx, id in enumerate(config["camera_ids"]):
                    self.__frame_window_map[id] = self.findChild(QLabel, config["camera_windows"][idx])
                    self.__console.info(f"Ready for camera grabber #{id} monitoring")
                    portname = f"image_stream_monitor_source_{id}"
                    self.__console.info("- Start Camera #{id} Monitoring...")
                    self.__camera_image_subscriber_map[id] = CameraMonitorSubscriber(self.__pipeline_context,connection=config[portname],
                                                                                     topic=f"{config['image_stream_monitor_topic_prefix']}{id}")
                    self.__camera_image_subscriber_map[id].frame_update_signal.connect(self.on_update_camera_image)
                    self.__camera_image_subscriber_map[id].start()

                # system alive check requester
                for idx, src in enumerate(config["system_echo_sources"]):
                    _id = src["id"]
                    self.__system_echo_requester_map[_id] = SystemEchoRequester(self.__pipeline_context, connection=src["source"], id=_id, interval_ms=src["interval"])
                    self.__system_echo_requester_map[_id].alive_update_signal.connect(self.on_update_alive)
                    self.__console.info("- Start System Echo Requester...")

                # create sdd inference subscriber
                use_sdd_inference = self.__config.get("use_sdd_inference", False)
                if use_sdd_inference:
                    from subscriber.model_inference import SDDModelInference
                    self.__sdd_inference_subscriber = SDDModelInference(self.__pipeline_context,
                                                                        connection=config["line_signal_monitor_source"],
                                                                        topic=config["line_signal_monitor_topic"],
                                                                        model_config=config["sdd_model_config"],
                                                                        in_path_root=config["sdd_in_root"],
                                                                        out_path_root=config["sdd_out_root"],
                                                                        save_visual=config.get("sdd_inference_save_result_images", False))
                    self.__sdd_inference_subscriber.update_status_signal.connect(self.on_update_sdd_status)
                    self.__sdd_inference_subscriber.processing_result_signal.connect(self.on_update_sdd_result_binary)

        except Exception as e:
            self.__console.error(f"{e}")

    def clear_defect_plot(self):
        self.__frame_defect_grid_plot.clear()

    def clear_temperature_plot(self):
        self.__frame_temperature_grid_plot.clear()

    def on_btn_preset_load(self):
        selected_preset = self.combobox_preset.currentText()

        if selected_preset:
            absolute_path = pathlib.Path(self.__config["preset_path"])/selected_preset
            self.__console.info(f"Selected Preset : {absolute_path}")

            try:
                # file load (json format)
                preset_file = open(absolute_path, encoding='utf-8')
                preset = json.load(preset_file)
                preset_file.close()

                # set focus value
                for lens_id in preset["focus_value"]:
                    edit_focus = self.findChild(QLineEdit, name=f"edit_focus_value_{lens_id}")
                    if edit_focus:
                        edit_focus.setText(str(preset["focus_value"][lens_id]))
                # set camera exposure time
                for camera_id in preset["camera_exposure_time"]:
                    edit_exposure_time = self.findChild(QLineEdit, name=f"edit_exposure_time_value_{camera_id}")
                    if edit_exposure_time:
                        edit_exposure_time.setText(str(preset["camera_exposure_time"][camera_id]))
                # set light value
                for light_id in preset["light_value"]:
                    edit_light_value = self.findChild(QLineEdit, name=f"edit_light_level_value_{light_id}")
                    if edit_light_value:
                        edit_light_value.setText(str(preset["light_value"][light_id]))

            except json.JSONDecodeError as e:
                QMessageBox.critical(self, "Error", f"Preset file load failed. ({e})")
            except FileNotFoundError as e:
                QMessageBox.critical(self, "Error", f"Preset file does not exist. ({absolute_path})")
    
    
    ### change lens focus value
    def on_btn_focus_preset_set_all(self):
        for lens_id in self.__config["camera_ids"]:
            self.on_btn_focus_set(lens_id)

    def on_btn_focus_set(self, id:int):
        if self.__lens_control_publisher:
            focus_value = self.findChild(QLineEdit, name=f"edit_focus_value_{id}").text()
            if focus_value is not None:
                self.__lens_control_publisher.focus_move(lens_id=id, value=int(focus_value))
        else:
            QMessageBox.critical(self, "Error", f"Lens control is not activated. Check your configuration(*.cfg).")

    ### Change for all of camera exposure time
    def on_btn_exposure_time_set_all(self):
        for cam_id in self.__config["camera_ids"]:
            self.__exposure_time_set(cam_id)

    def __exposure_time_set(self, id:int):
        if id in self.__camera_control_publisher_map.keys():
            et_val = self.findChild(QLineEdit, name=f"edit_exposure_time_value_{id}").text()
            if et_val is not None:
                self.__camera_control_publisher_map[id].set_exposure_time(id, float(et_val))
        else:
            QMessageBox.critical(self, "Error", f"Camera #{id} control pipieline is not activated")

    ### Change for all of light level (note!! idx is not a light id)
    def on_btn_light_level_set_all(self):
        brightness = []
        for idx, id in enumerate(self.__config["light_ids"]):
            light_value = self.findChild(QLineEdit, name=f"edit_light_level_value_{idx+1}").text()
            if light_value is not None:
                brightness.append(int(light_value))
            else:
                brightness.append(0)
        self.__light_set(ids=self.__config["light_ids"], values=brightness)

    def __light_set(self, ids:list, values:list):
        self.__light_control_subscriber.set_control_multi(self.__config["dmx_ip"], self.__config["dmx_port"], ids, brightness=values)
    
    def on_btn_light_off(self):
        self.__light_control_subscriber.set_off(self.__config["dmx_ip"], self.__config["dmx_port"], self.__config["light_ids"])


    ### show grabbed images
    def on_update_camera_image(self, camera_id:int, image:np.ndarray):
        """ show image on window for each camera id """
        h, w, ch = image.shape
        qt_image = QImage(image.data, w, h, ch*w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        try:
            self.__frame_window_map[camera_id].setPixmap(pixmap.scaled(self.__frame_window_map[camera_id].size(), Qt.AspectRatioMode.KeepAspectRatio))
            self.__frame_window_map[camera_id].show()
        except Exception as e:
            self.__console.error(e)

    def on_update_alive(self, id:int, alive:bool):
        if id==1: # sdd server mw
            if alive:
                self.set_status_active("label_server_status")
            else:
                self.set_status_inactive("label_server_status")
        elif id==2: # controller mw
            if alive:
                self.set_status_active("label_onsite_controller_status")
            else:
                self.set_status_inactive("label_onsite_controller_status")

    def on_update_sdd_status(self, status:dict):
        try:
            if status.get("working", False):
                self.set_status_active("label_sdd_processing_status")
            else:
                self.set_status_inactive("label_sdd_processing_status")
        except Exception as e:
            self.__console.error(f"SDD Status Update Error : {e}")

    def on_update_sdd_result_multiclass(self, sdd_result_file_path:str, fm_length:int):
        pass

    def on_update_sdd_result_binary(self, sdd_result_file_path:str, fm_length:int):
        # show only boolean(defect or not) result
        self.__frame_defect_grid_plot.clear()
        self.__frame_defect_grid_plot.setXRange(0, fm_length)

        # read csv file
        try:
            with open(sdd_result_file_path, 'r') as csvfile:
                reader = csv.reader(csvfile)
                next(reader)  # skip header
                row_count = sum(1 for row in reader)
                csvfile.seek(0)  # reset reader to the beginning

                reader = csv.reader(csvfile)  # regenerate reader
                next(reader)
                points = []
                for row in reader:
                    match = re.match(r"(\d+)_(\d+)\.jpg", row[0])
                    if not match:
                        continue
                    y = int(match.group(1))
                    x = int(match.group(2))*fm_length/int(row_count//10)
                    try:
                        defect = int(row[6])
                        if defect==1: # defect found
                            points.append({'pos': (x, y), 'brush': 'r', 'size': 5, 'symbol':'s'})
                    except ValueError:
                        self.__console.error(f"Invalid defect value in row {row}")
                        continue

            scatter = graph.ScatterPlotItem()
            scatter.addPoints(points)
            self.__frame_defect_grid_plot.addItem(scatter)
            self.__frame_defect_grid_plot.enableAutoRange(axis=graph.ViewBox.XAxis)
            self.__frame_defect_grid_plot.show()
        except ValueError as e:
            self.__console.error(f"Error reading CSV file {sdd_result_file_path}: {e}")
        except FileNotFoundError as e:
            self.__console.error(f"File not found: {sdd_result_file_path}")

                
                

           
                
    def closeEvent(self, event:QCloseEvent) -> None: 

        # clsoe dmx status observer
        if self.__dmx_status_observer:
            self.__dmx_status_observer.close()
            self.__console.info("Close DMX Status Observer")

        # close nas status observer
        if self.__nas_status_observer:
            self.__nas_status_observer.close()
            self.__console.info("Close NAS Status Observer")

        # close temperature monitor subscriber
        if self.__temperature_monitor_subscriber:
            self.__temperature_monitor_subscriber.close()
            self.__console.info("Close Temperature Subscriber")

        # close level2 data subscriber
        if self.__dk_level2_data_subscriber:
            self.__dk_level2_data_subscriber.close()
            self.__console.info("Close DK Level2 Data Subscriber")

        # close level2 status subscriber
        if self.__dk_level2_status_subscriber:
            self.__dk_level2_status_subscriber.close()
            self.__console.info("Close DK Level2 Status Subscriber")

        # close lens control publisher
        if self.__lens_control_publisher:
            self.__lens_control_publisher.close()
            self.__console.info("Close Lens Control Publisher")

        # close line signal monitoring subscriber
        if self.__line_signal_monitor_subscriber:
            self.__line_signal_monitor_subscriber.close()
            self.__console.info("Close Line Signal Monitor Subscriber")

        # close camera control publisher
        if len(self.__camera_control_publisher_map.keys())>0:
            with ThreadPoolExecutor(max_workers=10) as executor:
                executor.map(lambda publisher: publisher.close(), self.__camera_control_publisher_map.values())

        # close light control requester
        if self.__light_control_subscriber:
            self.__light_control_subscriber.close()
            self.__console.info("Close Light Control Subscriber")

        # close sdd inference subscriber
        if self.__sdd_inference_subscriber:
            self.__sdd_inference_subscriber.close()
            self.__console.info("Close SDD Inference Subscriber")

        # close camera stream monitoring subscriber
        if len(self.__camera_image_subscriber_map.keys())>0:
            with ThreadPoolExecutor(max_workers=10) as executor:
                executor.map(lambda subscriber: subscriber.close(), self.__camera_image_subscriber_map.values())   

        # close cmaera status subscriber
        if self.__camera_status_monitor_subscriber:  
            self.__camera_status_monitor_subscriber.close()
            self.__console.info("Close Camera Status Subscriber")  

        # close echo requester
        for requester in self.__system_echo_requester_map.values():
            requester.close()
            self.__console.info("Close System Echo Requester")
        # context termination with linger=0
        self.__pipeline_context.destroy(0)
            
        return super().closeEvent(event)

    def on_update_temperature(self, values:dict): # key:str, value:str
        try:
            for idx, id in enumerate(values):
                widget = self.findChild(QLabel, name=f"label_temperature_value_{id}")
                if widget:
                    widget.setText(f"{values[id]}")

            # value added
            self.__frame_temperature_x.append(datetime.datetime.now().timestamp()) # append x(time) axis data
            for idx, id in enumerate(self.__config["temperature_ids"]):         # append y(temperature) axis data
                self.__frame_temperature_y[idx].append(float(values[str(id)]))

            # update plot
            for idx, id in enumerate(self.__config["temperature_ids"]):
                self.__frame_temperature_curves[idx].setData(list(self.__frame_temperature_x), list(self.__frame_temperature_y[idx]))

        except Exception as e:
            self.__console.error(f"Temperature update error : {e}")


    def on_update_camera_status(self, status:str):
        """ update camera status """
        try:
            status = json.loads(status)
            sum = 0
            for camera_id in self.__config["camera_ids"]:
                if str(camera_id) in status:
                    sum = sum + status[str(camera_id)]["frames"]
            self.__console.debug(f"{sum}")
            self.label_total_images.setText(str(sum))

        except json.JSONDecodeError as e:
            self.__console.error(f"Camera Status Update Error : {e}")

    def on_update_dk_level2_status(self, data:dict):
        try:
            if data.get("available", False):
                self.set_status_active("label_level2_status")
            else:
                self.set_status_inactive("label_level2_status")
        except Exception as e:
            self.__console.error(f"DK Level2 Status Update Error : {e}")


    def on_update_dk_level2_data(self, data:dict):
        """ update dk level2 data """
        try:
            # display level2 information
            self.label_lotno.setText(data.get("lot_no", "-")) # display lot no
            self.label_mtno.setText(data.get("mt_no", "-")) # display mt no
            self.label_date.setText(data.get("date", datetime.datetime.today().strftime('@%Y-%m-%d-%H-%M-%S'))) # display date
            self.label_mt_stand_height.setText(str(int(data.get("mt_stand_height", 0)/10)))
            self.label_mt_stand_width.setText(str(int(data.get("mt_stand_width", 0)/10)))
            self.label_mt_stand_t1.setText(str(int(data.get("mt_stand_t1", 0)/10)))
            self.label_mt_stand_t2.setText(str(int(data.get("mt_stand_t2", 0)/10)))
            self.label_fm_length.setText(str(data.get("fm_length", 0)))

            # load nearest preset file
            near_preset = self.__find_nearest_preset(h=int(data.get("mt_stand_height", 0)/10),
                                                     b=int(data.get("mt_stand_width", 0)/10),
                                                     filenames=self.__preset_files)
            if near_preset:
                self.combobox_preset.setCurrentText(near_preset)
                self.__console.info(f"Selected Nearest Preset : {near_preset}")
                self.on_btn_preset_load()
                if self.__config.get("use_nearest_preset_auto_select",False):
                    if self.__last_preset_file!=near_preset and self.__system_online: # set all if system is online
                        self.__console.info("Set focus, exposure time and light level by LV2 data")
                        self.on_btn_exposure_time_set_all()
                        time.sleep(0.1)
                        self.on_btn_light_level_set_all()
                        time.sleep(0.1)
                        self.on_btn_focus_preset_set_all()
                        self.__last_preset_file = near_preset
                    else:
                        self.__console.info(f"Preset file that was previously applied is currently in use {self.__last_preset_file}")
                
            else:
                self.__console.warning("Cannot found nearest preset file")

        except Exception as e:
            self.__console.error(f"DK Level2 Data Update Error : {e}")
        
    def on_update_line_signal(self, data:dict):
        """ update library signal status """
        try:
            # online signal
            if data.get("online_signal_on", False):
                self.set_status_active("label_line_signal_status")
                self.__system_online = True
            else:
                self.set_status_inactive("label_line_signal_status")
                self.__system_online = False

            # HMD signal 1
            if data.get("hmd_signal_1_on", False):
                self.set_status_active("label_hmd_signal_1_status")
            else:
                self.set_status_inactive("label_hmd_signal_1_status")

            # HMD signal 2
            if data.get("hmd_signal_2_on", False):
                self.set_status_active("label_hmd_signal_2_status")
            else:
                self.set_status_inactive("label_hmd_signal_2_status")

        except Exception as e:
            self.__console.error(f"Line Signal Update Error : {e}")

    def on_update_nas_status(self, status:dict):
        try:
            if status.get("available", False):
                self.set_status_active("label_nas_status")
            else:
                self.set_status_inactive("label_nas_status")
        except Exception as e:
            self.__console.error(f"DK Level2 Status Update Error : {e}")

    def on_update_dmx_status(self, status:dict):
        try:
            if status.get("available", False):
                self.set_status_active("label_dmx_status")
            else:
                self.set_status_inactive("label_dmx_status")
        except Exception as e:
            self.__console.error(f"DK Level2 Status Update Error : {e}")

    def on_update_temperature_status(self, msg:str): # update temperature control monitoring pipeline status
        self.label_temp_monitor_pipeline_message.setText(msg)
        
    
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
                self.__light_control_subscriber.set_control(self.__config["dmx_ip"], self.__config["dmx_port"], self.__config["light_ids"], value)
            else:
                QMessageBox.critical(self, "Error", f"DMX IP and Port is not defined")
        else:
            value = int(self.label_light_control_value.text())
            QMessageBox.critical(self, "Error", f"Light control did not activated. value is {value}")
    
    def set_status_active(self, label_name:str):
        """ change background color to green for active status """
        label_object = self.findChild(QLabel, name=label_name)
        if label_object:
            label_object.setStyleSheet("background-color: #00FF00; color: black")

    def set_status_inactive(self, label_name:str):
        """ change background color to red for inactive status """
        label_object = self.findChild(QLabel, name=label_name)
        if label_object:
            label_object.setStyleSheet("background-color: #FF0000; color: white")

    def set_status_warning(self, label_name:str):
        """ change background color to yellow for warning status """
        label_object = self.findChild(QLabel, name=label_name)
        if label_object:
            label_object.setStyleSheet("background-color: yellow; color: black")

    def update_total_image_count(self, count:int):
        """ update total image count """
        self.label_total_images.setText(str(count))

    def __parse_filename(self, filename: str) -> Tuple[int, int]:
        match = re.match(r"(\d+)_(\d+)\.preset$", filename)
        if match:
            height, width = map(int, match.groups())
            return height, width
        return None
    def __find_nearest_preset(self, h:int, b:int, filenames:List[str]) -> str:
        min_distance = float('inf')
        nearest_file = None

        for filename in filenames:
            parsed = self.__parse_filename(filename)
            if parsed:
                height, width = parsed
                distance = (height - h)**2 + (width - b)**2
                if distance < min_distance:
                    min_distance = distance
                    nearest_file = filename

        return nearest_file

