/**
 * @file focus.lens.controller.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief Motorized Focus Lens Controller Component
 * @version 0.1
 * @date 2025-01-03
 * 
 * @copyright Copyright (c) 2025
 * 
 */

#ifndef FLAME_FOCUS_LENS_CONTROLLER_HPP_INCLUDED
#define FLAME_FOCUS_LENS_CONTROLLER_HPP_INCLUDED

#include <flame/component/object.hpp>

class focus_lens_controller : public flame::component::object {
    public:
        focus_lens_controller() = default;
        virtual ~focus_lens_controller() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        /* task impl. of status publisher for every 1 sec */
        void _subtask_status_publish(json parameters);
        

    private:
        /* sub-tasks */
        pthread_t _subtask_status_publisher; /* for status publish */

}; /* class */

EXPORT_COMPONENT_API

#endif

