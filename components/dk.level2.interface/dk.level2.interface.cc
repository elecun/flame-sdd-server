
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
    _alive_interval = get_profile()->parameters().value("alive_interval", 1);

    /* client */
    try{
        _client_worker = thread(&dk_level2_interface::_do_client_work, this, get_profile()->parameters());
        _server_worker = thread(&dk_level2_interface::_do_server_work, this, get_profile()->parameters());
    }
    catch(std::exception& e) {
        logger::error("[{}] Create client exception : {}", get_name(), e.what());
    }

    return true;
}

void dk_level2_interface::_do_client_work(json parameters){

    logger::info("[{}] Trying to access to Level2 {}:{}", get_name(), lv2_access_ip, lv2_access_port);
    tcp_socket<>* _tcp_socket = nullptr;

    // _tcp_socket = new tcp_socket<>([this](int error_code, std::string error_msg){
    //     logger::error("[{}] Socket creation error {}", get_name(), error_code);
    // });
    // _tcp_socket->on_socket_closed = [this](int error_code){
    //     logger::info("[{}] Connection Closed({})", get_name(), error_code);
    // };

    while(!_worker_stop.load()){
        try{
            
            /* tcp socket is required */
            if(!_tcp_socket){
                /* create new socket */
                _tcp_socket = new tcp_socket<>([this](int error_code, std::string error_msg){
                    logger::error("[{}] Socket creation error {}", get_name(), error_code);
                });
                _tcp_socket->on_socket_closed = [this](int error_code){
                    logger::info("[{}] Connection Closed({})", get_name(), error_code);
                };

                logger::info("[{}] TCP socket is created", get_name());
            }
            else{
                if(!_tcp_socket->is_available()){

                    int alive_time = 0;
                    _tcp_socket->connect(lv2_access_ip, lv2_access_port, [&] {
                        logger::info("[{}] Connected to Level2 server successfully", get_name());
                        alive_time = 0; // reset counter
                    },[this](int error_code, std::string error_msg){
                        logger::error("[{}] Level2 server connection failed({},{}), Retry to connect...", get_name(), error_code, error_msg);
                        this_thread::sleep_for(chrono::milliseconds(1000)); // wait for a second
                    });
                }
                else{
                    logger::info("now available");
                    int result = _tcp_socket->connection_lost();
                    if(result==1){
                        logger::error("losted");
                        _tcp_socket->close();
                        this_thread::sleep_for(chrono::milliseconds(1000));
                        delete _tcp_socket;
                        _tcp_socket = nullptr;
                    }
                }
            }


            // if(!_tcp_socket->is_available()){

            //     int alive_time = 0;
            //     //tcp_socket.close();
            //     _tcp_socket->connect(lv2_access_ip, lv2_access_port, [&] {
            //         logger::info("[{}] Connected to Level2 server successfully", get_name());
            //         alive_time = 0; // reset counter
            //     },[this](int error_code, std::string error_msg){
            //         logger::error("[{}] Level2 server connection failed({},{}), Retry to connect...", get_name(), error_code, error_msg);
            //         this_thread::sleep_for(chrono::milliseconds(1000)); // wait for a second
            //     });

            // }
            // else {
            //     // logger::info("now available");
            //     int result = _tcp_socket->connection_lost();
            //     if(result==1){
            //         _tcp_socket->close();
            //         delete _tcp_socket;
            //         _tcp_socket = nullptr;
            //         this_thread::sleep_for(chrono::milliseconds(1000)); // wait for a second

            //         // tcp_socket<> tcp_socket([this](int error_code, std::string error_msg){
            //         //     logger::error("[{}] Socket creation error {}", get_name(), error_code);
            //         // });
            //         // tcp_socket.on_socket_closed = [this](int error_code){
            //         //     logger::info("[{}] Connection Closed({})", get_name(), error_code);
            //         // };

            //     }
            // }

            /* connection lost check */
            // int result = tcp_socket.connection_lost();
            // if(result==1) {
            //     logger::error("[{}] Connection lost. Try to reconnect...", get_name());

            //     /* reconnect */
            //     tcp_socket.close();
            //     tcp_socket.connect(lv2_access_ip, lv2_access_port, [&] {
            //         logger::info("[{}] Connected to Level2 server successfully", get_name());
            //         alive_time = 0; // reset counter
            //     },[this](int error_code, std::string error_msg){
            //         logger::error("[{}] Level2 server connection failed({},{}), Retry to connect...", get_name(), error_code, error_msg);
            //         this_thread::sleep_for(chrono::milliseconds(1000)); // wait for a second
            //     });
            // }
            // else if(result==-1){
            //     logger::error("error");
            //     this_thread::sleep_for(chrono::milliseconds(1000)); // wait for a second
            // }
        
            
            // if(!tcp_socket.is_available()){
                
            // }
            // else{
            //     /* send alive check */
            //     if(alive_time>=(_alive_interval*10)){
            //         /* send alive packet for every 30s */
            //         dk_sdd_alive alive_packet = generate_packet_alive();
            //         char* packet = reinterpret_cast<char*>(&alive_packet);
            //         tcp_socket.send(packet, sizeof(alive_packet));
            //         alive_time = 0;
            //     }
            //     alive_time++;

            //     /* send alarm code */
            //     dk_sdd_alarm alarm_packet;
            //     if(_sdd_alarm_queue.pop_async(alarm_packet)){
            //         char* packet = reinterpret_cast<char*>(&alarm_packet);
            //         tcp_socket.send(packet, sizeof(alarm_packet));
            //     }

            //     /* job result */
            //     dk_sdd_job_result job_result_packet;
            //     if(_sdd_job_result_queue.pop_async(job_result_packet)){
            //         char* packet = reinterpret_cast<char*>(&job_result_packet);
            //         tcp_socket.send(packet, sizeof(job_result_packet));
            //     }
            // }
            
        }
        catch(const zmq::error_t& e){
            break;
        }

        this_thread::sleep_for(chrono::milliseconds(100));
    }

    if(_tcp_socket){
        _tcp_socket->close();
        delete _tcp_socket;
    }
}

