
#include "dk.presdd.inference.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>

using namespace flame;

static dk_presdd_inference* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new dk_presdd_inference(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool dk_presdd_inference::on_init(){
    logger::info("<{}> call dk_presdd_inference on_init", _THIS_COMPONENT_);

    //connect
    return true;
}

void dk_presdd_inference::on_loop(){
    logger::info("<{}> call dk_presdd_inference on_loop", _THIS_COMPONENT_);

    static int n = 0;
    std::string message = fmt::format("push {}",n);
    zmq::message_t zmq_message(message.data(), message.size());
    this->get_dataport()->send(zmq_message, zmq::send_flags::dontwait);

    logger::info("{} : {}", _THIS_COMPONENT_, message);

    n++;
}

void dk_presdd_inference::on_close(){
    logger::info("<{}> call dk_presdd_inference on_close", _THIS_COMPONENT_);
}

void dk_presdd_inference::on_message(){
    logger::info("<{}> call dk_presdd_inference on_message", _THIS_COMPONENT_);
}
