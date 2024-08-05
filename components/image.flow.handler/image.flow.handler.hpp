/**
 * @file image.flow.handler.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief Image Stream data flow handler component
 * @version 0.1
 * @date 2024-08-01
 * 
 * @copyright Copyright (c) 2024
 * 
 */

#ifndef FLAME_IMAGE_FLOW_HANDLER_HPP_INCLUDED
#define FLAME_IMAGE_FLOW_HANDLER_HPP_INCLUDED

#include <flame/component/object.hpp>
#include <vector>
#include <queue>
#include <string>
#include <opencv2/opencv.hpp>

using namespace std;


class image_flow_handler : public flame::component::object {
    public:
        image_flow_handler() = default;
        virtual ~image_flow_handler() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        void _image_puller(json parameters);

    private:
        pthread_t _stream_puller_handle;
        std::atomic<bool> _thread_stop_signal { false };

        queue<vector<uint8_t>> _image_container;

}; /* class */

EXPORT_COMPONENT_API


#endif