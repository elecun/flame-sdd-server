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

    def __init__(self, connection:str, topic:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"Temperature controller Connection : {connection} (topic:{topic})")

        # store parameters
        self.__connection = connection
        self.__topic = topic

        # initialize zmq
        self.__context = zmq.Context()
        self.__socket = self.__context.socket(zmq.SUB)
        self.__socket.setsockopt(zmq.RCVBUF .RCVHWM, 1000)
        self.__socket.connect(connection)
        self.__socket.subscribe(topic)

        # create socket connection status monitoring thread
        self._monitor_thread_stop_event = threading.Event()
        self._monitor_thread = threading.Thread(target=self.socket_monitor, args=(self.__socket,))
        self._monitor_thread.daemon = True
        self._monitor_thread.start()

        self.__console.info("* Start Temperature Subscriber")

        self.start()

    def get_connection_info(self) -> str: # return connection address
        return self.__connection
    
    def get_topic(self) -> str: # return subscriber topic
        return self.__topic

    def run(self):
        """ Run the subscriber thread """
        while True:
            if self.isInterruptionRequested():
                break
            try:
                topic, data = self.__socket.recv_multipart() # only data block
                if topic.decode() == self.__topic:
                    data = json.loads(data.decode('utf8').replace("'", '"'))
                    self.temperature_update_signal.emit(data)
                
            except json.JSONDecodeError as e:
                self.__console.critical(f"{e}")
            except Exception as e:
                self.__console.critical(f"{e}")

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
            self.__context.term()

    def close(self) -> None:
        """ Close the socket and context """
        # close monitoring thread
        self._monitor_thread_stop_event.set()
        self._monitor_thread.join()

        self.requestInterruption()
        self.quit()