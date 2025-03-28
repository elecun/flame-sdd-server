"""
Light Control with DMX protocol
"""
import socket
import time

class LightController:
    def __init__(self):
        pass

    def light_on(self, id, dest_ip:str, dest_port:int):
        dmx_data = bytearray(512)
        dmx_data[id] = 0x55  # 첫 채널 값을 255로 설정 (조명 켜짐)

        packet = self.__create_artnet_dmx_packet(sequence=0, physical=0, universe=0, data=dmx_data)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(packet, (dest_ip, dest_port))
        sock.close()
        print("on")

    def light_off(self, id, dest_ip:str, dest_port:int):
        dmx_data = bytearray(512)
        dmx_data[id] = 0x00  # 첫 채널 값을 255로 설정 (조명 켜짐)

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

if __name__ == "__main__":
    # id = 23
    controller = LightController()
    # controller.light_on(id, "192.168.0.60", 6454)
    # time.sleep(5)
    # controller.light_off(id, "192.168.0.60", 6454)
    ids = [1,3,5,7,9,11,13,15,17,19, 21, 23]
    for id in ids:
        print(f"{id} on")
        controller.light_on(id, "192.168.0.60", 6454)
        time.sleep(3)
        print(f"{id} off")
        controller.light_off(id, "192.168.0.60", 6454)
        time.sleep(3)