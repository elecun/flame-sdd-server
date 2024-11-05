
#include "dk.level2.terminal.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>
#include <filesystem>

using namespace flame;

static dk_level2_terminal* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new dk_level2_terminal(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool dk_level2_terminal::on_init(){

    /* for level2 data with req/rep */
    thread responser = thread(&dk_level2_terminal::_response, this, get_profile()->parameters());
    _responser_handle = responser.native_handle();
    responser.detach();

    return true;
}

void dk_level2_terminal::on_loop(){

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

void dk_level2_terminal::on_close(){

    /* cancel the thread */
    _thread_stop_signal.store(true);
    pthread_cancel(_responser_handle);
    pthread_join(_responser_handle, nullptr);
    
}

void dk_level2_terminal::on_message(){
    
}

void dk_level2_terminal::_response(json parameters){

    pthread_setcancelstate(PTHREAD_CANCEL_ENABLE, nullptr);
    pthread_setcanceltype(PTHREAD_CANCEL_DEFERRED, nullptr);

    while(!_thread_stop_signal.load()){
        try{
            pipe_data request;

            zmq::recv_result_t request_result = get_port("level2_terminal")->recv(request, zmq::recv_flags::none);

            if(request_result){
                std::string message(static_cast<char*>(request.data()), request.size());
                auto json_data = json::parse(message);

                /* parse received data */
                _parse(json_data);

                if(json_data.contains("LOT")){
                    bool lot_number = json_data["LOT"].get<string>();

                    _parse

                    /* create */
                    if(triggered){
                        _start_pulse_generation(_daq_pulse_freq, _daq_pulse_samples, _daq_pulse_duty);
                        logger::info("[{}] Start generating camera triggering...", get_name());
                    }
                    else {
                        _stop_pulse_generation();
                        logger::info("[{}] Stop generating camera triggering...", get_name());
                    }
                }

                logger::info("Received Message : {}", json_data.dump());

                // reply
                json reply_message = {
                    {"response_code", 1}
                };
                pipe_data reply(reply_message.dump().size());
                memcpy(reply.data(), reply_message.dump().data(), reply_message.dump().size());
                get_port("manual_control")->send(reply, zmq::send_flags::none);
            }
        }
        catch(const json::parse_error& e){
            logger::error("[{}] message cannot be parsed. {}", get_name(), e.what());
        }
        catch(const std::runtime_error& e){
            logger::error("[{}] Runtime error occurred!", get_name());
        }
        catch(const zmq::error_t& e){
            logger::error("[{}] Pipeline error : {}", get_name(), e.what());
        }
    }
}

void dk_level2_terminal::_parse(json data){

}