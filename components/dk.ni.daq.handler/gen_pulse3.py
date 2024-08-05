import nidaqmx
from nidaqmx.stream_writers import CounterWriter
from nidaqmx.constants import *
from nidaqmx.constants import Edge, AcquisitionType, FrequencyUnits, Level
from ast import Break


with nidaqmx.Task() as task:
    task.co_channels.add_co_pulse_chan_freq("Dev1/ctr0","",units=FrequencyUnits.HZ, idle_state=Level.LOW, initial_delay=0.0, freq=30.0, duty_cycle=0.5)
    task.timing.cfg_implicit_timing(sample_mode=AcquisitionType.CONTINUOUS)
    task.start()
    try:
        while True:
            task.is_task_done()
    except KeyboardInterrupt:
        Break

    task.stop()