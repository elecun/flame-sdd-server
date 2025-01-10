"""
Lens Controller Requester
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
import zmq.asyncio

EVENT_MAP = {}
for name in dir(zmq):
    if name.startswith('EVENT_'):
        value = getattr(zmq, name)
        EVENT_MAP[value] = name

class LensControlRequester(QObject):

    focus_update_signal = pyqtSignal(dict) # signal for focus value update
    connection_status_message = pyqtSignal(str) # signal for connection status message

    def __init__(self, connection:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"Lens Control node connection : {connection}")

        self.__connection = connection

        # initialize zmq
        self.__context = zmq.Context()
        self.__socket = self.__context.socket(zmq.REQ)
        self.__socket.connect(connection)

        # create socket monitoring thread
        self._stop_monitoring_event = threading.Event()
        self._monitor_thread = threading.Thread(target=self.socket_monitor, args=(self.__socket,))
        self._monitor_thread.daemon = True
        self._monitor_thread.start()

        self.__console.info("Start Lens Control Requester")

    def focus_move(self, id:int, value:int):
        """ set focus value """
        try:
            message = {
                "id":id,
                "function":"focus_move",
                "value":value
            }

            # request
            request_string = json.dumps(message)
            self.__socket.send_string(request_string)
            self.__console.info(f"Request : {request_string}")

            # reply
            response = self.__socket.recv_string()
            self.__console.info(f"Reply : {response}")
        except zmq.error.ZMQError as e:
            self.__console.error(f"{e}")
        
    
    def read_focus(self):
        """ read all lens focus value """
        try:
            message = {
                "function":"read_focus"
            }
            request_string = json.dumps(message)
            self.__socket.send_string(request_string)
            self.__console.info(f"Request : {request_string}")

            # reply
            response = self.__socket.recv_string()
            self.__console.info(f"Reply : {response}")
        except zmq.error.ZMQError as e:
            self.__console.error(f"{e}")

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
        
        self.__console.info(f"Stopped Lens socket monitoring...")

    def close(self):
        """ close the socket and context """
        # close monitoring thread
        self._stop_monitoring_event.set()
        self._monitor_thread.join()

        try:
            self.__socket.close()
            self.__context.term()
        except zmq.error.ZMQError as e:
            self.__console.error(f"{e}")

        
        
