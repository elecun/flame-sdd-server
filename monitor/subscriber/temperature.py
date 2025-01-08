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

class TemperatureSubscriber(QThread):

    temperature_update_signal = pyqtSignal(dict) # signal for temperature update

    def __init__(self, connection:str, topic:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"Temperature node connection : {connection} with {topic}")

        # store parameters
        self.__connection = connection
        self.__topic = topic

        # initialize zmq
        self.__context = zmq.Context()
        self.__socket = self.__context.socket(zmq.SUB)
        self.__socket.connect(connection)
        self.__socket.subscribe(topic)

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

    def close(self) -> None:
        """ Close the socket and context """
        self.requestInterruption()
        self.quit()
        self.wait(500)

        self.__socket.close()
        self.__context.term()