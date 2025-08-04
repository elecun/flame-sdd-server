#include "system.echo.replier.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>

using namespace flame;

static system_echo* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new system_echo(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool system_echo::on_init(){

    try{
        /* read parameters */
        json param = get_profile()->parameters();

        _show_debug.store(param.value("show_debug", false));

        // perform task
        _echo_worker = thread(&system_echo::_echo_worker_task, this);
        logger::info("[{}] System Echo Replier is now running...", get_name());
    }
    catch(json::exception& e){
        logger::error("[{}] Profile Error : {}", get_name(), e.what());
        return false;
    }
    
    return true;
}

void system_echo::on_loop(){

}

void system_echo::on_close(){

    /* work stop signal */
    _worker_stop.store(true);

    /* wait for termination*/
    if(_echo_worker.joinable()){
        _echo_worker.join();
        logger::info("[{}] System Echo Replier worker is now stopped.", get_name());
    }

}

void system_echo::on_message(){

}

void system_echo::_echo_worker_task(){

    while(!_worker_stop.load()){
        try{

            /* recv data */
            pipe_data echo_msg;
            zmq::recv_result_t message_result = get_port("echo")->recv(echo_msg, zmq::recv_flags::none);

            /* echo-back */
            if(message_result){
                string message(static_cast<char*>(echo_msg.data()), echo_msg.size());
                get_port("echo")->send(echo_msg, zmq::send_flags::none);

                if(_show_debug.load()){
                    logger::debug("[{}] Echo Message : {}", get_name(), message);
                }
            }
        }
        catch(const zmq::error_t& e){
            logger::error("[{}] Pipeline error : {}", get_name(), e.what());
            break;
        }
        catch(const std::exception& e){
            logger::error("[{}] Standard Exception : {}", get_name(), e.what());
        }
        catch(const json::parse_error& e){
            logger::error("[{}] message cannot be parsed. {}", get_name(), e.what());
        }
    }

}