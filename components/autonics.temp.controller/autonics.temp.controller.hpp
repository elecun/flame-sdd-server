/**
 * @file autonics.temp.controller.hpp
 * @author Byunghun Hwang (bh.hwang@iae.re.kr)
 * @brief Autonics Temperature Controlller Component (Model : TK4S-T4RN / Modubus RTU - MultiDrop)
 * @version 0.1
 * @date 2025-01-03
 * 
 * @copyright Copyright (c) 2025
 * 
 */

#ifndef FLAME_AUTONICS_TEMP_CONTROLLER_HPP_INCLUDED
#define FLAME_AUTONICS_TEMP_CONTROLLER_HPP_INCLUDED

#include <flame/component/object.hpp>
#include <vector>
#include <modbus/modbus.h>

using namespace std;

class autonics_temp_controller : public flame::component::object {
    public:
        autonics_temp_controller() = default;
        virtual ~autonics_temp_controller() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        /* task impl. of status publisher for every 1 sec */
        void _subtask_status_publish(json parameters);
        void _update_status();
        bool _init_modbus();    /* initialize modbus RTU */

    private:
        /* sub-tasks */
        pthread_t _subtask_status_publisher; /* for status publish */

        /* modbus RTU */
        modbus_t* _modbus_ctx { nullptr };
        vector<int> _slave_addrs;


}; /* class */

EXPORT_COMPONENT_API


#endif