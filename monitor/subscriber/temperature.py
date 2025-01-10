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

EVENT_MAP = {}
for name in dir(zmq):
    if name.startswith('EVENT_'):
        value = getattr(zmq, name)
        EVENT_MAP[value] = name

class TemperatureSubscriber(QThread):

    temperature_update_signal = pyqtSignal(dict) # signal for temperature update
    connection_status_message = pyqtSignal(str) # signal for connection status message

    def __init__(self, connection:str, topic:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"Temperature controller node connection : {connection} (topic:{topic})")

        # store parameters
        self.__connection = connection
        self.__topic = topic

        # initialize zmq
        self.__context = zmq.Context()
        self.__socket = self.__context.socket(zmq.SUB)
        self.__socket.connect(connection)
        self.__socket.subscribe(topic)

        # create socket monitoring thread
        self._stop_monitoring_event = threading.Event()
        self._monitor_thread = threading.Thread(target=self.socket_monitor, args=(self.__socket,))
        self._monitor_thread.daemon = True
        self._monitor_thread.start()

        self.__console.info("Start Temperature Subscriber")

    def run(self):
        """ Run the subscriber thread """
        while True:
            if self.isInterruptionRequested():
                break
            try:
                data = self.__socket.recv_multipart()[1] # only data block
                #jstr = data.decode('utf8').replace("'", '"')
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
            while not self._stop_monitoring_event.is_set():
                if not monitor.poll(timeout=1000):  # 1sec timeout
                    continue

                event: Dict[str, any] = {}
                monitor_event = zmq_monitor.recv_monitor_message(monitor)
                event.update(monitor_event)
                event["description"] = EVENT_MAP[event["event"]]
                event_msg = event["description"].replace("EVENT_", "")
                endpoint = event["endpoint"].decode('utf-8')

                msg = f"[{endpoint}] {event_msg}" # message format
                
                # emit event message
                self.connection_status_message.emit(msg)
                
            monitor.close()
        except  zmq.error.ZMQError as e:
            self.__console.error(f"{e}")
        
        self.__console.info(f"Stopped Temp. Controller monitoring...")

    def close(self) -> None:
        """ Close the socket and context """
        # close monitoring thread
        self._stop_monitoring_event.set()
        self._monitor_thread.join()

        self.requestInterruption()
        self.quit()
        #self.wait(500)

        try:
            self.__socket.close()
            self.__context.term()
        except zmq.error.ZMQError as e:
            self.__console.error(f"{e}")