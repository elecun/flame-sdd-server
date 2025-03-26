"""
DMX Light Control Publisher
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
import subprocess

# zmq socket monitoring event map
EVENT_MAP = {}
for name in dir(zmq):
    if name.startswith('EVENT_'):
        value = getattr(zmq, name)
        EVENT_MAP[value] = name


class DMXLightControlPublisher(QThread):
    """ Publisher for DMX Light Control """

    dmx_alive_signal = pyqtSignal(dict)

    def __init__(self, context:zmq.Context, connection:str, dmx_ip:str, topic:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"+ DMX Light Control Connection : {connection}")

        self.__connection = connection # connection info.
        self.__topic = topic
        self.__dmx_ip = dmx_ip

        self.__console.info("* Start DMX Light Control Publisher")

    def run(self):
        """ Run the subscriber thread """
        while not self.isInterruptionRequested():
            try:
                self.__status_monitor()
                time.sleep(3)
            
            except json.JSONDecodeError as e:
                self.__console.critical(f"<DMX Light Control>[DecodeError] {e}")
                continue
            except zmq.error.ZMQError as e:
                self.__console.critical(f"<DMX Light Control>[ZMQError] {e}")
                break
            except Exception as e:
                self.__console.critical(f"<DMX Light Control>[Exception] {e}")
                break

    def close(self):
        """ close """

        self.requestInterruption()
        self.quit()
        self.wait()

        # try:
        #     self.__socket.close()
        # except Exception as e:
        #     self.__console.error(f"{e}")
        # except zmq.ZMQError as e:
        #     self.__console.error(f"Context termination error : {e}")

    

    def __status_monitor(self):
        message = {"alive":self.__get_alive(self.__dmx_ip)}
        self.dmx_alive_signal.emit(message)

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
        self.__console.info(f"<DMX Light Monitor> {brightness}")
        

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
            self.__console.error(f"<DMX Light Control> General exception")

    def __get_alive(self, host) -> bool:
        """ get alive """
        try:
            result = subprocess.run(
                ["ping", "-c", "1", host],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return result.returncode == 0 #success
        except Exception as e:
            print(f"<DMX Light Control> Error: {e}")
            return False