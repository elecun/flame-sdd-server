"""
NI DAQ Trigger
"""

import nidaqmx
from nidaqmx.stream_writers import CounterWriter
from nidaqmx.constants import *
from nidaqmx.constants import Edge, AcquisitionType, FrequencyUnits, Level
from ast import Break
from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal

from util.logger.console import ConsoleLogger
import numpy as np
import time

class QTrigger(QThread):

    def __init__(self, camera_id:int):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__is_working = False
        self.__task = None

    def close(self) -> None:
        self.requestInterruption() # to quit for thread
        self.quit()
        self.wait(1000)

    def begin(self):
        """ start thread """
        if not self.__is_working:
            self.start()
        else:
            self.__console.warning("Trigger is already working")

    # image grab with thread
    def run(self):
        while True:
            if self.isInterruptionRequested():
                break
            
    
    def is_working(self) -> bool:
        """check if trigger is working"""
        return self.__is_working
    
    def start_trigger(self):
        """start trigger"""
        if not self.__is_working:
            self.__is_working = True

    def stop_trigger(self):
        """stop trigger"""
        if self.__is_working:
            self.__is_working = False

    def start_trigger_continuous(self, channel:str, freq:float, duty:float) -> bool:
        """start triggering continuously"""

        if self.__task is not None:
            self.__console.info("Task is already running")
            return False



class Trigger:
    def __init__(self):
        self.__task = None
        self.__console = ConsoleLogger.get_logger()

    def start_trigger_continuous(self, channel:str, freq:float, duty:float) -> bool:
        """start triggering continuously"""

        if self.__task is not None:
            self.__console.info("Task is already running")
            return False

        self.__task = nidaqmx.Task()
        self.__task.co_channels.add_co_pulse_chan_freq(channel,"",units=FrequencyUnits.HZ, idle_state=Level.LOW, initial_delay=0.0, freq=freq, duty_cycle=duty)
        self.__task.timing.cfg_implicit_timing(sample_mode=AcquisitionType.CONTINUOUS)
        self.__task.start()
        try:
            while True:
                self.__task.is_task_done()
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.__console.info("Trigger is now stopped")
            Break

        self.__task.stop()
        return True

    def start_trigger_finite(self, channel:str, freq:float, samples:int, duty:float):
        """start triggering"""
        self.__console.warning("Not implemented yet")

    def stop_trigger(self):
        """stop triggering continuously"""

        if self.__task is not None:
            self.__task.stop()
            self.__task.close()
            self.__task = None
            self.__console.info("Trigger is now stopped")

    def is_triggering(self):
        """check if tsk is runniung"""
        return self.__task is not None
    

