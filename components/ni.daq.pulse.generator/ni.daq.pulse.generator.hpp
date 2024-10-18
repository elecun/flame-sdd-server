/**
 * @file ni.daq.pulse.generator
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief Trigger Signal Generator with NI DAQ 
 * @version 0.1
 * @date 2024-07-24
 * 
 * @copyright Copyright (c) 2024
 * 
 */

#ifndef FLAME_NI_DAQ_PULSE_GENERATOR_HPP_INCLUDED
#define FLAME_NI_DAQ_PULSE_GENERATOR_HPP_INCLUDED

#include <flame/component/object.hpp>
#include <string>
#include <NIDAQmx.h>
#include <atomic>

class ni_daq_pulse_generator : public flame::component::object {
    public:
        ni_daq_pulse_generator() = default;
        virtual ~ni_daq_pulse_generator() = default;

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
        void _response(json parameters);

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
        pthread_t _subscriber_handle;   // pub/sub
        pthread_t _responser_handle;    // req/rep
        std::atomic<bool> _thread_stop_signal { false };
        

}; /* class */

EXPORT_COMPONENT_API


#endif