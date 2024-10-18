import nidaqmx
from nidaqmx.system import System

def list_ni_devices():
    system = System.local()
    for device in system.devices:
        print(device)

list_ni_devices()

