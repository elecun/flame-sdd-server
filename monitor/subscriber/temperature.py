"""
Temperature subscriber
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
import os
import datetime

# connection event message parsing
EVENT_MAP = {}
for name in dir(zmq):
    if name.startswith('EVENT_'):
        value = getattr(zmq, name)
        EVENT_MAP[value] = name
# event_description, event_value = zmq.utils.monitor.parse_monitor_message(event)

class TemperatureMonitorSubscriber(QThread):

    temperature_update_signal = pyqtSignal(dict) # signal for temperature update
    status_msg_update_signal = pyqtSignal(str) # signal for connection status message

    def __init__(self, context:zmq.Context, connection:str, topic:str, log_config:dict):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"Temperature Monitor Connection : {connection} (topic:{topic})")

        # store parameters
        self.__connection = connection
        self.__topic = topic
        self.__log_config = log_config

        # initialize zmq
        self.__socket = context.socket(zmq.SUB)
        self.__socket.setsockopt(zmq.RCVBUF .RCVHWM, 1000)
        self.__socket.setsockopt(zmq.RCVTIMEO, 500)
        self.__socket.setsockopt(zmq.LINGER,0)
        self.__socket.connect(connection)
        self.__socket.subscribe(topic)

        self.__poller = zmq.Poller()
        self.__poller.register(self.__socket, zmq.POLLIN) # POLLIN, POLLOUT, POLLERR

        self.__console.info("* Start Temperature Subscriber")

        self.start()

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
                    topic, data = self.__socket.recv_multipart()
                    if topic.decode() == self.__topic:
                        data = json.loads(data.decode('utf8').replace("'", '"'))
                        self.temperature_update_signal.emit(data)

                        # save temperataure log
                        if self.__log_config.get("option_save_temperature_log", False):
                            path = self.__log_config.get("option_save_temperature_log_path", "/tmp")
                            fullpath = os.path.join(path, f"{datetime.datetime.today().strftime('%Y-%m-%d')}.csv")

                            today = datetime.today().strftime('%Y-%m-%d')
file_name = f'{today}.csv'

                            # create direcotry if not exist
                            if not os.path.exists(path):


        
            
            except json.JSONDecodeError as e:
                self.__console.critical(f"<Temperature Monitor>[DecodeError] {e}")
                continue
            except zmq.error.ZMQError as e:
                self.__console.critical(f"<Temperature Monitor>[ZMQError] {e}")
                break
            except Exception as e:
                self.__console.critical(f"<Temperature Monitor>[Exception] {e}")
                break

    def socket_monitor(self, socket:zmq.SyncSocket):
        """socket monitoring"""
        try:
            monitor = socket.get_monitor_socket()
            while not self._monitor_thread_stop_event.is_set():
                if not monitor.poll(timeout=1000):  # 1sec timeout
                    continue

                event: Dict[str, any] = {}
                monitor_event = zmq_monitor.recv_monitor_message(monitor)
                event.update(monitor_event)
                event["description"] = EVENT_MAP[event["event"]]
                event_msg = event["description"].replace("EVENT_", "")
                endpoint = event["endpoint"].decode('utf-8')

                msg = f"[{endpoint}] {event_msg}" # message format
                self.status_msg_update_signal.emit(msg) # emit message to signal
                
            monitor.close()
        except  zmq.error.ZMQError as e:
            self.__console.error(f"{e}")
        finally:
            self.__socket.close()

    def close(self) -> None:
        """ Close the socket and context """
        # close monitoring thread

        # self._monitor_thread_stop_event.set()
        # self._monitor_thread.join()

        self.requestInterruption()
        self.quit()
        self.wait()

        try:
            self.__socket.setsockopt(zmq.LINGER, 0)
            self.__poller.unregister(self.__socket)
            self.__socket.close()
        except zmq.ZMQError as e:
            self.__console.error(f"<Temperature Monitor> {e}")

        