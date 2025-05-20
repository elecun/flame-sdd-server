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
from subscriber.camera_status import CameraStatusMonitorSubscriber
from publisher.lens_control import LensControlPublisher
from publisher.camera_control import CameraControlPublisher
from publisher.line_signal import LineSignalPublisher
from subscriber.line_signal import LineSignalSubscriber
from subscriber.dmx_light_control import DMXLightControlSubscriber
from subscriber.camera import CameraMonitorSubscriber
from subscriber.dk_level2 import DKLevel2DataSubscriber
from subscriber.dk_level2_status import DKLevel2StatusSubscriber
from requester.system_alive import SystemAliveRequester

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
        self.__line_signal_monitor_subscriber = None        # line signal status monitor subscriber
        self.__light_control_subscriber = None              # light control subscriber
        self.__dk_level2_data_subscriber = None             # level2 data subscriber
        self.__camera_image_subscriber_map = {}             # camera image subscriber
        self.__lens_control_publisher = None                # lens control publisher
        self.__camera_control_publisher_map = {}            # camera control publishers
        self.__system_alive_requester_map = {}              # system requester

        # variables
        self.__total_frames = 0

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
                self.__frame_defect_grid_plot.setLabel("bottom", "Frame Counts", **styles)
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
                self.btn_inference_model_apply.clicked.connect(self.on_btn_inference_model_apply)               # change sdd model


                # checkbox callback functions
                self.check_option_save_level2_info.stateChanged.connect(self.on_check_option_save_level2_info)
                self.check_option_save_temperature.stateChanged.connect(self.on_check_option_save_temperature)
                self.check_inference_batch_processing.stateChanged.connect(self.on_check_inference_batch_processing)
                self.check_inference_save_results.stateChanged.connect(self.on_check_inference_save_results)

                # default status indication
                self.set_status_inactive("label_onsite_controller_status")
                self.set_status_inactive("label_server_status")
                self.set_status_inactive("label_level2_status")
                self.set_status_inactive("label_light_controller_status")
                self.set_status_inactive("label_nas_status")
                self.set_status_inactive("label_line_signal_status")
                self.set_status_inactive("label_hmd_signal_1_status")
                self.set_status_inactive("label_hmd_signal_2_status")
                self.set_status_inactive("label_sdd_processing_status")               

                # find preset files in preset directory (default : ./bin/preset)
                self.__config["preset_path"] = (pathlib.Path(self.__config["root_path"]) / "bin" / "preset").as_posix()
                if os.path.exists(pathlib.Path(self.__config["preset_path"])):
                    preset_files = [f for f in os.listdir(self.__config["preset_path"])]
                    for preset in preset_files:
                        self.combobox_preset.addItem(preset)

                # find sdd model files in model directory (default : sdd_default.py)
                self.__config["model_path"] = (pathlib.Path(self.__config["root_path"]) / "bin" / "model").as_posix()
                if os.path.exists(pathlib.Path(self.__config["model_path"])):
                    model_files = [f for f in os.listdir(self.__config["model_path"])]
                    for model in model_files:
                        self.combobox_inference_sdd_model.addItem(model)

                # create temperature monitoring subscriber
                use_temperature_monitor = self.__config.get("use_temperature_monitor", False)
                if use_temperature_monitor:
                    if "temp_stream_source" in config and "temp_stream_sub_topic" in config:
                        try:
                            self.__temperature_monitor_subscriber = TemperatureMonitorSubscriber(self.__pipeline_context, 
                                                                                                 connection=config["temp_stream_source"], 
                                                                                                 topic=config["temp_stream_sub_topic"])
                            self.__temperature_monitor_subscriber.temperature_update_signal.connect(self.on_update_temperature)
                            self.__temperature_monitor_subscriber.start() # run in thread
                        except Exception as e:
                            self.__console.warning(f"Temperature Monitor has problem : {e}")
                else:
                    self.__console.warning("Temperature Monitor is not enabled")

                # dk level2 data monitoring subscriber
                use_dk_level2_interface = self.__config.get("use_dk_level2_interface", False)
                if use_dk_level2_interface:
                    if "dk_level2_interface_source" in config and "dk_level2_interface_sub_topic" in config:
                        self.__dk_level2_data_subscriber = DKLevel2DataSubscriber(self.__pipeline_context, 
                                                                                  connection=config["dk_level2_interface_source"], 
                                                                                  topic=config["dk_level2_interface_sub_topic"])
                        self.__dk_level2_data_subscriber.level2_data_update_signal.connect(self.on_update_dk_level2_data)
                        self.__dk_level2_data_subscriber.start()
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
                            self.__light_control_subscriber.dmx_alive_signal.connect(self.on_update_dmx_light_control)
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
                for idx, src in enumerate(config["system_echo_source"]):
                    self.__system_alive_requester_map[src["id"]] = SystemAliveRequester(self.__pipeline_context, connection=src["source"], alive_msg=src["echo"])
                    self.__system_alive_requester_map[src["id"]].alive_update_signal.connect(partial(self.on_update_alive, src["id"], src["name"]))
                    self.__console.info("- Start System Echo Requester...")
                

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
        self.__light_set(ids=self.__config["light_ids"], value=brightness)

    def __light_set(self, ids:list, values:list):
        self.__light_control_subscriber.set_control_multi(self.__config["dmx_ip"], self.__config["dmx_port"], ids, brightness=values)
    
    def on_btn_light_off(self):
        self.__light_control_subscriber.set_off(self.__config["dmx_ip"], self.__config["dmx_port"], self.__config["light_ids"])
    
    def on_btn_inference_model_apply(self):
        selected_model = self.combobox_inference_sdd_model.currentText()

        if selected_model:
            absolute_path = pathlib.Path(self.__config["model_path"])/selected_model
            self.__console.info(f"Selected Model : {absolute_path}")

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

    ### checkbox options
    def on_check_option_save_level2_info(self, state):
        # online_checked = self.check_online_signal.isChecked()
        pass

    def on_check_option_save_temperature(self, state):
        pass

    
    def on_check_inference_batch_processing(self, state):
        pass

    def on_check_inference_save_results(self, state):
        pass



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

    def on_update_alive(self, id:int, name:str):
        if id==1: # sdd server mw
            pass
        elif id==2: # controller mw
            pass
                
    def closeEvent(self, event:QCloseEvent) -> None: 

        # close temperature monitor subscriber
        if self.__temperature_monitor_subscriber:
            self.__temperature_monitor_subscriber.close()
            self.__console.info("Close Temperature Subscriber")

        # close level2 data subscriber
        if self.__dk_level2_data_subscriber:
            self.__dk_level2_data_subscriber.close()
            self.__console.info("Close DK Level2 Data Subscriber")

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

        # close camera stream monitoring subscriber
        if len(self.__camera_image_subscriber_map.keys())>0:
            with ThreadPoolExecutor(max_workers=10) as executor:
                executor.map(lambda subscriber: subscriber.close(), self.__camera_image_subscriber_map.values())       

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
            self.__total_frames = 0
            for camera_id in self.__config["camera_ids"]:
                if str(camera_id) in status:
                    self.__total_frames = self.__total_frames + status[str(camera_id)]["frames"]
            
            self.label_total_images.setText(str(self.__total_frames))

        except json.JSONDecodeError as e:
            self.__console.error(f"Camera Status Update Error : {e.waht()}")

    def on_update_dk_level2_status(self, data:dict):
        try:
            if "level2_connect" in data:
                if data["level2_connect"]:
                    self.set_status_active("label_level2_status")
                else:
                    self.set_status_inactive("label_level2_status")
        except json.JSONDecodeError as e:
            self.__console.error(f"DK Level2 Status Update Error : {e.waht()}")


    def on_update_dk_level2_data(self, data:dict):
        """ update dk level2 data """
        try:
            # display lot no
            if "lot_no" in data:
                self.label_lotno.setText(data["lot_no"])
            else:
                self.label_lotno.setText("-")

            # display mt. no
            if "mt_no" in data:
                self.label_mtno.setText(data["mt_no"])
            else:
                self.label_mtno.setText("-")

            # display date
            if "date" in data:
                self.label_date.setText(data["date"])
            else:
                self.label_date.setText("-")

            # display mt stand height
            if "mt_stand_height" in data:
                self.label_mt_stand_height.setText(str(int(data["mt_stand_height"]/10)))
            else:
                self.label_mt_stand_height.setText("-")

            # display mt stand width
            if "mt_stand_width" in data:
                self.label_mt_stand_width.setText(str(int(data["mt_stand_width"]/10)))
            else:
                self.label_mt_stand_width.setText("-")

            # display mt stand t1
            if "mt_stand_t1" in data:
                self.label_mt_stand_t1.setText(str(int(data["mt_stand_t1"]/10)))
            else:
                self.label_mt_stand_t1.setText("-")

            # display mt stand t2
            if "mt_stand_t2" in data:
                self.label_mt_stand_t2.setText(str(int(data["mt_stand_t2"]/10)))
            else:
                self.label_mt_stand_t2.setText("-")

            # display fm length
            if "fm_length" in data:
                self.label_fm_length.setText(str(data["fm_length"]))
            else:
                self.label_fm_length.setText("-")

        except json.JSONDecodeError as e:
            self.__console.error(f"DK Level2 Data Update Error : {e.waht()}")
        
    def on_update_line_signal(self, data:dict):
        """ update library signal status """
        try:
            # online signal
            if "online_signal_on" in data:
                if data["online_signal_on"]:
                    self.set_status_active("label_line_signal_status")
                else:
                    self.set_status_inactive("label_line_signal_status")

            # HMD signal 1
            if "hmd_signal_1_on" in data:
                if data["hmd_signal_1_on"]:
                    self.set_status_active("label_hmd_signal_1_status")
                else:
                    self.set_status_inactive("label_hmd_signal_1_status")

            # HMD signal 2
            if "hmd_signal_2_on" in data:
                if data["hmd_signal_2_on"]:
                    self.set_status_active("label_hmd_signal_2_status")
                else:
                    self.set_status_inactive("label_hmd_signal_2_status")

        except json.JSONDecodeError as e:
            self.__console.error(f"Line Signal Update Error : {e.what()}")

    def on_update_dmx_light_control(self, data:str):
        """ update dmx light status """
        try:
            if "alive" in data:
                if data["alive"]:
                    self.set_status_active("label_light_controller_status")
                else:
                    self.set_status_inactive("label_light_controller_status")
        except json.JSONDecodeError as e:
            self.__console.error(f"DMX Light Status Update Error : {e.what()}")

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

