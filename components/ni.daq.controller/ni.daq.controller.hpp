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
#include <NIDAQmx.h>

class ni_daq_controller : public flame::component::object {
    public:
        ni_daq_controller() = default;
        virtual ~ni_daq_controller() = default;

        /* common component interfaces */
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        /* subtasks */
        TaskHandle _task_handle_pulse_generation { nullptr };
        TaskHandle _task_handle_dio_reader { nullptr };

    private:
        /* daq parameters */
        string _daq_device_name {""};
        string _daq_counter_channel {""};
        string _daq_di_channel {""};
        double _daq_pulse_freq {30.0};
        double _daq_pulse_duty {0.5};

        thread _daq_control_worker;  /* control message subscriber */
        thread _daq_pulse_generation_worker;    //for Trigger
        thread _daq_dio_read_worker;  //for HMd
        atomic<bool> _worker_stop {false};

    private:
        void _daq_control_task();
        void _daq_pulse_gen_task();
        void _daq_dio_read_task();

        void _publish_hmd_signal(const char* portname, bool value);

        

        /* message instruction via mq */
        

    // private:
    //     /* internal variables & user parameters */
    //     string _device_name {""};
    //     string _counter_channel {""};
    //     string _di_channel {""};
    //     double _counter_pulse_freq {30};
    //     double _counter_pulse_duty {0.5};
    //     long _counter_pulse_off_time_delay {0};

        

        /* for worker handle */
        // vector<thread> _worker_container;

        // /* for worker termination */
        // atomic<bool> _worker_stop {false};


        

}; /* class */

EXPORT_COMPONENT_API


# endif