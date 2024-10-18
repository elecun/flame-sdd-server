import nidaqmx
from nidaqmx.constants import Edge, AcquisitionType

def generate_pulses(device_name, counter_channel, frequency, number_of_pulses):
    """
    지정된 카운터 채널에서 특정 주파수로 지정된 개수의 펄스를 생성합니다.
    :param device_name: 장치 이름 (예: 'Dev1')
    :param counter_channel: 카운터 채널 (예: 'ctr0')
    :param frequency: 펄스의 주파수 (Hz)
    :param number_of_pulses: 생성할 펄스의 개수
    """
    with nidaqmx.Task() as task:
        # 카운터 채널 설정
        counter = task.co_channels.add_co_pulse_chan_freq(
            f"{device_name}/{counter_channel}", 
            freq=frequency, 
            duty_cycle=0.5
        )

        # 펄스 수 설정
        task.timing.cfg_implicit_timing(
            sample_mode=AcquisitionType.FINITE, 
            samps_per_chan=number_of_pulses
        )

        # 펄스 생성 시작
        task.start()

        # 모든 펄스가 완료될 때까지 기다림
        task.wait_until_done()

        # print(f"{number_of_pulses}개의 펄스가 {frequency}Hz 주파수로 생성되었습니다.")

# 함수 사용 예시
generate_pulses('Dev1', 'ctr0', 30, 100)  # 30[FPS]이미지 획득 속도 / 1,000[Pulses] 이미지 갯수
