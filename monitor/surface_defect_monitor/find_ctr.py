import nidaqmx
from nidaqmx.system import System

def list_device_counters():
    system = System.local()
    for device in system.devices:
        print(f"장치 이름: {device.name}")
        try:
            counters = device.co_physical_chans
            if counters:
                print("카운터/타이머 채널 목록:")
                for counter in counters:
                    print(f"  {counter.name}")
            else:
                print("  이 장치에는 카운터/타이머 채널이 없습니다.")
        except nidaqmx.errors.DaqError as e:
            print(f"  에러: {e}")
        print("")

list_device_counters()

