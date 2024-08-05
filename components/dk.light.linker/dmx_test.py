import socket

# Art-Net 패킷을 생성하는 함수
def create_artnet_dmx_packet(sequence, physical, universe, data):
    # Art-Net 패킷 헤더
    header = bytearray('Art-Net\x00', 'utf-8')
    opcode = bytearray([0x00, 0x50])  # OpOutput / DMX
    protocol_version = bytearray([0x00, 0x0e])
    sequence = bytearray([sequence])
    physical = bytearray([physical])
    universe = universe.to_bytes(2, byteorder='little')
    length = len(data).to_bytes(2, byteorder='big')
    
    return header + opcode + protocol_version + sequence + physical + universe + length + data

# DMX 데이터 (예시 데이터, 512 채널)
dmx_data = bytearray(512)
dmx_data[1] = 0x00  # 첫 채널 값을 255로 설정 (조명 켜짐)
dmx_data[5] = 0x00  # 0x3d 위치 채널 값을 255로 설정 (조명 켜짐)
dmx_data[9] = 0x00  # 추가로 켜진 조명 1

# Art-Net DMX 패킷 생성
packet = create_artnet_dmx_packet(sequence=0, physical=0, universe=0, data=dmx_data)

# 소켓 생성 및 설정
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# 목적지 IP와 포트를 설정합니다.
dest_ip = "192.168.0.10"
dest_port = 6454

# 패킷 전송
sock.sendto(packet, (dest_ip, dest_port))

print("패킷이 전송되었습니다.")

# 소켓을 닫습니다.
sock.close()
