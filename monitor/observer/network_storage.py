"""
NAS (Network Attached Storage) Status Observer
@author Byunghun Hwang <bh.hwang@iae.re.kr>
"""

try:
    # using PyQt5
    from PyQt5.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
    from PyQt6.QtGui import QImage
except ImportError:
    # using PyQt6
    from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
    from PyQt6.QtGui import QImage

from util.logger.console import ConsoleLogger
import os


class NASStatusObserver(QThread):
    """ NAS Status Monitor """

    status_update_signal = pyqtSignal(dict) # signal for status

    def __init__(self, fullpath:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__fullpath = fullpath

        self.__console.info("* Start Network Attached Storage (NAS) Status Observer")
        self.start()

    def run(self):
        while not self.isInterruptionRequested():
            status = {}
            if os.path.exists(self.__fullpath):
                status["available"] = True
            else:
                status["available"] = False
            
            # update status
            self.status_update_signal.emit(status)


    def available(self) -> bool:
        # return true if file is exist
        if os.path.exists(self.__fullpath):
            self.__console.info(f"NAS Status Observer : {self.__fullpath} is available")
            return True
    
    def close(self):
        """ close the socket """
        try:
            pass
        except Exception as e:
            self.__console.error(f"{e}")