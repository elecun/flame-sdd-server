import nidaqmx
import time
import threading
from nidaqmx.constants import Edge, AcquisitionType

# DAQ 장치 설정
DEVICE_NAME = "Dev1"
COUNTER_CHANNEL = "ctr0:1"  # 지속적인 펄스 트레인을 발생할 채널
TRIGGER_CHANNEL = "PFI0"  # 외부 접점 신호를 모니터링할 채널
FREQUENCY = 30  # 지속적인 펄스 트레인 주파수 (Hz)

def generate_continuous_pulses():
    """
    30FPS로 지속적으로 펄스 트레인을 생성하는 함수.
    """
    with nidaqmx.Task() as task:
        task.co_channels.add_co_pulse_chan_freq(
            f"{DEVICE_NAME}/{COUNTER_CHANNEL}",
            freq=FREQUENCY,
            duty_cycle=0.5
        )

        # 무한정 지속되는 펄스 트레인 설정
        task.timing.cfg_implicit_timing(sample_mode=AcquisitionType.CONTINUOUS)

        print(f" {FREQUENCY}Hz 카메라 트리거신호 시작...")
        task.start()

        # 무한 루프 유지 (스레드에서 실행될 것이므로 별도로 종료되지 않음)
        while True:
            time.sleep(1)

def monitor_trigger():
    """
    외부 접점 신호(PFI0)를 10ms 주기로 읽어 상태를 모니터링하는 함수.
    """
    print(f" 외부 신호 모니터링 시작 (10ms 주기) - {DEVICE_NAME}/{TRIGGER_CHANNEL}")

    with nidaqmx.Task() as trigger_task:
        trigger_task.di_channels.add_di_chan(f"{DEVICE_NAME}/{TRIGGER_CHANNEL}")

        while True:
            current_state = trigger_task.read()
            print(f" 접점 신호 상태: {'HIGH' if current_state else 'LOW'}")

            time.sleep(0.1)  # 10ms 주기

if __name__ == "__main__":
    # 지속적인 펄스 트레인 실행 (별도 스레드)
    pulse_thread = threading.Thread(target=generate_continuous_pulses, daemon=True)
    pulse_thread.start()

    # 외부 신호 모니터링 실행 (메인 루프)
    monitor_trigger()
