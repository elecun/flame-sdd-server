import nidaqmx
from nidaqmx.constants import VoltageUnits

def write_analog_voltage(device_name, channel, voltage):
    """
    지정된 채널에 아날로그 전압을 출력합니다.
    :param device_name: 장치 이름 (예: 'Dev1')
    :param channel: 아날로그 출력 채널 (예: 'ao0')
    :param voltage: 출력할 전압 값
    """
    # Task 객체 생성
    with nidaqmx.Task() as task:
        # 아날로그 출력 채널 추가
        task.ao_channels.add_ao_voltage_chan(f"{device_name}/{channel}",
                                             min_val=-10, max_val=10,
                                             units=VoltageUnits.VOLTS)

        # 전압 출력
        task.write(voltage)
        print(f"{voltage} V가 {device_name}/{channel} 채널에 출력되었습니다.")

# 함수 사용 예시
write_analog_voltage('Dev1', 'ao0', 9)
