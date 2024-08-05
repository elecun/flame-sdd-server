/**
 * @file dk.ni.daq.handler.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief NI DAQ Handler
 * @version 0.1
 * @date 2024-07-24
 * 
 * @copyright Copyright (c) 2024
 * 
 */

#ifndef FLAME_DK_NI_DAQ_HANDLER_HPP_INCLUDED
#define FLAME_DK_NI_DAQ_HANDLER_HPP_INCLUDED

#include <flame/component/object.hpp>
#include <string>
#include <NIDAQmx.h>
#include <atomic>

class dk_ni_daq_handler : public flame::component::object {
    public:
        dk_ni_daq_handler() = default;
        virtual ~dk_ni_daq_handler() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        /* start or stop the pulse generation continuously */
        bool _start_pulse_generation(double freq, unsigned long long n_pulses, double duty);
        void _stop_pulse_generation();

        void _subscribe(json parameters);

    private:
        string _daq_device_name {""};
        string _daq_counter_channel {""};
        double _daq_pulse_freq {30};
        unsigned long long _daq_pulse_samples { 1000 };
        double _daq_pulse_duty {0.5};
        TaskHandle _handle_pulsegen_task { nullptr };

        /* status */
        std::atomic<bool> _triggering { false };

        /* for manual control */
        pthread_t _subscriber_handle;
        std::atomic<bool> _thread_stop_signal { false };

}; /* class */

EXPORT_COMPONENT_API


#endif