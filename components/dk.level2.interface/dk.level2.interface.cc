
#include "dk.level2.interface.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>
#include <chrono>
#include <filesystem>
#include <sstream>

using namespace flame;

static dk_level2_interface* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new dk_level2_interface(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool dk_level2_interface::on_init(){

    _show_raw_packet.store(get_profile()->parameters().value("show_raw_packet", false));
    lv2_access_ip = get_profile()->parameters().value("level2_access_ip", "127.0.0.1"); //level2 server ip address
    lv2_access_port = get_profile()->parameters().value("level2_access_port", 9999);
    sdd_host_ip = get_profile()->parameters().value("sdd_host_ip", "127.0.0.1"); //sdd server ip address
    sdd_host_port = get_profile()->parameters().value("sdd_host_port", 9998);

    /* client socket (lv2 server access )*/
    _client_socket = tcp::socket(_io_context);
    _lv2_endpoint = tcp::endpoint(address::from_string(lv2_access_ip), lv2_access_port);


    // tcp::acceptor acceptor(_io_context, tcp::endpoint(tcp::v4(), sdd_host_port));
    // std::cout << "Server started. Waiting for clients..." << std::endl;

    // _worker_container.emplace_back(&dk_level2_interface::_server_proc, this);

    return true;
}

void dk_level2_interface::on_loop(){

    /* send alive packet for every 30s */
    dk_sdd_alive alive_packet = generate_packet_alive();

    /* show raw packet data */
    if(_show_raw_packet.load())
        show_raw_packet(reinterpret_cast<char*>(&alive_packet), sizeof(alive_packet));


}

void dk_level2_interface::on_close(){


    
}

void dk_level2_interface::on_message(){
    
}

dk_sdd_alive dk_level2_interface::generate_packet_alive(){

    dk_sdd_alive packet;

    /* 1. cTcCode (4) */
    string code = "1199";
    std::copy_n(code.begin(), code.size(), packet.cTcCode);

    /* 2. cDate (14) */
    string date = get_current_time();
    std::copy_n(date.begin(), date.size(), packet.cDate);

    /* 3. cTcLength (6) */
    std::stringstream s1;
    s1 << std::setw(sizeof(packet.cTcLength)) << std::setfill('0') << sizeof(dk_sdd_alive);
    std::string str_size = s1.str();
    std::copy_n(str_size.begin(), str_size.size(), packet.cTcLength);

    /* 4. cCount (4) */
    std::stringstream s2;
    s2 << std::setw(sizeof(packet.cCount)) << std::setfill('0') << _alive_msg_counter++;
    std::string str_counter = s2.str();
    if(_alive_msg_counter>9999)
        _alive_msg_counter = 0;
    std::copy_n(str_counter.begin(), str_counter.size(), packet.cCount);

    /* 5. reserved (22) */
    memset(packet.cSpare, '0', sizeof(packet.cSpare));

    return packet;

}

void dk_level2_interface::_server_proc(){

    // tcp::acceptor acceptor(_io_context, tcp::endpoint(tcp::v4(), sdd_host_port));
    // logger::info("[{}] Server({}) started. Waiting for clients...", get_name(), sdd_host_port);

    // while(!_worker_stop.load()){
    //     tcp::socket socket(_io_context);
    //     tcp::socket socket = acceptor.accept();
    //     logger::info("[{}] New client connected", get_name());

    //     try{
    //         boost::system::error_code error;
    //         boost::asio::streambuf buffer;
    //         boost::asio::read(socket, buffer, error);

    //         if(error && error != boost::asio::error::eof){
    //             logger::error("[{}] Receive failed: {}", get_name(), error.message());
    //         }
    //         else{
    //             std::istream is(&buffer);
    //             std::string data;
    //             std::getline(is, data);
    //             logger::info("[{}] Received data : {}", get_name(), data);
    //         }
    //     }
    //     catch(const std::exception& e){
    //         logger::error("[{}] Exception : {}", get_name(), e.what());
    //     }
    // }

}

string dk_level2_interface::get_current_time(){

    /* get local time */
    auto now = std::chrono::system_clock::now();
    std::time_t time = std::chrono::system_clock::to_time_t(now);
    std::tm local_tm = *std::localtime(&time);

    /* time to string */
    std::stringstream ss_time;
    ss_time << std::put_time(&local_tm, "%Y%m%d%H%M%S");

    return ss_time.str();
}

void dk_level2_interface::show_raw_packet(char* data, size_t size){
    std::stringstream log_stream;
    log_stream.write(data, size);
    logger::info("[{}](size:{}){}", get_name(), log_stream.str().size(), log_stream.str());
}

void dk_level2_interface::lv2_connect(){
    boost::asio::ip::tcp::resolver::results_type endpoints;
    try {
            endpoints = _resolver_.resolve(host_, std::to_string(port_));
        } catch (const boost::system::system_error& error) {
            std::cerr << "Resolve failed: " << error.what() << std::endl;
            reconnect();
            return;
        }

        socket_ = std::make_unique<boost::asio::ip::tcp::socket>(io_context_);
        boost::asio::async_connect(*socket_, endpoints,
            [this](const boost::system::error_code& error, const boost::asio::ip::tcp::endpoint& /*endpoint*/) {
                if (!error) {
                    std::cout << "Connected to server!" << std::endl;
                    start_read();
                } else {
                    std::cerr << "Connect failed: " << error.message() << std::endl;
                    reconnect();
                }
            });
}