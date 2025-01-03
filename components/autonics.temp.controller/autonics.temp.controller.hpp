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


class dk_local_temp_indicator : public flame::component::object {
    public:
        dk_local_temp_indicator() = default;
        virtual ~dk_local_temp_indicator() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:

}; /* class */

EXPORT_COMPONENT_API


#endif