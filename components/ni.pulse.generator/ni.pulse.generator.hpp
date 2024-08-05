/**
 * @file ni.pulse.generator.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief External Trigger for Industrial Camera with NIDAQ
 * @version 0.1
 * @date 2024-06-30
 * 
 * @copyright Copyright (c) 2024
 * 
 */

#ifndef FLAME_NI_PULSE_GENERATOR_HPP_INCLUDED
#define FLAME_NI_PULSE_GENERATOR_HPP_INCLUDED

#include <flame/component/object.hpp>


class ni_pulse_generator : public flame::component::object {
    public:
        ni_pulse_generator() = default;
        virtual ~ni_pulse_generator() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        string _device_name { "Dev1" };
        string _counter_channel { "ctr0" };

}; /* class */

EXPORT_COMPONENT_API


#endif