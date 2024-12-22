"""
NI DAQ Trigger
"""

import nidaqmx
from nidaqmx.stream_writers import CounterWriter
from nidaqmx.constants import *
from nidaqmx.constants import Edge, AcquisitionType, FrequencyUnits, Level
from ast import Break

from util.logger.console import ConsoleLogger

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
    

