import nidaqmx
import time
import threading
from nidaqmx.constants import Edge, AcquisitionType, LineGrouping

DEVICE_NAME = "Dev1"
COUNTER_CHANNEL = "ctr0:1"
PULSE_FREQUENCY = 20

DIGITAL_INPUT_LINES = {
    "P1.0 (11번핀)": "port1/line0",
    "P1.2 (43번핀)": "port1/line2",
    "P1.3 (42번핀)": "port1/line3",
}

def generate_continuous_pulses():
    with nidaqmx.Task() as task:
        task.co_channels.add_co_pulse_chan_freq(
            f"{DEVICE_NAME}/{COUNTER_CHANNEL}",
            freq=PULSE_FREQUENCY,
            duty_cycle=0.5
        )
        task.timing.cfg_implicit_timing(sample_mode=AcquisitionType.CONTINUOUS)
        print(f" {PULSE_FREQUENCY}Hz 카메라 트리거신호 시작...")
        task.start()
        while True:
            time.sleep(1)

def monitor_multiple_inputs():
    print(f" 외부 신호 모니터링 시작 (10ms 주기) - {DEVICE_NAME} / P1.0, P1.2, P1.3")

    with nidaqmx.Task() as trigger_task:
        # 유효한 채널 명시 방식으로 수정
        trigger_task.di_channels.add_di_chan(
            f"{DEVICE_NAME}/port1/line0,{DEVICE_NAME}/port1/line2,{DEVICE_NAME}/port1/line3",
            line_grouping=LineGrouping.CHAN_PER_LINE
        )

        while True:
            states = trigger_task.read()  # 리스트 반환
            signal_status = {
                "MD": "HIGH" if states[0] else "LOW",
                "SDD_OffLine": "HIGH" if states[1] else "LOW",
                "SDD_OnLine": "HIGH" if states[2] else "LOW",
            }
            print(" 접점 신호 상태:", signal_status)
            time.sleep(0.01)

if __name__ == "__main__":
    pulse_thread = threading.Thread(target=generate_continuous_pulses, daemon=True)
    pulse_thread.start()
    monitor_multiple_inputs()

