
#include "dk.level2.gateway.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>

using namespace flame;

static dk_level2_gateway* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new dk_level2_gateway(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool dk_level2_gateway::on_init(){

    //connect
    return true;
}

void dk_level2_gateway::on_loop(){

    /* create message */
    map<string, string> status;
    status.insert(make_pair("Product", "test"));
    json info = status;
    string status_message = info.dump();

    /* camera grabbing info publish */
    string topic = fmt::format("{}/{}", get_name(), "/status");
    pipe_data topic_msg(topic.data(), topic.size());
    pipe_data end_msg(status_message.data(), status_message.size());
    get_port("status")->send(topic_msg, zmq::send_flags::sndmore);
    get_port("status")->send(end_msg, zmq::send_flags::dontwait);

}

void dk_level2_gateway::on_close(){
    
}

void dk_level2_gateway::on_message(){
    
}