void dk_level2_interface::_do_server_work(json parameters){

    logger::info("[{}] Waiting for connection... {}:{}", get_name(), sdd_host_ip, sdd_host_port);

    while(!_worker_stop.load()){
        try{

        }
        catch(const zmq::error_t& e){
            break;
        }

        this_thread::sleep_for(chrono::milliseconds(100));
    }
}

void dk_level2_interface::on_loop(){

}

void dk_level2_interface::on_close(){

    /* work stop signal */
    _worker_stop.store(true);

    /* thread terminate */
    if(_client_worker.joinable()){
        logger::info("[{}] waiting for stopping client...", get_name());
        _client_worker.join();
    }
    if(_server_worker.joinable()){
        logger::info("[{}] waiting for stopping server...", get_name());
        _server_worker.join();
    }
    
}

void dk_level2_interface::on_message(){
    
}

// void dk_level2_interface::on_server_connected(const tcp::endpoint& endpoint){

// }

// void dk_level2_interface::on_server_disconnected(const tcp::endpoint& endpoint){

// }

// void dk_level2_interface::on_server_received(const std::string& data){

// }

dk_sdd_alive dk_level2_interface::generate_packet_alive(){

    dk_sdd_alive packet;
    std::stringstream ss;
    static unsigned long alive_msg_counter = 0;

    /* 1. cTcCode (4) */
    string code = "1199";
    std::memcpy(packet.cTcCode, code.c_str(), sizeof(packet.cTcCode));

    /* 2. cDate (14) */
    string date = get_current_time();
    std::memcpy(packet.cDate, date.c_str(), sizeof(packet.cDate));

    /* 3. cTcLength (6) */
    ss << std::setw(sizeof(packet.cTcLength)) << std::setfill('0') << sizeof(dk_sdd_alarm);
    std::memcpy(packet.cTcLength, ss.str().c_str(), sizeof(packet.cTcLength));
    ss.str(""); ss.clear();

    /* 4. cCount (4) */
    ss << std::setw(sizeof(packet.cCount)) << std::setfill('0') << alive_msg_counter++;
    if(alive_msg_counter>9999)
        alive_msg_counter = 0;
    std::memcpy(packet.cCount, ss.str().c_str(), sizeof(packet.cCount));
    ss.str(""); ss.clear();

    /* 5. reserved (22) */
    memset(packet.cSpare, '0', sizeof(packet.cSpare));

    /* show raw packet data */
    if(_show_raw_packet.load())
        show_raw_packet(reinterpret_cast<char*>(&packet), sizeof(packet));

    return packet;

}
dk_sdd_alarm dk_level2_interface::generate_packet_alarm(string alarm_code = "000"){

    dk_sdd_alarm packet;
    std::stringstream ss;

    /* 1. cTcCode (4) */
    string code = "1198";
    std::memcpy(packet.cTcCode, code.c_str(), sizeof(packet.cTcCode));

    /* 2. cDate (14) */
    string date = get_current_time();
    std::memcpy(packet.cDate, date.c_str(), sizeof(packet.cDate));

    /* 3. cTcLength (6) */
    ss << std::setw(sizeof(packet.cTcLength)) << std::setfill('0') << sizeof(dk_sdd_alarm);
    std::memcpy(packet.cTcLength, ss.str().c_str(), sizeof(packet.cTcLength));
    ss.str(""); ss.clear();

    /* 4. cMessage (3) */
    std::memcpy(packet.cMessage, alarm_code.c_str(), sizeof(packet.cMessage));

    /* 5. reserved (23) */
    memset(packet.cSpare, '0', sizeof(packet.cSpare));

    /* show raw packet data */
    if(_show_raw_packet.load())
        show_raw_packet(reinterpret_cast<char*>(&packet), sizeof(packet));

    return packet;
}

