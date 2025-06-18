""" 
System Echo(Alive) Check Requester
@author Byunghun Hwang <bh.hwang@iae.re.kr>
"""

try:
    # using PyQt5
    from PyQt5.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
except ImportError:
    # using PyQt6
    from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal


import zmq
import zmq.asyncio
import zmq.utils.monitor as zmq_monitor
from util.logger.console import ConsoleLogger
import json
import threading
import time
from typing import Any, Dict
from functools import partial
import threading
import uuid

# zmq socket monitoring event map
EVENT_MAP = {}
for name in dir(zmq):
    if name.startswith('EVENT_'):
        value = getattr(zmq, name)
        EVENT_MAP[value] = name

class SystemEchoRequester(QThread):

    alive_update_signal = pyqtSignal(int, bool)

    def __init__(self, context:zmq.Context, connection:str, id:int, interval_ms:int):
        super().__init__()

        self.__connection = connection
        self.__time_interval = interval_ms
        self.__system_id = id
        self.__console = ConsoleLogger.get_logger()
        self.__console.info(f"+ System Echo Requester Connection : {connection}")

        # intialize zmq
        self.__socket = context.socket(zmq.REQ)
        self.__socket.setsockopt(zmq.RCVBUF .RCVHWM, 100)
        self.__socket.setsockopt(zmq.RCVTIMEO, 500)
        self.__socket.setsockopt(zmq.LINGER, 0)
        self.__socket.connect(connection)

        self.__poller = zmq.Poller()
        self.__poller.register(self.__socket, zmq.POLLIN) # POLLIN, POLLOUT, POLLERR

        self.start()

    def get_connection_info(self) -> str:
        return self.__connection
    
    def close(self) -> None:
        """ close the socket and context """
        self.requestInterruption()
        self.quit()
        self.wait()

        try:
            self.__socket.setsockopt(zmq.LINGER, 0)
            self.__poller.unregister(self.__socket)
            self.__socket.close()
        except zmq.ZMQError as e:
            self.__console.error(f"<System Echo> {e}")
        
        self.__console.info(f"Close System Echo Requester")

    def run(self):
        _echo_msg = ""
        while not self.isInterruptionRequested():
            try:
                events = dict(self.__poller.poll(self.__time_interval))

                if self.__socket in events:                
                    if events[self.__socket] == zmq.POLLIN:
                        reply = self.__socket.recv_string()
                        if reply == _echo_msg:
                            self.alive_update_signal.emit(self.__system_id, True)
                        else:
                            self.alive_update_signal.emit(self.__system_id, False)
                else: # poller timeout
                    _echo_msg = str(uuid.uuid4())
                    self.__socket.send_string(_echo_msg)
                    self.alive_update_signal.emit(self.__system_id, False)
                
            except json.JSONDecodeError as e:
                self.__console.critical(f"<System Echo>(JSON Exception) {e}")
                continue
            except zmq.ZMQError as e:
                if e.errno != zmq.EFSM:
                    self.__console.critical(f"<System Echo>(ZMQ Error) {e}")
                continue
            except Exception as e:
                self.__console.critical(f"<System Echo>(General Exception) {e}")
                break


