"""
DMX Light Control Subscriber
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


class DMXLightControlSubscriber(QThread):
    """ Subscriber for DMX Light Control """

    def __init__(self, context:zmq.Context, connection:str, dmx_ip:str, dmx_port:int, light_ids:list, topic:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"+ DMX Light Control Connection : {connection}")

        self.__connection = connection # connection info.
        self.__topic = topic
        self.__dmx_ip = dmx_ip
        self.__dmx_port = dmx_port
        self.__brightness = 0
        self.__brightness_array = []
        self.__light_ids = light_ids

        # initialize zmq
        self.__socket = context.socket(zmq.SUB)
        self.__socket.setsockopt(zmq.RCVBUF .RCVHWM, 1000)
        self.__socket.setsockopt(zmq.RCVTIMEO, 500)
        self.__socket.setsockopt(zmq.LINGER,0)
        self.__socket.connect(connection)
        self.__socket.subscribe(topic)

        self.__poller = zmq.Poller()
        self.__poller.register(self.__socket, zmq.POLLIN | zmq.POLLERR) # POLLIN, POLLOUT, POLLERR

        self.__console.info("* Start DMX Light Control Subscriber")

    def get_connection_info(self) -> str: # return connection address
        return self.__connection
    
    def get_topic(self) -> str: # return subscriber topic
        return self.__topic

    def run(self):
        """ Run the subscriber thread """
        while not self.isInterruptionRequested():
            try:
                events = dict(self.__poller.poll(1000)) # wait 1sec
                if self.__socket in events:

                    # ready to process
                    if events[self.__socket] == zmq.POLLIN:
                        topic, data = self.__socket.recv_multipart()
                        if topic.decode() == self.__topic:
                            data = json.loads(data.decode('utf8').replace("'", '"'))

                            # control by line signal
                            if "hmd_signal_1_on" in data and "hmd_signal_2_on" in data and "online_signal_on" in data:
                                if data["hmd_signal_1_on"] and data["online_signal_on"]: # in
                                    self.set_control_multi(self.__dmx_ip, self.__dmx_port, self.__light_ids, self.__brightness_array)

                                elif not data["hmd_signal_2_on"] and data["online_signal_on"]: # out
                                    self.set_off(self.__dmx_ip, self.__dmx_port, self.__light_ids)
            
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

        try:
            self.__socket.setsockopt(zmq.LINGER, 0)
            self.__poller.unregister(self.__socket)
            self.__socket.close()
        except zmq.ZMQError as e:
            self.__console.error(f"<DMX Light Control> {e}")


    def get_connection_info(self) -> str:
        return self.__connection
    
    def set_off(self, ip:str, port:int, device_ids:list):
        """ turn on the light """
        dmx_data = bytearray(512)
        for id in device_ids:
            dmx_data[id] = 0# .to_bytes(1, byteorder="big")
        packet = self.__create_artnet_dmx_packet(sequence=0, physical=0, universe=0, data=dmx_data)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(packet, (ip, port))
        sock.close()

    def set_control_multi(self, ip:str, port:int, device_ids:list, brightness:list):
        if len(device_ids)!=len(brightness):
            self.__console.error("Number of device is not equal to number of values")
            return
        
        self.__brightness_array = brightness

        dmx_data = bytearray(512)
        for idx, id in enumerate(device_ids):
            dmx_data[id] = brightness[idx]
        packet = self.__create_artnet_dmx_packet(sequence=0, physical=0, universe=0, data=dmx_data)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(packet, (ip, port))
        sock.close()
        self.__console.info(f"<DMX Light Control> {brightness}")


    def set_control(self, ip:str, port:int, device_ids:list, brightness:int):
        """ turn on the light """
        self.__brightness = brightness # save brightness

        dmx_data = bytearray(512)
        for id in device_ids:
            dmx_data[id] = brightness# .to_bytes(1, byteorder="big")
        packet = self.__create_artnet_dmx_packet(sequence=0, physical=0, universe=0, data=dmx_data)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(packet, (ip, port))
        sock.close()
        self.__console.info(f"<DMX Light Control> {brightness}")
        

    def __create_artnet_dmx_packet(self, sequence, physical, universe, data):
        header = bytearray('Art-Net\x00', 'utf-8')
        opcode = bytearray([0x00, 0x50])  # OpOutput / DMX
        protocol_version = bytearray([0x00, 0x0e])
        sequence = bytearray([sequence])
        physical = bytearray([physical])
        universe = universe.to_bytes(2, byteorder='little')
        length = len(data).to_bytes(2, byteorder='big')
        
        return header + opcode + protocol_version + sequence + physical + universe + length + data

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