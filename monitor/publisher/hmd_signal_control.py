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


class HMDSignalControlPublisher(QObject):
    """ Publisher for HDM Signal Control """

    def __init__(self, context:zmq.Context, connection:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"+ HMD Signal Controller connection : {connection}")

        self.__connection = connection # connection info.

        # create context for zmq requester
        self.__socket = context.socket(zmq.PUB)
        self.__socket.setsockopt(zmq.SNDHWM, 100)
        self.__socket.setsockopt(zmq.SNDBUF, 1000)
        self.__socket.setsockopt(zmq.LINGER, 0)
        self.__socket.bind(connection)

        self.__console.info("* Start HMD Signal Control Publisher (Test Only)")
    
    def get_connection_info(self) -> str:
        """ get connection info """
        return self.__connection
    
    def set_signal_on(self, signal_1_on:bool, signal_2_on:bool):
        """ set signal on """
        try:
            topic = "hmd_signal"
            message = {"hmd_signal_1_on":signal_1_on, "hmd_signal_2_on":signal_2_on}
            jmsg = json.dumps(message)

            self.__socket.send_multipart([topic.encode(), jmsg.encode()])
            self.__console.info(f"Publish HMD Signal Control : {signal_1_on},{signal_2_on}")

        except zmq.ZMQError as e:
            self.__console.error(f"<HMD Signal Control> {e}")

    
    def close(self):
        """ close the socket """
        try:
            self.__socket.close()
        except Exception as e:
            self.__console.error(f"{e}")
        except zmq.ZMQError as e:
            self.__console.error(f"Context termination error : {e}")