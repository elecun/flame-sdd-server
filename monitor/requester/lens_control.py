"""
Lens Controller Requester (Async)
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


EVENT_MAP = {}
for name in dir(zmq):
    if name.startswith('EVENT_'):
        value = getattr(zmq, name)
        EVENT_MAP[value] = name
# alternative
# event_description, event_value = zmq.utils.monitor.parse_monitor_message(event)

class LensControlRequester(QObject):

    focus_read_update_signal = pyqtSignal(dict) # signal for focus value update
    status_msg_update_signal = pyqtSignal(str) # signal for connection status message
    focus_move_signal = pyqtSignal(bool) # signal for move focus

    def __init__(self, connection:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"Lens Controller connection : {connection}")

        self.__connection = connection # connection info.

        # initialize zmq
        self.__context = zmq.asyncio.Context()
        self.__socket = self.__context.socket(zmq.REQ)
        self.__socket.connect(connection)
        #self._evt_loop = asyncio.get_event_loop()

        # create socket monitoring thread
        # self.__stop_monitoring_event = threading.Event()
        # self.__monitor_thread = threading.Thread(target=self.socket_monitor, args=(self.__socket,))
        # self.__monitor_thread.daemon = True
        # self.__monitor_thread.start()

        # self._monitoring = False
        # self.monitor_socket = None
        self.__console.info("* Start Lens Control Requester")

    def get_connection_info(self) -> str:
        return self.__connection

    def read_focus(self, id:int):
        """ read focus value """
        self.__console.info("call read_focus {id}")
        asyncio.create_task(self._read_focus(id))


    async def _read_focus(self, id:int): # -1 = all
        focus_value = {}

        try:
            message = {
                "function":"read_focus"
            }
            
            if id<0: # for all lens
                print("start poller")
                poller = zmq.asyncio.Poller()
                poller.register(self.__socket, zmq.POLLIN)
                event = await poller.poll(1000) # 1000ms

                if event:
                    response = await self.__socket.recv_string()
                    self.__console.info(f"{response}")

                    focus_value = json.loads(response)
                    self.focus_read_update_signal.emit(focus_value) # emit response
                else:
                    self.__console.error(f"Response timeout!")
                    self.focus_read_update_signal.emit(focus_value)

            else: # for each lens
                self.__console.warning(f"Not implemented yet")

        except zmq.error.ZMQError as e:
            self.__console.error(f"{e}")
        except Exception as e:
            self.__console.error(f"{e}")
            self.focus_read_update_signal.emit(focus_value)


    def focus_move(self, id:int, value:int):
        """ set focus value """
        try:
            message = {
                "id":id,
                "function":"focus_move",
                "value":value
            }

            # request
            request_string = json.dumps(message)
            self.__socket.send_string(request_string)
            self.__console.info(f"Request : {request_string}")

            # reply
            response = self.__socket.recv_string()
            self.__console.info(f"Reply : {response}")
        except zmq.error.ZMQError as e:
            self.__console.error(f"{e}")


    async def socket_monitor_async(self):
        self.monitor_socket = self.socket.get_monitor_socket()
        self._monitoring = True  # 모니터링 시작
        try:
            while self._monitoring:
                try:
                    event = await self.monitor_socket.recv_multipart()
                    event_description, event_value = zmq.utils.monitor.parse_monitor_message(event)
                    print(f"Monitor Event: {event_description}, Value: {event_value}")
                except zmq.ZMQError:
                    break  # 소켓이 닫히거나 에러 발생 시 루프 종료
        finally:
            print("Monitoring stopped.")

    async def receive_data(self):
        """REP 서버로부터 데이터를 수신하고 PyQt 시그널로 전달"""
        while self._monitoring:
            try:
                # 데이터를 수신
                response = await self.socket.recv_string()
                print(f"Received data: {response}")
                
                # PyQt6 시그널로 연결된 슬롯에 데이터 전달
                self.focus_read_update_signal.emit(response)
            except zmq.ZMQError:
                break  # 소켓이 닫히거나 에러 발생 시 루프 종료

    def start_monitoring(self):
        """모니터링 작업 및 데이터 수신 작업을 백그라운드에서 시작"""
        if not self.monitor_socket:
            asyncio.create_task(self.monitor_socket_events())
        asyncio.create_task(self.receive_data())


    async def on_response_read_focus(self, response:str):
        """ received response data handling """
        #self.focus_update_signal.emit
        data = json.loads(response)
        self.focus_read_update_signal.emit(data)
        print(data)

    def socket_monitor(self, socket:zmq.SyncSocket):
        """socket monitoring"""
        try:
            monitor = socket.get_monitor_socket()
            while not self._stop_monitoring_event.is_set():
                if not monitor.poll(timeout=1000):  # 1sec timeout
                    continue

                event: Dict[str, any] = {}
                monitor_event = zmq_monitor.recv_monitor_message(monitor)
                event.update(monitor_event)
                event["description"] = EVENT_MAP[event["event"]]
                event_msg = event["description"].replace("EVENT_", "")
                endpoint = event["endpoint"].decode('utf-8')

                msg = f"[{endpoint}] {event_msg}" # message format
                
                # emit event message
                self.connection_status_message.emit(msg)
                
            monitor.close()
        except  zmq.error.ZMQError as e:
            self.__console.error(f"{e}")
        
        self.__console.info(f"Stopped Lens socket monitoring...")

    def close(self):
        """ close the socket and context """
        self._monitoring = False
        if self.monitor_socket:
            self.monitor_socket.close()
        # close monitoring thread
        # self._stop_monitoring_event.set()
        # self._monitor_thread.join()

        try:
            self.__socket.close()
            self.__context.term()
        except Exception as e:
            self.__console.error(f"{e}")

        
        