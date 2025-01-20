"""
Light Control Requester
@author Byunghun Hwang <bh.hwang@iae.re.kr>
"""

try:
    # using PyQt5
    from PyQt5.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
except ImportError:
    # using PyQt6
    from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal

import zmq
import zmq.asyncio
import asyncio
import zmq.utils.monitor as zmq_monitor
from util.logger.console import ConsoleLogger
import json
import threading
import time
from typing import Any, Dict
from functools import partial
import socket

# zmq socket monitoring event map
EVENT_MAP = {}
for name in dir(zmq):
    if name.startswith('EVENT_'):
        value = getattr(zmq, name)
        EVENT_MAP[value] = name


class LightControlRequester(QObject):

    def __init__(self, context:zmq.Context, connection:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()
        self.__console.info(f"+ Light Controller connection : {connection}")

        self.__connection = connection

    def close(self):
        pass

    def get_connection_info(self) -> str:
        return self.__connection
    
    def set_control(self, ip:str, port:int, device_ids:list, brightness:int):
        """ turn on the light """
        dmx_data = bytearray(512)
        for id in device_ids:
            dmx_data[id] = brightness# .to_bytes(1, byteorder="big")
            print(f"Set DMX ID #{id} : {brightness}")
        packet = self.__create_artnet_dmx_packet(sequence=0, physical=0, universe=0, data=dmx_data)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(packet, (ip, port))
        sock.close()
        self.__console.info(f"Light Control : {brightness}")
        

    def __create_artnet_dmx_packet(self, sequence, physical, universe, data):
        header = bytearray('Art-Net\x00', 'utf-8')
        opcode = bytearray([0x00, 0x50])  # OpOutput / DMX
        protocol_version = bytearray([0x00, 0x0e])
        sequence = bytearray([sequence])
        physical = bytearray([physical])
        universe = universe.to_bytes(2, byteorder='little')
        length = len(data).to_bytes(2, byteorder='big')
        
        return header + opcode + protocol_version + sequence + physical + universe + length + data

    async def _async_set_control_on_request(self):
        """ turn on async """
        try:
            pass
        except zmq.error.ZMQError as e:
            self.__console.error(f"{e}")
        except Exception as e:
            self.__console.error(f"General exception")
    
