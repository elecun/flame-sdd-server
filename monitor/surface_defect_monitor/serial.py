import serial

# 시리얼 포트 설정
port = 'COM3'  # 시리얼 포트 지정 (장치에 따라 변경 필요)
ser = serial.Serial(port, baudrate= 57600)  # DMX USB PRO는 실제 baudrate에 관계없이 57600으로 설정

# DMX 패킷 전송을 위한 기본 설정
start_code = 0x7E  # 시작 코드
label = 6  # Output Only Send DMX Packet Request
end_code = 0xE7  # 종료 코드
Num=255
ch1=Num
ch5=Num
ch9=Num
ch13=Num
# DMX 데이터 준비 (예: 512개 채널 모두 0 값으로 설정)
dmx_data = [0]*1+[int(ch1)]*1+[0]*3+[int(ch5)]*1+[0]*3+[int(ch9)]*1+[0]*3+[int(ch13)]*1+[0]*2
# dmx_data = [0]*512
dmx_length = len(dmx_data) + 1  # DMX 데이터 길이 + 1 (스타트 코드 포함)
data_length_lsb = dmx_length & 0xFF  # 데이터 길이 LSB
data_length_msb = (dmx_length >> 8) & 0xFF  # 데이터 길이 

# 메시지 구성 및 전송
message = [start_code, label, data_length_lsb, data_length_msb, 0] + dmx_data + [end_code]
print(message)
ser.write(bytearray(message))

# 시리얼 포트 닫기
ser.close()

# import serial.tools.list_ports

# def list_serial_ports_windows():
#     ports = serial.tools.list_ports.comports()
#     if len(ports) == 0:
#         print("사용 가능한 시리얼 포트를 찾을 수 없습니다.")
#     else:
#         print("사용 가능한 시리얼 포트:")
#         for port in ports:
#             print(f"포트 이름: {port.device}, 설명: {port.description}")

# if __name__ == "__main__":
#     list_serial_ports_windows()