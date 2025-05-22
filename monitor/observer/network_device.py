"""
Network Device Observer (with ping command)
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
import datetime
import time
import platform
import subprocess


class NetworkDeviceObserver(QThread):
    """ Network Device Monitor """

    status_update_signal = pyqtSignal(dict) # signal for status

    def __init__(self, ipaddr:str, period:int=3):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger

        self.__ipaddr = ipaddr
        self.__period = period

        self.__console.info("* Start Network Device Status Observer")
        self.start()

    def run(self):
        """ run the observer """
        while not self.isInterruptionRequested():
            status = {}
            status['available'] = self.available(self.__ipaddr)
            self.status_update_signal.emit(status) # emit signal

            time.sleep(self.__period) # every 3 seconds
            
    def available(self, ipaddr) -> bool:
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'

        try:
            result = subprocess.run(['ping', param, '1', timeout_param, str(int(1)), ipaddr],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return result.returncode == 0
        except Exception as e:
            return False
    
    def close(self):
        """ close the socket """
        try:
            pass
        except Exception as e:
            self.__console.error(f"{e}")