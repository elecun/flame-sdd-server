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

# zmq socket monitoring event map
EVENT_MAP = {}
for name in dir(zmq):
    if name.startswith('EVENT_'):
        value = getattr(zmq, name)
        EVENT_MAP[value] = name


class LensControlRequester(QObject):

    focus_read_update_signal = pyqtSignal(dict) # signal for focus value read reuslt update
    status_msg_update_signal = pyqtSignal(str) # signal for connection status message
    focus_move_signal = pyqtSignal(bool) # signal for move focus

    def __init__(self, context:zmq.Context, connection:str):
        super().__init__()

        self.__console = ConsoleLogger.get_logger()   # console logger
        self.__console.info(f"+ Lens Controller connection : {connection}")

        self.__connection = connection # connection info.

        # create context for zmq requester
        self.__socket = context.socket(zmq.REQ)
        self.__socket.setsockopt(zmq.RCVBUF .RCVHWM, 1000)
        self.__socket.connect(connection)
        self.__socket.setsockopt(zmq.RCVTIMEO, 1000)
        #self.__lens_control_loop = asyncio.get_event_loop()


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
    
    def focus_init_all(self) -> None:
        try :
            self.__console.info("Initialize all Focus Lens")
            message = {"function":"init_all"}
            request_string = json.dumps(message)
            self.__socket.send_string(request_string)
            self.__console.info(f"Request : {request_string}")

            # reply
            response = self.__socket.recv_string()
            self.__console.info(f"Reply : {response}")

        except zmq.error.ZMQError as e:
            self.__console.error(f"{e}")
        except zmq.error.Again as e:
            self.__console.error(f"Receive timeout")
    

    def read_focus(self):
        """ read focus value """
        self.__console.info("read focus all")
        self._read_focus_request(-1)
        #asyncio.run_coroutine_threadsafe(self._read_focus_request(-1), self.__lens_control_loop)

    async def _read_focus_request(self, id:int):
        try:
            message = {"function":"read_focus"}
            await self.__socket.send_string(message)
            self.__console.info(f"send {message}")
            try:
                response = await asyncio.wait_for(self.__socket.recv_string(), timeout=1.0)
                self.__console.info(f"response : {response}")
                focus_value = json.loads(response)
                self.focus_read_update_signal.emit(focus_value)
            except asyncio.TimeoutError:
                self.__console.warning(f"Timeout Error")
        except zmq.error.ZMQError as e:
            self.__console.error(f"{e}")
        except Exception as e:
            self.__console.warning(f"Error Exception")


    def focus_move(self, user_id:int, value:int):
        """ set focus value """
        try:
            message = {
                "id":user_id,
                "function":"move_focus",
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
        try:
            self.__socket.close()
        except Exception as e:
            self.__console.error(f"{e}")
        except zmq.ZMQError as e:
            self.__console.error(f"Context termination error : {e}")

        
        
