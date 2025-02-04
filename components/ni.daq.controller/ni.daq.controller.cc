
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

    _worker_stop.store(true);

    for_each(_worker_container.begin(), _worker_container.end(), [](thread& t){ // do in parallel, available for C++17
        if(t.joinable()){
            t.join();
        }
    });

    _worker_container.clear();
}

void ni_daq_controller::on_message(){
    
}

void ni_daq_controller::_counter_channel_proc(){

    while(!_worker_stop.load()){
        this_thread::sleep_for(chrono::milliseconds(500));
    }

}

void ni_daq_controller::_di_channel_proc(){

    while(!_worker_stop.load()){
        this_thread::sleep_for(chrono::milliseconds(500));
    }
}

void ni_daq_controller::_control_proc(){

    try{
        while(!_worker_stop.load()){
            try {
                pipe_data message;
                zmq::recv_result_t result = get_port("manual_control")->recv(message, zmq::recv_flags::none);
                if(result.has_value()){ // failed
                    if(result.value() == EAGAIN){
                        continue;
                    }
                    else{
                        string msg_str(static_cast<char*>(message.data()), message.size());
                        // parse message here
                    }
                }
            }
            catch(const zmq::error_t& e){
                if(e.num() == ETERM){
                    logger::error("[{}] Pipeline context was terminated. stopping receiver...", get_name());
                    break;
                }
                throw;
            }

        }

    }
    catch(const zmq::error_t& e){
        logger::error("[{}] Pipeline error : {}", get_name(), e.what()); // ETERM
    }
    catch(const std::runtime_error& e){
        logger::error("[{}] Runtime error occurred!", get_name());
    }
    catch(const json::parse_error& e){
        logger::error("[{}] message cannot be parsed. {}", get_name(), e.what());
    }

}
