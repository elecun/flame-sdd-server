import nidaqmx
from nidaqmx.stream_writers import CounterWriter
from nidaqmx.constants import *
from nidaqmx.constants import Edge, AcquisitionType

with nidaqmx.Task() as task:
    task.co_channels.add_co_pulse_chan_time(counter = "Dev1/ctr0")
    task.timing.cfg_implicit_timing(sample_mode=AcquisitionType.CONTINUOUS)
    cw = CounterWriter(task.out_stream, True)
    task.start()
    cw.write_one_sample_pulse_frequency(30, 0.5, 10)