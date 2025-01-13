/**
 * @file system.status.monitor.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief System Status Monitor Component
 * @version 0.1
 * @date 2025-01-03
 * 
 * @copyright Copyright (c) 2025
 * 
 */

#ifndef FLAME_SYSTEM_STATUS_MONITOR_HPP_INCLUDED
#define FLAME_SYSTEM_STATUS_MONITOR_HPP_INCLUDED

#include <flame/component/object.hpp>
#include "system_usage.hpp"

class system_status_monitor : public flame::component::object {
    public:
        system_status_monitor() = default;
        virtual ~system_status_monitor() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        CPU_stats _t1;


}; /* class */

EXPORT_COMPONENT_API

#endif