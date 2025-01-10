"""
Lens Controller Requester
@author Byunghun Hwang <bh.hwang@iae.re.kr>
"""

try:
    # using PyQt5
    from PyQt5.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
except ImportError:
    # using PyQt6
    from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal

import zmq
import zmq.utils.monitor as zmq_monitor
from util.logger.console import ConsoleLogger
import json
import threading
import time
from typing import Any, Dict
import zmq.asyncio

EVENT_MAP = {}
for name in dir(zmq):
    if name.startswith('EVENT_'):
        value = getattr(zmq, name)
        EVENT_MAP[value] = name
# alternative
# event_description, event_value = zmq.utils.monitor.parse_monitor_message(event)

class LensControlRequester(QObject):

    focus_update_signal = pyqtSignal(dict) # signal for focus value update
    connection_status_message = pyqtSignal(str) # signal for connection status message

    def __init__(self, connection:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"Lens Control node connection : {connection}")

        self.__connection = connection

        # initialize zmq
        self.__context = zmq.asyncio.Context()
        self.__socket = self.__context.socket(zmq.REQ)
        self.__socket.connect(connection)
        self._evt_loop = asyncio.get_event_loop()

        # create socket monitoring thread
        # self._stop_monitoring_event = threading.Event()
        # self._monitor_thread = threading.Thread(target=self.socket_monitor, args=(self.__socket,))
        # self._monitor_thread.daemon = True
        # self._monitor_thread.start()

        self._monitoring = False  # 종료 플래그
        self.monitor_socket = None
        self.__console.info("Start Lens Control Requester")

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

    async def read_focus_async(self):
        try:
            message = {
                "function":"read_focus"
            }
        request_string = json.dumps(message)
        await self.__socket.send_string(request_string)
        response = await self.__socket.recv_string()
        self.focus_update_signal.emit(response)

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
                self.focus_update_signal.emit(response)
            except zmq.ZMQError:
                break  # 소켓이 닫히거나 에러 발생 시 루프 종료

    def start_monitoring(self):
        """모니터링 작업 및 데이터 수신 작업을 백그라운드에서 시작"""
        if not self.monitor_socket:
            asyncio.create_task(self.monitor_socket_events())
        asyncio.create_task(self.receive_data())
    
    async def read_focus(self):
        """ read all lens focus value """
        try:
            message = {
                "function":"read_focus"
            }
            request_string = json.dumps(message)
            await self.__socket.send_string(request_string, timeout=1000)
            self.__console.info(f"Request : {request_string}")

            # reply
            response = await self.__socket.recv_string()
            self.__console.info(f"Reply : {response}")

            # trigger callback
            await self.on_response_read_focus(response)

        except zmq.error.ZMQError as e:
            self.__console.error(f"{e}")
        except asyncio.TimeoutError as e:
            self.__console.warn(f"{e}")

    async def on_response_read_focus(self, response:str):
        """ received response data handling """
        #self.focus_update_signal.emit
        data = json.loads(response)
        self.focus_update_signal.emit(data)
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

    async def close(self):
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
        except zmq.error.ZMQError as e:
            self.__console.error(f"{e}")

        
        
