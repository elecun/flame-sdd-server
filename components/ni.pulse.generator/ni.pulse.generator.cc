
#include "ni.pulse.generator.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>

#include <NIDAQmx.h>
#include <iostream>
#include <stdexcept>
#include <string>

using namespace flame;

static ni_pulse_generator* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new ni_pulse_generator(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool ni_pulse_generator::on_init(){

    //connect
    return true;
}

void ni_pulse_generator::on_loop(){
    

    static int n = 0;
    std::string message = fmt::format("push {}",n);
    zmq::message_t zmq_message(message.data(), message.size());
    this->get_dataport()->send(zmq_message, zmq::send_flags::dontwait);

    logger::info("{} : {}", _THIS_COMPONENT_, message);

    n++;
}

void ni_pulse_generator::on_close(){
    
}

void ni_pulse_generator::on_message(){
    
}
