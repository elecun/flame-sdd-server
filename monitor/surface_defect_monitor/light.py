"""
Light Control with DMX protocol
"""
import socket
from util.logger.console import ConsoleLogger

class LightController:
    def __init__(self):
        self.__console = ConsoleLogger.get_logger()


    def light_on(self, dest_ip:str, dest_port:int):
        dmx_data = bytearray(512)
        dmx_data[1] = 0x10  # 첫 채널 값을 255로 설정 (조명 켜짐)
        dmx_data[7] = 0x10  # 0x3d 위치 채널 값을 255로 설정 (조명 켜짐)
        dmx_data[9] = 0x10  # 추가로 켜진 조명 1

        packet = self.__create_artnet_dmx_packet(sequence=0, physical=0, universe=0, data=dmx_data)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(packet, (dest_ip, dest_port))
        sock.close()
        print("on")

    def light_off(self, dest_ip:str, dest_port:int):
        dmx_data = bytearray(512)
        dmx_data[1] = 0x00  # 첫 채널 값을 255로 설정 (조명 켜짐)
        dmx_data[7] = 0x00  # 0x3d 위치 채널 값을 255로 설정 (조명 켜짐)
        dmx_data[9] = 0x00  # 추가로 켜진 조명 1

        packet = self.__create_artnet_dmx_packet(sequence=0, physical=0, universe=0, data=dmx_data)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(packet, (dest_ip, dest_port))
        sock.close()

    def __create_artnet_dmx_packet(self, sequence, physical, universe, data):
        header = bytearray('Art-Net\x00', 'utf-8')
        opcode = bytearray([0x00, 0x50])  # OpOutput / DMX
        protocol_version = bytearray([0x00, 0x0e])
        sequence = bytearray([sequence])
        physical = bytearray([physical])
        universe = universe.to_bytes(2, byteorder='little')
        length = len(data).to_bytes(2, byteorder='big')
        
        return header + opcode + protocol_version + sequence + physical + universe + length + data