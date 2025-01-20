/**
 * @file computar.vlmpz.controller.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief Computar VLMPZ lens connect controller
 * @version 0.1
 * @date 2025-01-08
 * 
 * @copyright Copyright (c) 2025
 * 
 */

#ifndef FLAME_COMPUTAR_VLMPZ_CONTROLLER_HPP_INCLUDED
#define FLAME_COMPUTAR_VLMPZ_CONTROLLER_HPP_INCLUDED

#include <flame/component/object.hpp>
#include <map>
#include <vector>
#include <string>
#include <thread>
#include <condition_variable>
#include <mutex>
#include <functional>
#include <queue>
#include <thread>

/* lens controller */
//#include "include/LensConnect.h"
#include "include/LensCtrl.h"
#include "include/defVal.h"

using namespace std;


class controlImpl {
    public:
        controlImpl(string parent_name, int device_id, int camera_id);
        virtual ~controlImpl() = default;

        /* functions */
        bool open();    // device open
        void close();   // device close

        /* function supports (working in thread)*/
        void focus_initialize();  //focus initialize
        void iris_initialize();   //iris initialize
        void focus_move(int value); //focus move
        void iris_move(int value);  //iris move
        int read_focus_position(); //read focus position

        /* push the api in queue */
        bool caller(const json& api);

        int get_device_id() { return _lens_device_id; }
        int get_camera_id() { return _lens_camera_id; }
        string get_sn() { return _lens_device_sn; }

        /* USB related functions */
        int UsbGetNumDevices(unsigned int* numDevices);
        int UsbGetSnDevice(unsigned short index, char* SnString);
        int UsbOpen(unsigned long deviceNumber);
        void UsbClose();
        int UsbSetConfig();
        int UsbRead(unsigned short segmentOffset, unsigned short receiveSize);
        unsigned short UsbRead2Bytes();
        unsigned int CountRead();
        int UsbWrite(unsigned short segmentOffset, unsigned short writeData);

        /* lens control low-level functions */
        int CapabilitiesRead(unsigned short* capabilities);
        int Status2ReadSet();
        int FocusParameterReadSet();
        int FocusCurrentAddrReadSet();
        int IrisParameterReadSet();
        int IrisCurrentAddrReadSet();
        int FocusInit();
        int StatusWait(unsigned short segmentOffset, unsigned short statusMask, int waitTime);
        void MsSleep(int n);
        int IrisInit();
        int WaitCalc(unsigned short moveValue, int speedPPS);
        int FocusMove(unsigned short addrData);
        int DeviceMove(unsigned short segmentOffset, unsigned short *addrData, unsigned short mask , int waitTime);
        int IrisMove(unsigned short addrData);

    private:
        void run_process(); /* run process in thread */
        void execute(const json& api);
       
    private:

        HID_SMBUS_DEVICE connectedDevice;
        unsigned char i2cAddr = I2CSLAVEADDR * 2;
        unsigned char receivedData[80];

        unique_ptr<thread> _control_worker; /* control process in thread */
        mutex _mutex; /* mutex for thread */
        atomic<bool> _is_running = true;
        queue<function<void()>> _f_queue;
        condition_variable  _cv;
        string _parent_name;

        /* scanned lens info. */
        string  _lens_device_sn;    // lens serial number
        unsigned long     _lens_device_id = -1;// lens device id
        int     _lens_camera_id = -1; //lens user id

        map<string, int> function_code {
            {"focus_initialize", 1},
            {"iris_initialize", 2},
            {"move_focus", 3},
            {"iris_move", 4}
        };
}; /* class */

class computar_vlmpz_controller : public flame::component::object {
    public:
        computar_vlmpz_controller() = default;
        virtual ~computar_vlmpz_controller() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        /* pipieline processing */
        void _lens_control_responser(json parameters); // lens control port

    private:
        /* task impl. of status publisher for every 1 sec */
        void _subtask_status_publish(json parameters);

        /* USB device scan to find lens */
        void _usb_device_scan();

    private:

        /* pipeline processing handle*/
        bool _thread_stop_signal { false };
        pthread_t _lens_control_responser_handle;

        /* scanned lens info. */
        vector<string> _lens_device_sn; // lens serial number
        map<int, controlImpl*> _lens_controller_map; // device id, controller instance
        map<int, int> _device_id_mapper; // user id : device id

    private:
        /* sub-tasks */
        pthread_t _subtask_status_publisher; /* for status publish */

}; /* class */

EXPORT_COMPONENT_API

#endif

