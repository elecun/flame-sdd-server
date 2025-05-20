/**
 * @file system.echo.hpp
 * @author byunghun hwang <bh.hwang@iae.re.kr>
 * @brief System Echo Component
 * @version 0.1
 * @date 2025-05-19
 * 
 * @copyright Copyright (c) 2025
 * 
 */

#ifndef FLAME_SYSTEM_ECHO_HPP_INCLUDED
#define FLAME_SYSTEM_ECHO_HPP_INCLUDED

#include <flame/component/object.hpp>

class system_echo : public flame::component::object {
    public:
        system_echo() = default;
        virtual ~system_echo() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        atomic<bool> _worker_stop {false};
        atomic<bool> _show_debug {false};
        thread _echo_worker;

    private:
        void _echo_worker_task();

}; /* class */

EXPORT_COMPONENT_API

#endif