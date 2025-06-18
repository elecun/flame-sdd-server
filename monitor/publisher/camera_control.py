"""
Camera Control Publisher
@author Byunghun Hwang <bh.hwang@iae.re.kr>
"""

try:
    # using PyQt5
    from PyQt5.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
    from PyQt6.QtGui import QImage
except ImportError:
    # using PyQt6
    from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
    from PyQt6.QtGui import QImage

import zmq
import zmq.asyncio
import asyncio
import zmq.utils.monitor as zmq_monitor
from util.logger.console import ConsoleLogger
import json
import threading
import time
from typing import Any, Dict
from functools import partial


class CameraControlPublisher(QObject):
    """ Publisher for Camera Control """

    set_exposure_time_signal = pyqtSignal(float) # signal for set exposure time

    def __init__(self, context:zmq.Context, connection:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"+ Camera Controller connection : {connection}")

        self.__connection = connection # connection info.

        # create context for zmq requester
        self.__socket = context.socket(zmq.PUB)
        self.__socket.setsockopt(zmq.RCVBUF .RCVHWM, 100)
        self.__socket.setsockopt(zmq.LINGER, 0)
        self.__socket.bind(connection)

        self.__console.info("* Start Camera Control Publisher")
    
    def get_connection_info(self) -> str:
        """ get connection info """
        return self.__connection
    
    def set_exposure_time(self, camera_id:int, value:float):
        """ set camera exposure time """
        try:
            topic = f"camera_control_{camera_id}"
            message = {
                "function":"set_exposure_time",
                "id":camera_id,
                "value":value
            }
            jmsg = json.dumps(message)
            self.__console.info(jmsg)
            self.__socket.send_multipart([topic.encode(), jmsg.encode()])
            self.__console.info(f"Publish Camera ExposureTime Control : Camera-ID {camera_id}, E.Time {value}")

        except zmq.ZMQError as e:
            self.__console.error(f"<Camera Control> {e}")

    
    def close(self):
        """ close the socket """
        try:
            self.__socket.close()
        except Exception as e:
            self.__console.error(f"{e}")
        except zmq.ZMQError as e:
            self.__console.error(f"Context termination error : {e}")