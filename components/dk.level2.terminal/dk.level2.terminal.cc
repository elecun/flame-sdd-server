
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
            pipe_data request_in;

            zmq::recv_result_t request_in_result = get_port("level2_terminal_in")->recv(request_in, zmq::recv_flags::none);
            string lot_number = "";

            /* terminal in */
            if(request_in_result){
                std::string message(static_cast<char*>(request_in.data()), request_in.size());
                auto json_data = json::parse(message);

                /* parse received data */
                lot_number = _parse(json_data);

                // level2_terminal_in reply
                _reply("level2_terminal_in", 1);
            }

            /* terminal out */
            if(!lot_number.empty()){
                logger::info("[{}] LOT Number : {}", get_name(), lot_number);
                json msg {
                    {"LOT", lot_number}
                };

                _request("level2_terminal_out", msg);
                _wait_response("level2_terminal_out");
                
            }
            else{
                logger::warn("[{}] No LOT number contained", get_name());
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

string dk_level2_terminal::_parse(json data){
    if(data.contains("LOT")){
        string lot_number = data["LOT"].get<string>();
        return lot_number;
    }
    return "";
}

void dk_level2_terminal::_reply(string port_name, int response_code){
    json reply_message = {
        {"response_code", response_code}
    };
    pipe_data reply(reply_message.dump().size());
    memcpy(reply.data(), reply_message.dump().data(), reply_message.dump().size());
    get_port(port_name)->send(reply, zmq::send_flags::none);
}

bool dk_level2_terminal::_wait_response(string port_name){
    pipe_data res;
    zmq::recv_result_t res_result = get_port(port_name)->recv(res, zmq::recv_flags::none);

    if(res_result){
        std::string message(static_cast<char*>(res.data()), res.size());
        auto json_data = json::parse(message);
        if(json_data.contains("response_code")){
            int code = json_data["response_code"].get<int>();
            logger::info("[{}] Responsed (code:{})", get_name(), code);
        }
        return true;
    }

    return false;
}

void dk_level2_terminal::_request(string port_name, json data){
    string dump_data = data.dump();
    pipe_data request_message(dump_data.size());
    memcpy(request_message.data(), dump_data.c_str(), dump_data.size());
    zmq::recv_result_t request_message_result = get_port(port_name)->send(request_message, zmq::send_flags::none);
}