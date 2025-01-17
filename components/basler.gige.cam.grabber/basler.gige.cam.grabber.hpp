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
#include <pthread.h>
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
        void on_message() override;

    private:
        /* task impl. of status publisher for every 1 sec */
        void _subtask_status_publish(json parameters);

        void _image_stream_task(int camera_id, CBaslerUniversalInstantCamera* camera, json parameters);
        void _status_monitor_task(json parameters);
        void _status_publish();

        void _publish_status(); //publish camera work status for every seconds

    private:

        /* sub-tasks */
        pthread_t _subtask_status_publisher; /* for status publish */

        unordered_map<int, pthread_t> _camera_grab_worker;  // camera id, grab thread
        unordered_map<int, unsigned long long> _camera_grab_counter; // camera id, grab counter
        unordered_map<int, json> _camera_status; // camera id, status
        map<int, CBaslerUniversalInstantCamera*> _device_map; // camera id, camera device instance
        bool _thread_stop_signal { false };

        pthread_t _status_monitor; /* for status publish */

        map<string, int> _method_type { 
            {"batch", 0 },
            {"realtime", 1}
        };
        int _stream_method = 0; //batch mode default
        bool _monitoring = false;
        int _stream_batch_buffer_size = 1000;
        typedef vector<unsigned char> image_data;
        map<int, vector<image_data>> _image_container;
        
        



}; /* class */

EXPORT_COMPONENT_API


#endif