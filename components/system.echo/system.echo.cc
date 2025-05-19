#include "system.echo.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>

using namespace flame;

static system_echo* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new system_echo(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool system_echo::on_init(){

    _echo_worker = thread(&system_echo::_echo_worker, this);

    logger::info("[{}] System echo responser is now running...", get_name());
    
    return true;
}

void system_echo::on_loop(){

}

void system_echo::on_close(){

}

void system_echo::on_message(){

}

void system_echo::_echo_worker_task(){

    try{

        string portname { "echo" };

        while(!_worker_stop.load()){

            zmq::multipart_t msg_multipart;
            bool success = msg_multipart.recv(*get_port(portname));

            if(success){
                //echo back
                msg_multipart.send(*get_port(portname));
                logger::info("[{}] Echo-Back", get_name());
            }

        }
    }
    catch(const zmq::error_t& e){
        logger::error("[{}] Pipeline error : {}", get_name(), e.what());
    }
    catch(const std::runtime_error& e){
        logger::error("[{}] Runtime error occurred!", get_name());
    }
    catch(const json::parse_error& e){
        logger::error("[{}] message cannot be parsed. {}", get_name(), e.what());
    }

}