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


class LineSignalSubscriber(QThread):
    """ Publisher for Line Status(On/Offline) Signal Control """

    line_signal = pyqtSignal(dict)

    def __init__(self, context:zmq.Context, connection:str, topic:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"+ Line Signal connection : {connection} (topic:{topic})")

        self.__connection = connection # connection info.
        self.__topic = topic

        self.__socket = context.socket(zmq.SUB)
        self.__socket.setsockopt(zmq.RCVBUF .RCVHWM, 100)
        self.__socket.setsockopt(zmq.RCVTIMEO, 500)
        self.__socket.setsockopt(zmq.LINGER,0)
        self.__socket.connect(connection)
        self.__socket.subscribe(topic)

        self.__poller = zmq.Poller()
        self.__poller.register(self.__socket, zmq.POLLIN) # POLLIN, POLLOUT, POLLERR

        self.__console.info("* Start Line Signal Subscriber")
        self.start()
    
    def get_connection_info(self) -> str:
        """ get connection info """
        return self.__connection
    
    def get_topic(self) -> str: # return subscriber topic
        return self.__topic
    
    def run(self):
        """ Run the subscriber thread """
        while not self.isInterruptionRequested():
            try:
                events = dict(self.__poller.poll(500)) # wait 1 sec
                if self.__socket in events:
                    topic, data = self.__socket.recv_multipart()
                    if topic.decode() == self.__topic:
                        data = json.loads(data.decode('utf8').replace("'", '"'))
                        self.line_signal.emit(data) # dict type
            
            except json.JSONDecodeError as e:
                self.__console.critical(f"<Line Signal Monitor>[DecodeError] {e}")
                continue
            except zmq.error.ZMQError as e:
                self.__console.critical(f"<Line Signal Monitor>[ZMQError] {e}")
                break
            except Exception as e:
                self.__console.critical(f"<Line Signal Monitor>[Exception] {e}")
                break
    
    def close(self):
        """ close the socket """
        self.requestInterruption()
        self.quit()
        self.wait()

        try:
            self.__socket.setsockopt(zmq.LINGER, 0)
            self.__poller.unregister(self.__socket)
            self.__socket.close()
        except zmq.ZMQError as e:
            self.__console.error(f"<Line Signal Monitor> {e}")