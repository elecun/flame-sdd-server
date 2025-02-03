
#include "ni.daq.controller.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>
#include <algorithm>
#include <execution> // parallel

using namespace flame;

static ni_daq_controller* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new ni_daq_controller(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}


bool ni_daq_controller::on_init(){

    /* read profile */
    _device_name = get_profile()->parameters().value("device_name", "Dev1");
    _counter_channel = get_profile()->parameters().value("counter_channel", "ctr0:1");
    _di_channel = get_profile()->parameters().value("di_channel", "port0/line0:7");
    _counter_pulse_freq = get_profile()->parameters().value("counter_pulse_freq", 30.0);
    _counter_pulse_duty = get_profile()->parameters().value("counter_pulse_duty", 0.5);
    _counter_pulse_off_time_delay = get_profile()->parameters().value("counter_pulse_off_time_delay", 0);

    /* start workers */
    bool auto_start = get_profile()->parameters().value("auto_start", false);
    if(auto_start){
        _worker_container.emplace_back(&ni_daq_controller::_control_proc, this);
        _worker_container.emplace_back(&ni_daq_controller::_counter_channel_proc, this);
        _worker_container.emplace_back(&ni_daq_controller::_di_channel_proc, this);
    }

    return true;
}

void ni_daq_controller::on_loop(){

    
    
}

void ni_daq_controller::on_close(){

    _worker_stop = true;

    for_each(_worker_container.begin(), _worker_container.end(), [](thread& t){ // do in parallel, available for C++17
        if(t.joinable())
            t.join();
    });

    _worker_container.clear();
}

void ni_daq_controller::on_message(){
    
}

void ni_daq_controller::_counter_channel_proc(){

    while(!_worker_stop){
        this_thread::sleep_for(chrono::milliseconds(500));
        logger::info("[{}] counter channel worker is running", get_name());
    }

}

void ni_daq_controller::_di_channel_proc(){

    while(!_worker_stop){
        this_thread::sleep_for(chrono::milliseconds(500));
        logger::info("[{}] di channel worker is running", get_name());
    }

}

void ni_daq_controller::_control_proc(){

    while(!_worker_stop){
        this_thread::sleep_for(chrono::milliseconds(500));
        logger::info("[{}] control worker is running", get_name());
    }

}




void ni_daq_controller::_start_control_worker(){

    thread control_worker = thread(&ni_daq_controller::_control_proc, this);
    _control_worker_handle = control_worker.native_handle();
    control_worker.detach(); //worker thread will be detached from the main thread
    logger::info("[{}] control worker detached", get_name());
}

void ni_daq_controller::_stop_control_worker(){

    /* stop control worker */
    // pthread_cancel(_control_worker_handle);
    // pthread_join(_control_worker_handle, nullptr);
}

/* start thread for di channel */
void ni_daq_controller::_start_di_channel_worker(){

    thread di_channel_worker = thread(&ni_daq_controller::_di_channel_proc, this);
    _di_channel_worker_handle = di_channel_worker.native_handle();
    di_channel_worker.detach();
    logger::info("[{}] di channel worker detached", get_name());
}

/* stop thread for di channel */
void ni_daq_controller::_stop_di_channel_worker(){
}

/* start thread for counter channel */
void ni_daq_controller::_start_counter_channel_worker(){

    thread counter_channel_worker = thread(&ni_daq_controller::_counter_channel_proc, this);
    _counter_channel_worker_handle = counter_channel_worker.native_handle();
    counter_channel_worker.detach();
    logger::info("[{}] counter channel worker detached", get_name());
}

/* stop thread for counter channel */
void ni_daq_controller::_stop_counter_channel_worker(){

    /* stop counter channel worker */
    // pthread_cancel(_counter_worker_handle);
    // pthread_join(_counter_worker_handle, nullptr);
}