dk_sdd_job_result dk_level2_interface::generate_packet_job_result(string lot_no, string mt_no, string mt_type_cd, string mt_stand, vector<dk_sdd_defect>* defect_list){

    dk_sdd_job_result packet;
    std::stringstream ss;
    static unsigned long transmit_counter = 0;

    /* 1. cTcCode (4) */
    string code = "1101";
    std::memcpy(packet.cTcCode, code.c_str(), sizeof(packet.cTcCode));

    /* 2. cDate (14) */
    string date = get_current_time();
    std::memcpy(packet.cDate, date.c_str(), sizeof(packet.cDate));

    /* 3. cTcLength (6) */
    ss << std::setw(sizeof(packet.cTcLength)) << std::setfill('0') << sizeof(dk_sdd_job_result);
    std::memcpy(packet.cTcLength, ss.str().c_str(), sizeof(packet.cTcLength));
    ss.str(""); ss.clear();

    /* 4. cLotNo (15) */
    ss << std::left << std::setw(sizeof(packet.cLotNo)) << std::setfill(' ') << lot_no;
    std::memcpy(packet.cLotNo, ss.str().c_str(), sizeof(packet.cLotNo));
    ss.str(""); ss.clear();

    /* 5. cMtNo (15) */
    ss << std::left << std::setw(sizeof(packet.cMtNo)) << std::setfill(' ') << mt_no;
    std::memcpy(packet.cMtNo, ss.str().c_str(), sizeof(packet.cMtNo));
    ss.str(""); ss.clear();

    /* 6. cMtTypeCd (2) */
    ss << std::left << std::setw(sizeof(packet.cMtTypeCd)) << std::setfill(' ') << mt_type_cd;
    std::memcpy(packet.cMtTypeCd, ss.str().c_str(), sizeof(packet.cMtTypeCd));
    ss.str(""); ss.clear();

    /* 7. cMtStand (30) */
    ss << std::left << std::setw(sizeof(packet.cMtStand)) << std::setfill(' ') << mt_stand;
    std::memcpy(packet.cMtStand, ss.str().c_str(), sizeof(packet.cMtStand));
    ss.str(""); ss.clear();

    /* 8. cCount (4) */
    ss << std::setw(sizeof(packet.cCount)) << std::setfill('0') << transmit_counter++;
    if(transmit_counter>9999)
        transmit_counter = 0;
    std::memcpy(packet.cCount, ss.str().c_str(), sizeof(packet.cCount));
    ss.str(""); ss.clear();

    /* show raw packet data */
    if(_show_raw_packet.load())
        show_raw_packet(reinterpret_cast<char*>(&packet), sizeof(packet));

    return packet;

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