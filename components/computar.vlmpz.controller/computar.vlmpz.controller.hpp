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

/* lens controller */
#include "include/LensConnect.h"
#include "include/LensCtrl.h"

using namespace std;

class controlImpl {
    public:
        controlImpl(int id, string sn):_lens_id(id), _lens_device_sn(sn){ };
        virtual ~controlImpl() = default;

        /* functions */
        bool open(int device_idx);    //open device
        void close();   //close device

        /* function supports (working in thread)*/
        void focus_initialize();  //focus initialize
        void iris_initialize();   //iris initialize
        void focus_move(int value); //focus move
        void iris_move(int value);  //iris move

        /* push the api in queue */
        bool caller(const json& api);

        int get_id() { return _lens_id; }
        string get_sn() { return _lens_device_sn; }

    private:
        void run_process(); /* run process in thread */
        void execute(const json& api);
       
    private:
        unique_ptr<thread> _control_worker; /* control process in thread */
        mutex _mutex; /* mutex for thread */
        bool _is_running = true;
        queue<function<void()>> _f_queue;
        condition_variable  _cv;

        /* scanned lens info. */
        string  _lens_device_sn; // id, lens serial number
        int     _lens_id = 0;

        map<string, int> function_code {
            {"focus_initialize", 1},
            {"iris_initialize", 2},
            {"focus_move", 3},
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
        /* task impl. of status publisher for every 1 sec */
        void _subtask_status_publish(json parameters);

        /* USB device scan to find lens */
        void _usb_device_scan();

    private:
        /* scanned lens info. */
        vector<string> _lens_device_sn; // id, lens serial number
        map<int, unique_ptr<controlImpl>> _device_map;

    private:
        /* sub-tasks */
        pthread_t _subtask_status_publisher; /* for status publish */

}; /* class */

EXPORT_COMPONENT_API

#endif
