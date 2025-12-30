/**
 * @file basler.gige.cam.grabber.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief Basler Gigabit Ethernet Camera Capture by external trigger
 * @version 0.1
 * @date 2024-06-30
 * 
 * @copyright Copyright (c) 2024
 * 
 */

/*
Hardware Triggering Setting parameters

TriggerSelector = FrameStart
TriggerMode = On
TriggerActivation = RisingEdge
TriggerSource = Line1

*/

// Note! FrameEnd Triggering is ....

#ifndef FLAME_BASLER_GIGE_CAM_GRABBER_HPP_INCLUDED
#define FLAME_BASLER_GIGE_CAM_GRABBER_HPP_INCLUDED

#include <flame/component/object.hpp>
#include <map>
#include <unordered_map>
#include <vector>
#include <thread>
#include <string>
#include <atomic>
#include <atomic>

#include <pylon/PylonIncludes.h>
#include <pylon/BaslerUniversalInstantCamera.h>

using namespace std;
using namespace Pylon;
using namespace GenApi;

class basler_gige_cam_grabber : public flame::component::object {
    public:
        basler_gige_cam_grabber() = default;
        virtual ~basler_gige_cam_grabber() = default;

        /* default interface functions */
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message(const component::message_t& msg) override;


    private:
        /* for device handle */
        map<int, CBaslerUniversalInstantCamera*> _device_map; // (camera id, instance)

        /* for worker threads handle */
        unordered_map<int, thread> _camera_grab_worker; // (camera id, thread)
        unordered_map<int, thread> _camera_control_worker; // (camera id, thread)
        thread _image_stream_control_worker;    //image stream control worker
        thread _level2_dispatch_worker; //level2 data interface
        thread _line_signal_worker; //hmd entry signal subscriber
        atomic<bool> _worker_stop {false};
        atomic<bool> _image_stream_enable {false};
        string _preset_path;

        /* camera-related status */
        unordered_map<int, atomic<unsigned long long>> _camera_grab_counter; // (camera id, counter)
        unordered_map<string, json> _camera_status; // (camera id(string), status)
        unordered_map<int, atomic<int>> _camera_exposure_time; // (camera id, exposure time)
        unordered_map<int, atomic<double>> _camera_coreboard_temperature; // (camera id, coreboard temperature)

        /* for profiles */
        atomic<bool> _prof_realtime_monitoring {false};

    private:
        /* subtasks */
        void _camera_control_task(int camera_id, CBaslerUniversalInstantCamera* camera); /* camera control */
        void _image_stream_task(int camera_id, CBaslerUniversalInstantCamera* camera, json parameters); /* image capture & flush in pipeline */ 
        void _image_stream_control_task(); /* image stream control task */    
        void _level2_dispatch_task(); /* level2 data interface */

}; /* class */

EXPORT_COMPONENT_API


#endif