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
from subscriber.camera_status import CameraStatusMonitorSubscriber
from publisher.lens_control import LensControlPublisher
from publisher.camera_control import CameraControlPublisher
from publisher.line_signal import LineSignalPublisher
from subscriber.line_signal import LineSignalSubscriber
from subscriber.dmx_light_control import DMXLightControlSubscriber
from subscriber.camera import CameraMonitorSubscriber
from subscriber.dk_level2 import DKLevel2DataSubscriber

class AppWindow(QMainWindow):
    def __init__(self, config:dict):
        """ initialization """
        super().__init__()
        
        self.__console = ConsoleLogger.get_logger() # logger
        self.__config = config  # copy configuration data
        self.__pipeline_context = zmq.Context(14) # zmq context

        self.__frame_defect_grid_layout = QVBoxLayout()
        self.__frame_defect_grid_plot = graph.PlotWidget()

        # device/service control interfaces
        self.__temp_monitor_subscriber = None
        self.__camera_status_monitor_subscriber = None
        self.__lens_control_publisher = None
        self.__hmd_signal_control_publisher = None
        self.__line_signal_control_publisher = None
        self.__line_signal_monitor_subscriber = None
        self.__light_control_subscriber = None
        self.__dk_level2_data_subscriber = None
        self.__camera_image_subscriber_map = {}
        self.__camera_control_publisher_map = {}

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
                self.btn_exposure_time_set_1.clicked.connect(partial(self.on_btn_exposure_time_set, 1))
                self.btn_exposure_time_set_2.clicked.connect(partial(self.on_btn_exposure_time_set, 2))
                self.btn_exposure_time_set_3.clicked.connect(partial(self.on_btn_exposure_time_set, 3))
                self.btn_exposure_time_set_4.clicked.connect(partial(self.on_btn_exposure_time_set, 4))
                self.btn_exposure_time_set_5.clicked.connect(partial(self.on_btn_exposure_time_set, 5))
                self.btn_exposure_time_set_6.clicked.connect(partial(self.on_btn_exposure_time_set, 6))
                self.btn_exposure_time_set_7.clicked.connect(partial(self.on_btn_exposure_time_set, 7))
                self.btn_exposure_time_set_8.clicked.connect(partial(self.on_btn_exposure_time_set, 8))
                self.btn_exposure_time_set_9.clicked.connect(partial(self.on_btn_exposure_time_set, 9))
                self.btn_exposure_time_set_10.clicked.connect(partial(self.on_btn_exposure_time_set, 10))
                self.btn_focus_read_all.clicked.connect(self.on_btn_focus_read_all)
                self.btn_focus_initialize_all.clicked.connect(self.on_btn_focus_initialize_all)
                self.btn_focus_preset_set_all.clicked.connect(self.on_btn_focus_preset_set_all)
                self.btn_focus_preset_load.clicked.connect(self.on_btn_focus_preset_load)
                self.check_online_signal.stateChanged.connect(self.on_check_online_signal)
                self.check_offline_signal.stateChanged.connect(self.on_check_offline_signal)
                self.check_hmd_signal.clicked.connect(self.on_check_hmd_signal)
                self.btn_light_control_off.clicked.connect(self.on_btn_light_control_off)

                # register dial event callback function
                self.dial_light_control.valueChanged.connect(self.on_change_light_control)
                self.dial_light_control.sliderReleased.connect(self.on_set_light_control)

                # default status indication
                self.set_status_inactive("label_onsite_controller_status")
                self.set_status_inactive("label_level2_status")
                self.set_status_inactive("label_camera_status")
                self.set_status_inactive("label_lens_status")
                self.set_status_inactive("label_nas_status")
                self.set_status_inactive("label_light_controller_status")
                self.set_status_inactive("label_hmd_signal_1_status")
                self.set_status_inactive("label_hmd_signal_2_status")
                self.set_status_inactive("label_line_signal_status")

                # find focus preset files in preset directory
                #preset_path = pathlib.Path(config["app_path"])/pathlib.Path(config["preset_path"])
                self.__config["preset_path"] = pathlib.Path(config["preset_path"]).as_posix()
                #self.__config["preset_path"] = preset_path.as_posix()
                self.__console.info(f"+ Preset Path : {config["preset_path"]}")
                if os.path.exists(pathlib.Path(config["app_path"])):
                    preset_files = [f for f in os.listdir(config["preset_path"])]
                    for preset in preset_files:
                        self.combobox_focus_preset.addItem(preset)

                # create temperature monitoring subscriber
                if "use_temperature_monitor" in config and config["use_temperature_monitor"]:
                    if "temp_stream_source" in config and "temp_stream_sub_topic" in config:
                        try:
                            self.__console.info("+ Create Temperature Monitoring Subscriber...")
                            self.__temp_monitor_subscriber = TemperatureMonitorSubscriber(self.__pipeline_context, connection=config["temp_stream_source"], topic=config["temp_stream_sub_topic"])
                            self.__temp_monitor_subscriber.temperature_update_signal.connect(self.on_update_temperature)
                            self.__temp_monitor_subscriber.start() # run in thread
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
                        self.__camera_status_monitor_subscriber.start() # run in thread

                # dk level2 data monitoring subscriber
                if "use_dk_level2_interface" in config and config["use_dk_level2_interface"]:
                    if "dk_level2_interface_source" in config and "dk_level2_interface_sub_topic" in config:
                        self.__console.info("+ Create DK Level2 Data Subscriber...")
                        self.__dk_level2_data_subscriber = DKLevel2DataSubscriber(self.__pipeline_context, connection=config["dk_level2_interface_source"], topic=config["dk_level2_interface_sub_topic"])
                        self.__dk_level2_data_subscriber.level2_data_update_signal.connect(self.on_update_dk_level2_data)
                        self.__dk_level2_data_subscriber.start()
                else:
                    self.__console.warning("DK Level2 Data Interface is not enabled")

                # create lens control publisher
                if "use_lens_control" in config and config["use_lens_control"]:
                    if "lens_control_source" in config:
                        try:
                            self.__console.info("+ Create Lens Control Publisher...")
                            self.__lens_control_publisher = LensControlPublisher(self.__pipeline_context, connection=config["lens_control_source"])
                        except Exception as e:
                            self.__console.warning(f"Lens Control Publisher has problem : {e}")
                else:
                    self.__console.warning("Lens Control is not enabled.")

                # create line(online, offline) control publisher
                if "use_line_signal_control" in config and config["use_line_signal_control"]:
                    if "line_signal_control_source" in config:
                        self.__console.info("+ Create Line Signal Control Publisher...")
                        self.__line_signal_control_publisher = LineSignalPublisher(self.__pipeline_context, connection=config["line_signal_control_source"])
                else:
                    self.__console.warning("Line Signal Control is not enabled.")
                
                # create line signal monitoring subscriber
                if "use_line_signal_monitor" in config and config["use_line_signal_monitor"]:
                    if "line_signal_monitor_source" in config and "line_signal_monitor_topic" in config:
                        self.__console.info("+ Create Line Signal Monitoring Subscriber...")
                        self.__line_signal_monitor_subscriber = LineSignalSubscriber(self.__pipeline_context, connection=config["line_signal_monitor_source"], topic=config["line_signal_monitor_topic"])
                        self.__line_signal_monitor_subscriber.line_signal.connect(self.on_update_line_signal)
                        self.__line_signal_monitor_subscriber.start()
                else:
                    self.__console.warning("Line Signal Monitor is not enabled")
                        
                # create camera control publisher
                if "use_camera_control" in config and config["use_camera_control"]:
                    for idx, id in enumerate(config["camera_ids"]):
                        portname = f"camera_control_source_{id}"
                        self.__console.info("+ Create Camera #{id} Control Publisher...")
                        self.__camera_control_publisher_map[id] = CameraControlPublisher(self.__pipeline_context, connection=config[portname])
                else:
                    self.__console.warning("Camera Control is not enabled.")

                # create light control requester (!!! control by line signal)
                if "use_light_control" in config and config["use_light_control"]:
                    if "line_signal_monitor_source" in config:
                        try:
                            self.__console.info("+ Create DMX Light Control Subscriber")
                            self.__light_control_subscriber = DMXLightControlSubscriber(self.__pipeline_context, connection=config["line_signal_monitor_source"], 
                                                                                        dmx_ip=config["dmx_ip"], dmx_port=config["dmx_port"], 
                                                                                        light_ids=config["light_ids"], topic=config["line_signal_monitor_topic"])
                            self.__light_control_subscriber.dmx_alive_signal.connect(self.on_update_dmx_light_status)
                            self.__light_control_subscriber.start()
                            self.__console.info("+ Create DMX Light Control Subscriber....")
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
                    self.__console.info("+ Create Camera #{id} Monitoring Subscriber...")
                    self.__camera_image_subscriber_map[id] = CameraMonitorSubscriber(self.__pipeline_context,connection=config[portname],
                                                                                     topic=f"{config['image_stream_monitor_topic_prefix']}{id}")
                    self.__camera_image_subscriber_map[id].frame_update_signal.connect(self.on_update_camera_image)
                    self.__camera_image_subscriber_map[id].start()

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

    def on_btn_focus_preset_load(self):
        """ load focus preset """
        selected_preset = self.combobox_focus_preset.currentText()

        if selected_preset:
            absolute_path = pathlib.Path(self.__config["preset_path"])/selected_preset
            self.__console.info(f"Selected Focus Lens Control preset : {absolute_path}")

            try:
                # file load (json format)
                preset_file = open(absolute_path, encoding='utf-8')
                focus_preset = json.load(preset_file)
                preset_file.close()

                # apply to the gui
                for lens_id in focus_preset["focus_value"]:
                    edit_focus = self.findChild(QLineEdit, name=f"edit_focus_value_{lens_id}")
                    if edit_focus:
                        edit_focus.setText(str(focus_preset["focus_value"][lens_id]))

            except json.JSONDecodeError as e:
                self.__console.error(f"Focus Preset Load Error : {e}")
            except FileNotFoundError as e:
                self.__console.error(f"{absolute_path} File not found")
    
    
    def on_btn_focus_preset_set_all(self):
        """ set focus preset for all lens """
        for lens_id in self.__config["camera_ids"]:
            self.on_btn_focus_set(lens_id)
    
    def __check_line_signal(self):
        """ check & set line signal """
        online_checked = self.check_online_signal.isChecked()
        offline_checked = self.check_offline_signal.isChecked()
        hmd_checked = self.check_hmd_signal.isChecked()
        if self.__line_signal_control_publisher:
            self.__line_signal_control_publisher.set_line_signal(online_checked, offline_checked,hmd_checked)
        else:
            self.__console.error("Line Signal Control Publisher is None")

    def on_check_online_signal(self, state):
        """ online signal control """
        self.__check_line_signal()
            
    def on_check_offline_signal(self, state):
        """ offline signal control """
        self.__check_line_signal

    def on_check_hmd_signal(self, state):
        """ hmd signal control """
        self.__check_line_signal()

    def on_change_light_control(self, value):
        """ control value update """
        self.label_light_control_value.setText(str(value))
    
    def on_btn_light_control_off(self):
        """ light off """
        self.__light_control_subscriber.set_off(self.__config["dmx_ip"], self.__config["dmx_port"], self.__config["light_ids"])
        self.label_light_control_value.setText("0")
        self.dial_light_control.setValue(0)


    def on_btn_focus_set(self, id:int):
        """ focus move control """
        if self.__lens_control_publisher:
            focus_value = self.findChild(QLineEdit, name=f"edit_focus_value_{id}").text()
            self.__lens_control_publisher.focus_move(lens_id=id, value=int(focus_value))
        else:
            self.statusBar().showMessage(f"Lens control pipeline cannot be found")

    def on_btn_exposure_time_set(self, id:int):
        """ camera exposure time control """
        if id in self.__camera_control_publisher_map.keys():
            et_val = self.findChild(QLineEdit, name=f"edit_exposure_time_value_{id}").text()
            self.__camera_control_publisher_map[id].set_exposure_time(id, float(et_val))
        else:
            self.statusBar().showMessage(f"Camera #{id} control pipeline cannot be found")
            
    
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
            cv2.line(image, (cx, 0), (cx, h), (0, 255, 0), 1) #(960, 0) (960, 1920)
            cv2.line(image, (0, cy), (w, cy), (0, 255, 0), 1) # 

        qt_image = QImage(image.data, w, h, ch*w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        try:
            self.__frame_window_map[camera_id].setPixmap(pixmap.scaled(self.__frame_window_map[camera_id].size(), Qt.AspectRatioMode.KeepAspectRatio))
            self.__frame_window_map[camera_id].show()
        except Exception as e:
            self.__console.error(e)
    
                
    def closeEvent(self, event:QCloseEvent) -> None: 
        """ terminate main window """      

        # close light control requester
        if self.__light_control_subscriber:
            self.__light_control_subscriber.close()
            self.__console.info("Close Light Control Subscriber")

        # close lens control publisher
        if self.__lens_control_publisher:
            self.__lens_control_publisher.close()
            self.__console.info("Close Lens Control Publisher")

        # close hmd signal control publisher
        if self.__hmd_signal_control_publisher:
            self.__hmd_signal_control_publisher.close()
            self.__console.info("Close HMD Signal Control Publisher")

        # close line signal control publisher
        if self.__line_signal_control_publisher:
            self.__line_signal_control_publisher.close()
            self.__console.info("Close Line Signal Control Publisher")

        # close line signal monitoring subscriber
        if self.__line_signal_monitor_subscriber:
            self.__line_signal_monitor_subscriber.close()
            self.__console.info("Close Line Signal Monitor Subscriber")

        # close temperature monitor subscriber
        if self.__temp_monitor_subscriber:
            self.__temp_monitor_subscriber.close()
            self.__console.info("Close Temperature Subscriber")

        # close level2 data subscriber
        if self.__dk_level2_data_subscriber:
            self.__dk_level2_data_subscriber.close()
            self.__console.info("Close DK Level2 Data Subscriber")
    
        # close camera status monitor subscriber
        if self.__camera_status_monitor_subscriber:
            self.__camera_status_monitor_subscriber.close()
            self.__console.info("Close Camera Status Monitor Subscriber")

        # close camera stream monitoring subscriber
        if len(self.__camera_image_subscriber_map.keys())>0:
            with ThreadPoolExecutor(max_workers=10) as executor:
                executor.map(lambda subscriber: subscriber.close(), self.__camera_image_subscriber_map.values())

        # close camera control publisher
        if len(self.__camera_control_publisher_map.keys())>0:
            with ThreadPoolExecutor(max_workers=10) as executor:
                executor.map(lambda publisher: publisher.close(), self.__camera_control_publisher_map.values())

        # context termination with linger=0
        self.__pipeline_context.destroy(0)
            
        return super().closeEvent(event)

    def on_update_temperature(self, values:dict):
        """ update temperature value in GUI """
        try:
            if "1" in values:   
                self.label_temperature_value_1.setText(str(values["1"]))
            if "2" in values:
                self.label_temperature_value_2.setText(str(values["2"]))
            if "3" in values:
                self.label_temperature_value_3.setText(str(values["3"]))
            if "4" in values:
                self.label_temperature_value_4.setText(str(values["4"]))
            if "5" in values:
                self.label_temperature_value_5.setText(str(values["5"]))
            if "6" in values:
                self.label_temperature_value_6.setText(str(values["6"]))
            if "7" in values:
                self.label_temperature_value_7.setText(str(values["7"]))
            if "8" in values:
                self.label_temperature_value_8.setText(str(values["8"]))
        except Exception as e:
            pass

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

    def on_update_dk_level2_data(self, data:dict):
        """ update dk level2 data """
        try:
            # display lot no
            if "lot_no" in data:
                self.label_lotno.setText(data["lot_no"])
            else:
                self.label_lotno.setText("-")

            # display mt stand height
            if "mt_stand_height" in data:
                self.label_mt_stand_height.setText(str(data["mt_stand_height"]))
            else:
                self.label_mt_stand_height.setText("-")

            # display mt stand width
            if "mt_stand_width" in data:
                self.label_mt_stand_width.setText(str(data["mt_stand_width"]))
            else:
                self.label_mt_stand_width.setText("-")

            # display mt stand t1
            if "mt_stand_t1" in data:
                self.label_mt_stand_t1.setText(str(data["mt_stand_t1"]))
            else:
                self.label_mt_stand_t1.setText("-")

            # display mt stand t2
            if "mt_stand_t1" in data:
                self.label_mt_stand_t2.setText(str(data["mt_stand_t2"]))
            else:
                self.label_mt_stand_t2.setText("-")

            # display fm length
            if "fm_length" in data:
                self.label_fm_length.setText(str(data["fm_length"]))
            else:
                self.label_fm_length.setText("-")

        except json.JSONDecodeError as e:
            self.__console.error(f"Camera Status Update Error : {e.waht()}")
        
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

    def on_update_dmx_light_status(self, data:str):
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

