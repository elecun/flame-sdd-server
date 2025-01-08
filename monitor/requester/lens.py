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
from util.logger.console import ConsoleLogger
import json

class LensControlRequester(QObject):

    focus_update_signal = pyqtSignal(dict) # signal for focus value update

    def __init__(self, connection:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"Lens Control node connection : {connection}")

        self.__connection = connection

        # initialize zmq
        self.__context = zmq.Context()
        self.__socket = self.__context.socket(zmq.REQ)
        self.__socket.connect(connection)

        self.__console.info("Start Lens Control Requester")

    def focus_move(self, id:int, value:int):
        """ set focus value """
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
        
    
    def read_focus(self):
        """ read all lens focus value """
        message = {
            "function":"read_focus"
        }
        request_string = json.dumps(message)
        self.__socket.send_string(request_string)
        self.__console.info(f"Request : {request_string}")

        # reply
        response = self.__socket.recv_string()
        self.__console.info(f"Reply : {response}")

    def close(self):
        """ close the socket and context """
        self.__socket.close()
        self.__context.term()