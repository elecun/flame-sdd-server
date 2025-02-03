"""
Background Service Worker (Thread)
@author Byunghun Hwang <bh.hwang@iae.re.kr>
"""

try:
    # using PyQt5
    from PyQt5.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
except ImportError:
    # using PyQt6
    from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal

import zmq


class Service(QThread):

    def __init__(self, context:zmq.Context, socket_type):
        super().__init__()
        self.__context = context
        self.__socket_type = socket_type
        self.__socket = context.socket(socket_type)
        self.__is_running = True

    def stop(self):
        self.__is_running = False
        self.__socket.close()
        self.quit() # stop event loop
        self.wait() # wait for thread out