"""
DK Level2 Subscriber
@author Byunghun Hwang <bh.hwang@iae.re.kr>
"""

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
import threading
import time
from typing import Any, Dict

# connection event message parsing
EVENT_MAP = {}
for name in dir(zmq):
    if name.startswith('EVENT_'):
        value = getattr(zmq, name)
        EVENT_MAP[value] = name
# event_description, event_value = zmq.utils.monitor.parse_monitor_message(event)

class DKLevel2DataSubscriber(QThread):
    level2_data_update_signal = pyqtSignal(dict) # signal for level2 data update

    def __init__(self, context:zmq.Context, connection:str, topic:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"Temperature Monitor Connection : {connection} (topic:{topic})")

        # store parameters
        self.__connection = connection
        self.__topic = topic

        # initialize zmq
        self.__socket = context.socket(zmq.SUB)
        self.__socket.setsockopt(zmq.RCVBUF .RCVHWM, 1000)
        self.__socket.setsockopt(zmq.RCVTIMEO, 500)
        self.__socket.setsockopt(zmq.LINGER,0)
        self.__socket.connect(connection)
        self.__socket.subscribe(topic)

        self.__poller = zmq.Poller()
        self.__poller.register(self.__socket, zmq.POLLIN) # POLLIN, POLLOUT, POLLERR

        self.__console.info("* Start Level2 Data Subscriber")

    def get_connection_info(self) -> str: # return connection address
        return self.__connection
    
    def get_topic(self) -> str: # return subscriber topic
        return self.__topic
    
    def run(self):
        """ Run the subscriber thread """
        while not self.isInterruptionRequested():
            try:
                events = dict(self.__poller.poll(1000)) # wait 1 sec
                if self.__socket in events:
                    if events[self.__socket] == zmq.POLLERR:
                        self.__console.error(f"<Level2 Data Monitor> Error: {self.__socket.getsockopt(zmq.LAST_ENDPOINT)}")

                    elif events[self.__socket] == zmq.POLLIN:
                        topic, data = self.__socket.recv_multipart()
                        if topic.decode() == self.__topic:
                            data = json.loads(data.decode('utf8').replace("'", '"'))
                            self.level2_data_update_signal.emit(data)
            
            except json.JSONDecodeError as e:
                self.__console.critical(f"<Level2 Data Monitor>[DecodeError] {e}")
                continue
            except zmq.error.ZMQError as e:
                self.__console.critical(f"<Level2 Data Monitor>[ZMQError] {e}")
                break
            except Exception as e:
                self.__console.critical(f"<Level2 Data Monitor>[Exception] {e}")
                break

    def close(self):
        """ close the socket and context """
        self.requestInterruption()
        self.quit()
        self.wait()

        try:
            self.__socket.setsockopt(zmq.LINGER, 0)
            self.__poller.unregister(self.__socket)
            self.__socket.close()
        except zmq.ZMQError as e:
            self.__console.error(f"<Temperature Monitor> {e}")