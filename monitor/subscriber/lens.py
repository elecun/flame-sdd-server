"""
Focus lens controller
@author Byunghun Hwang <bh.hwang@iae.re.kr>
"""

from PyQt5.QtCore import QThread, pyqtSignal
import zmq
from util.logger.console import ConsoleLogger
import json

class LensController(QThread):

    lens_update_signal = pyqtSignal(dict) # signal for lens update

    def __init__(self, context:zmq.Context, connection:str, topic:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info("Start Lens Controller")

        # store parameters
        self.__connection = connection
        self.__topic = topic
        self.__running = True

        # initialize zmq
        self.__socket = context.socket(zmq.SUB)
        self.__socket.setsockopt(zmq.RCVBUF .RCVHWM, 100)
        self.__socket.connect(connection)
        self.__socket.setsockopt_string(zmq.SUBSCRIBE, topic)

    def __str__(self):
        """ Return the string representation of the object """
        return f"LensController({self.__connection}, {self.__topic})"

    def run(self):
        """ Run the subscriber thread """
        while self.__running:
            # if self.isInterruptionRequested():
            #     break

            data_str = self.__socket.recv_string()
            data = json.loads(data_str)
            self.lens_update_signal.emit(data)

    def close(self) -> None:
        """ Close the socket and context """
        self.__running = False
        # self.requestInterruption()
        # self.quit()
        self.wait()

        self.__socket.close()