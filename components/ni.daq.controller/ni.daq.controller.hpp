/**
 * @file ni.daq.controller.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief NI DAQ Controller Component
 * @version 0.1
 * @date 2025-02-03
 * 
 * @copyright Copyright (c) 2025
 * 
 */

#ifndef FLAME_NI_DAQ_CONTROLLER_HPP_INCLUDED
#define FLAME_NI_DAQ_CONTROLLER_HPP_INCLUDED

#include <flame/component/object.hpp>
#include <string>
#include <NIDAQmx.h>

class ni_daq_controller : public flame::component::object {
    public:
        ni_daq_controller() = default;
        virtual ~ni_daq_controller() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:

        /* internal worker start/stop instruction */
        void _start_di_channel_worker();
        void _stop_di_channel_worker();
        void _start_counter_channel_worker();
        void _stop_counter_channel_worker();
        void _start_control_worker();
        void _stop_control_worker();

    private:
        /* internal functions */
        void _counter_channel_proc(); /* counter channel worker callback function */
        void _di_channel_proc();    /* digital input channel worker callback function */
        void _control_proc();    /* control worker callback function */

        /* message instruction via mq */
        

    private:
        /* internal variables & user parameters */
        string _device_name {""};
        string _counter_channel {""};
        string _di_channel {""};
        double _counter_pulse_freq {30};
        double _counter_pulse_duty {0.5};
        long _counter_pulse_off_time_delay {0};

        /* for worker handle */
        vector<thread> _worker_container;
        pthread_t _counter_channel_worker_handle;
        pthread_t _di_channel_worker_handle;
        pthread_t _control_worker_handle; //puller

        /* for worker termination */
        volatile bool _worker_stop { false };

        

}; /* class */

EXPORT_COMPONENT_API


# endif