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
from service import Service
from zmq.utils.monitor import parse_monitor_message

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

    def __init__(self, context:zmq.Context, connection:str, topic:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"Temperature monitor subscriber is now connecting {connection} (topic:{topic})")

        """ local varuiables """
        self.__is_running = True

        """ create zmq socket for subscriber """
        self.__socket = context.socket(zmq.SUB)
        self.__socket.setsockopt(zmq.RCVBUF .RCVHWM, 1000)
        self.__socket.setsockopt(zmq.RCVTIMEO, 500)
        self.__socket.setsockopt(zmq.LINGER,0)
        self.__socket.connect(connection)
        self.__socket.subscribe(topic)
        
        # socket monitoring
        self._monitor_thread_stop_event = threading.Event()
        self.__monitor = self.__socket.get_monitor_socket()
        self.__poller = zmq.Poller()
        self.__poller.register(self.__socket, zmq.POLLIN)
        self.__poller.register(self.__monitor, zmq.POLLIN)

        # store parameters
        self.__connection = connection
        self.__topic = topic

        self.__console.info("* Start temperature monitor subscriber in background...")
        self.start()

    def get_connection_info(self) -> str:
        """ return connection info """
        return self.__connection
    
    def get_topic(self) -> str:
        """ get subscribe topic """
        return self.__topic

    def run(self):
        """ Run the subscriber thread """

        while self.__is_running:
            try:
                events = dict(self.__poller.poll())

                if self.__socket in events and events[self.__socket]==zmq.POLLIN:
                    message = self.__socket.recv_multipart(zmq.NOBLOCK)
                    # message data processing here

                if self.__monitor in events and events[self.__monitor]==zmq.POLLIN:
                    monitor_event = self.__monitor.recv_multipart(zmq.NOBLOCK)
                    parsed_event = parse_monitor_message(monitor_event)
                    
                    print(parsed_event)
                    # self.status_msg_update_signal.emit
            except Exception as e:
                self.__console.critical(f"Temperature Monitor Subscriber Exception : {e}")
            except zmq.ZMQError as e:
                if e.errno != zmq.EAGAIN: # if nothing to recv, occurred zmq error EAGAIN
                    break
            finally:
                self.__socket.close()
                self.__monitor.close()

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
        self._monitor_thread_stop_event.set()
        # self._monitor_thread.join()

        self.requestInterruption()
        self.quit()
        self.wait()