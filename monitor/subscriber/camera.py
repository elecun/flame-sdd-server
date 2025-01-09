"""
Camera Monitor subscriber
@author Byunghun Hwang <bh.hwang@iae.re.kr>
"""

from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QImage
import cv2
from datetime import datetime
import platform
from util.logger.console import ConsoleLogger
import numpy as np
from typing import Tuple
import csv
import pathlib


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

class CameraMonitorSubscriber(QThread):
    
    frame_update_signal = pyqtSignal(int, np.ndarray, float)

    def __init__(self, connection:str, topic:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"Camera Monitor node connection : {connection} with {topic}")

        # store parameters
        self.__connection = connection
        self.__topic = topic

        # initialize zmq
        self.__context = zmq.Context()
        self.__socket = self.__context.socket(zmq.SUB)
        self.__socket.connect(connection)
        self.__socket.subscribe(topic)

        self.__console.info("Start Camera Monitor Subscriber")

    def run(self):
        pass

    def close(self) -> None:
        """ Close the socket and context """
        self.requestInterruption()
        self.quit()
        self.wait(500)

        self.__socket.close()
        self.__context.term()
