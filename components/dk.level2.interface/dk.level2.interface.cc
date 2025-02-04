
#include "dk.level2.interface.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>
#include <filesystem>

using namespace flame;

static dk_level2_interface* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new dk_level2_interface(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool dk_level2_interface::on_init(){

    lv2_access_ip = get_profile()->parameters().value("lv2_access_ip", "127.0.0.1");
    lv2_access_port = get_profile()->parameters().value("lv2_access_port", 9999);
    sdd_host_ip = get_profile()->parameters().value("lv2_host_ip", "127.0.0.1");
    sdd_host_port = get_profile()->parameters().value("lv2_host_port", 9998);

    
    // tcp::acceptor acceptor(_io_context, tcp::endpoint(tcp::v4(), sdd_host_port));
    // std::cout << "Server started. Waiting for clients..." << std::endl;

    _worker_container.emplace_back(&dk_level2_interface::_server_proc, this);

    return true;
}

void dk_level2_interface::on_loop(){



}

void dk_level2_interface::on_close(){


    
}

void dk_level2_interface::on_message(){
    
}

void dk_level2_interface::_server_proc(){

    tcp::acceptor acceptor(_io_context, tcp::endpoint(tcp::v4(), sdd_host_port));
    logger::info("[{}] Server({}) started. Waiting for clients...", get_name(), sdd_host_port);

    while(!_worker_stop.load()){
        tcp::socket socket(_io_context);
        tcp::socket socket = acceptor.accept();
        logger::info("[{}] New client connected", get_name());

        try{
            boost::system::error_code error;
            boost::asio::streambuf buffer;
            boost::asio::read(socket, buffer, error);

            if(error && error != boost::asio::error::eof){
                logger::error("[{}] Receive failed: {}", get_name(), error.message());
            }
            else{
                std::istream is(&buffer);
                std::string data;
                std::getline(is, data);
                logger::info("[{}] Received data : {}", get_name(), data);
            }
        }
        catch(const std::exception& e){
            logger::error("[{}] Exception : {}", get_name(), e.what());
        }
    }

}