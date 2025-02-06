""" 
Pulse Generator Requester 
@author Byunghun Hwang <bh.hwang@iae.re.kr>
"""

try:
    # using PyQt5
    from PyQt5.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
except ImportError:
    # using PyQt6
    from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal

import nidaqmx.errors
import zmq
import zmq.asyncio
import asyncio
import zmq.utils.monitor as zmq_monitor
from util.logger.console import ConsoleLogger
import json
import threading
import time
from typing import Any, Dict
from functools import partial
import nidaqmx
from nidaqmx.stream_writers import CounterWriter
from nidaqmx.constants import *
from nidaqmx.constants import Edge, AcquisitionType, FrequencyUnits, Level
from ast import Break

# zmq socket monitoring event map
EVENT_MAP = {}
for name in dir(zmq):
    if name.startswith('EVENT_'):
        value = getattr(zmq, name)
        EVENT_MAP[value] = name

class PulseGeneratorRequester(QObject):
    def __init__(self, context:zmq.Context, connection:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()
        self.__console.info(f"+ Pulse Generator connection : {connection}")

        # create context for zmq requester
        self.__socket = context.socket(zmq.REQ)
        self.__socket.setsockopt(zmq.RCVBUF .RCVHWM, 1000)
        self.__socket.setsockopt(zmq.LINGER, 0)
        self.__socket.connect(connection)

        self.__worker = None
        self.__running = False
        self.__connection = connection
        self.__task = nidaqmx.Task()

        self.__console.info("* Start Pulse Generator Requester")

    def get_connection_info(self) -> str:
        return self.__connection
    
    def close(self):
        """ close the socket and context """
        # close pipeline connection
        try:
            self.__socket.close()
        except Exception as e:
            self.__console.error(f"{e}")
        except zmq.ZMQError as e:
            self.__console.error(f"Context termination error : {e}")

        if self.__running:
            self.stop_generation()
        self.__task.close()
    
    def __run(self, freq, duty):
        self.__task.co_channels.add_co_pulse_chan_freq("Dev1/ctr0:1","",units=FrequencyUnits.HZ, idle_state=Level.LOW, initial_delay=0.0, freq=freq, duty_cycle=duty)
        self.__task.timing.cfg_implicit_timing(sample_mode=AcquisitionType.CONTINUOUS)
        self.__task.start()
        try:
            while self.__running:
                if self.isInterruptionRequested():
                    break

                if self.__task.is_task_done():
                    time.sleep(0.1)
                    break
        except nidaqmx.errors.DaqError as e:
            self.__console.error("DAQ Pulse Generator Error")
        finally:
            self.__task.stop()
            self.__task.close()
        self.__running = False
    
    def start_generation(self, freq:float, duty:float):
        if self.__running:
            return
        self.__running = True
        self.__worker = threading.Thread(target=self.__run, args=(freq, duty, ), daemon=True)
        self.__worker.start()
        self.__console.info("Start Pulse Generator")

    def stop_generation(self):
        if not self.__running:
            return
        self.__running = False
        self.__worker.join()
