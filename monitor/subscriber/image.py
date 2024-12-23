"""
Image Data Subscriber
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

class ImageSubscriber(QThread):
    
    frame_update_signal = pyqtSignal(int, np.ndarray, float)

    def __init__(self, camera_id:int):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger