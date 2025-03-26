"""
HMD Signal Control Publisher
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


class LineSignalPublisher(QObject):
    """ Publisher for Line Status(On/Offline) Signal Control """

    def __init__(self, context:zmq.Context, connection:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"+ Line Status Signal Connection : {connection}")

        self.__connection = connection # connection info.

        # create context for zmq requester
        self.__socket = context.socket(zmq.PUB)
        self.__socket.setsockopt(zmq.RCVBUF .RCVHWM, 1000)
        self.__socket.setsockopt(zmq.LINGER, 0)
        self.__socket.bind(connection)

        self.__console.info("* Start Line Status Signal Control Publisher")
    
    def get_connection_info(self) -> str:
        """ get connection info """
        return self.__connection
    
    def set_line_signal(self, online_signal:bool, offline_signal:bool, hmd_signal:bool):
        """ set line signal"""
        try:
            topic = "ni_daq_controller/line_signal"
            message = {"online_signal_on":online_signal, "offline_signal_on":offline_signal, "hmd_signal_on":hmd_signal}
            jmsg = json.dumps(message)

            self.__socket.send_multipart([topic.encode(), jmsg.encode()])
            self.__console.info(f"Publish Line Signal Control : {message}")
        except zmq.ZMQError as e:
            self.__console.error(f"<Line Signal Control> {e}")
    
    def close(self):
        """ close the socket """
        try:
            self.__socket.close()
        except Exception as e:
            self.__console.error(f"{e}")
        except zmq.ZMQError as e:
            self.__console.error(f"Context termination error : {e}")