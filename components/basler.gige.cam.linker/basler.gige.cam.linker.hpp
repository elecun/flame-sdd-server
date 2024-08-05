/**
 * @file basler.gige.cam.linker.hpp
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

#ifndef FLAME_BASLER_GIGE_CAM_LINKER_HPP_INCLUDED
#define FLAME_BASLER_GIGE_CAM_LINKER_HPP_INCLUDED

#include <flame/component/object.hpp>
#include <pylon/PylonIncludes.h>
#include <pylon/BaslerUniversalInstantCamera.h>
#include <map>
#include <unordered_map>
#include <vector>
#include <thread>
#include <string>
#include <atomic>
#include <boost/lockfree/queue.hpp>

using namespace std;
using namespace Pylon;
using namespace GenApi;
using namespace boost;

class basler_gige_cam_linker : public flame::component::object {
    public:
        basler_gige_cam_linker() = default;
        virtual ~basler_gige_cam_linker() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        void _image_stream_task(int camera_id, CBaslerUniversalInstantCamera* camera, json parameters);
        void _status_monitor_task(json parameters);

        void _publish_status(); //publish camera work status for every seconds

    private:
        unordered_map<int, pthread_t> _camera_grab_worker;  // camera id, grab thread
        unordered_map<int, unsigned long long> _camera_grab_counter; // camera id, grab counter
        unordered_map<int, json> _camera_status; // camera id, status
        map<int, CBaslerUniversalInstantCamera*> _cameras; // camera id, camera device instance
        std::atomic<bool> _thread_stop_signal { false };

        pthread_t _status_monitor; /* for status publish */
        



}; /* class */

EXPORT_COMPONENT_API


#endif