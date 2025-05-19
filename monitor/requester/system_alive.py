""" 
System Alive Check Requester
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

# zmq socket monitoring event map
EVENT_MAP = {}
for name in dir(zmq):
    if name.startswith('EVENT_'):
        value = getattr(zmq, name)
        EVENT_MAP[value] = name

class SystemAliveRequester(QThread):

    alive_update_signal = pyqtSignal(bool)

    def __init__(self, context:zmq.Context, connection:str, alive_msg:str):
        super().__init__()

        self.__echo_msg = alive_msg

        self.__console = ConsoleLogger.get_logger()
        self.__console.info(f"+ System Alive Requester connection : {connection}")

        # intialize zmq
        self.__socket = context.socket(zmq.REQ)
        self.__socket.setsockopt(zmq.RCVBUF .RCVHWM, 5000)
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
            self.__console.error(f"<System Alive> {e}")
        
        self.__console.info(f"Close System Alive Requester")

    def run(self):
        while not self.isInterruptionRequested():
            try:
                self.__socket.send_string(self.__echo_msg)

                if self.__poller.poll(timeout=1000):  # poll for a reply within 1 second
                    reply = self.__socket.recv_string()
                    if reply == self.__echo_msg:
                        self.alive_update_signal.emit(True)
                    else:
                        self.alive_update_signal.emit(False)
                else:
                    self.alive_update_signal.emit(False)
            
                time.sleep(1)
                
            except json.JSONDecodeError as e:
                self.__console.critical(f"<System Alive> {e}")
                continue
            except zmq.ZMQError as e:
                self.__console.critical(f"<System Alive> {e}")
                break
            except Exception as e:
                self.__console.critical(f"<System Alive> {e}")
                break


