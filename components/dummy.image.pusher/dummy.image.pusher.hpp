/**
 * @file dummy.image.pusher.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief UnitTest Component for General File Staker
 * @version 0.1
 * @date 2025-05-12
 * 
 * @copyright Copyright (c) 2025
 * 
 */

#ifndef FLAME_DUMMY_IMAGE_PUSHER_HPP_INCLUDED
#define FLAME_DUMMY_IMAGE_PUSHER_HPP_INCLUDED

#include <flame/component/object.hpp>
#include <thread>
#include <string>
#include <unordered_map>
#include <queue>
#include <mutex>
#include <vector>
#include <filesystem>

using namespace std;
namespace fs = std::filesystem;

class dummy_image_pusher : public flame::component::object {
    public:
        dummy_image_pusher() = default;
        virtual ~dummy_image_pusher() = default;

        /* common interface function */
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message(const component::message_t& msg) override;

    private:
        /* worker */
        unordered_map<int, thread> _push_worker; // (stream id, thread)
        atomic<bool> _worker_stop {false};

    private:
        /* subtasks */
        void _image_push_task(int stream_id, const string pipename, const string sample_image);

        /* useful functions */
        string get_current_time();


}; /* class */

EXPORT_COMPONENT_API


#endif