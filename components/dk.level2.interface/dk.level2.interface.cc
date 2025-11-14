
#include "dk.level2.interface.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>
#include <chrono>
#include <filesystem>
#include <sstream>
#include <bitset>

using namespace flame;

static dk_level2_interface* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new dk_level2_interface(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool dk_level2_interface::on_init(){

    _show_raw_packet.store(get_profile()->parameters().value("show_raw_packet", false));
    _lv2_access_ip = get_profile()->parameters().value("level2_access_ip", "127.0.0.1"); //level2 server ip address
    _lv2_access_port = get_profile()->parameters().value("level2_access_port", 9999);
    _sdd_host_ip = get_profile()->parameters().value("sdd_host_ip", "127.0.0.1"); //sdd server ip address
    _sdd_host_port = get_profile()->parameters().value("sdd_host_port", 9998);
    _alive_interval = get_profile()->parameters().value("alive_interval", 60);

    logger::info("[{}] Level2 Access Address : {}:{}", get_name(), _lv2_access_ip, _lv2_access_port);
    logger::info("[{}] SDD Access Address : {}:{}", get_name(), _sdd_host_ip, _sdd_host_port);

    /* client */
    try{
        if(get_profile()->parameters().value("enable_level2_access", true))
            _client_worker = thread(&dk_level2_interface::_do_client_work, this, get_profile()->parameters());
        if(get_profile()->parameters().value("enable_sdd_host", true))
            _server_worker = thread(&dk_level2_interface::_do_server_work, this, get_profile()->parameters());
        if(get_profile()->parameters().value("enable_line_check", true))
            _line_check_worker = thread(&dk_level2_interface::_line_check_work, this, get_profile()->parameters());
        if(get_profile()->parameters().value("enable_job_check", true))
            _job_check_worker = thread(&dk_level2_interface::_job_check_work, this, get_profile()->parameters());
    }
    catch(std::exception& e) {
        logger::error("[{}] Create client exception : {}", get_name(), e.what());
    }

    return true;
}

void dk_level2_interface::_job_check_work(json parameters){
    while(!_worker_stop.load()){
        try{
            zmq::multipart_t msg_multipart;
            bool success = msg_multipart.recv(*get_port("sdd_job_queue"));
            if(success){
                string topic = msg_multipart.popstr();
                string data = msg_multipart.popstr();
                logger::info("[{}] Job Complete received : {}", get_name(), data);

                auto json_data = json::parse(data);

                // job complete packet generation & insert to queue
                // message = {"date":date, "lot_no":lot_no, "mt_no":mt_no, "mt_type_cd":mt_type_cd, "mt_stand":mt_stand, "defect_count":n_copied}
                dk_sdd_job_complete job_completed_packet = generate_packet_job_complete(json_data["lot_no"].get<string>(),
                                                                                        json_data["mt_no"].get<string>(),
                                                                                        json_data["mt_type_cd"].get<string>(),
                                                                                        json_data["mt_stand"].get<string>(),
                                                                                        json_data["frames"].get<int>());
                _sdd_job_complete_queue.push(std::move(job_completed_packet));
            }
        }
        catch(const zmq::error_t& e){
            logger::error("[{}] Pipeline Exception : {}", get_name(), e.what());
        }
        catch(const std::exception& e){
            logger::error("[{}] Standard Exception : {}", get_name(), e.what());
        }
    }

}

void dk_level2_interface::_line_check_work(json paramters){

    while(!_worker_stop.load()){
        try{

            zmq::multipart_t msg_multipart;
            bool success = msg_multipart.recv(*get_port("ni_daq_controller/line_signal"));
            if(success){
                string topic = msg_multipart.popstr();
                string data = msg_multipart.popstr();
                auto json_data = json::parse(data);

                if(json_data.contains("hmd_signal_1_on") && json_data.contains("hmd_signal_2_on") && json_data.contains("online_signal_on")){
                    bool hmd_signal_1_on = json_data["hmd_signal_1_on"].get<bool>();
                    bool hmd_signal_2_on = json_data["hmd_signal_2_on"].get<bool>();
                    bool online_signal_on = json_data["online_signal_on"].get<bool>();

                    if(hmd_signal_1_on || hmd_signal_2_on){
                        logger::info("[{}] Level2 Data usage will be discontinued", get_name());
                        _ignore.store(true);
                    }
                    else {
                        logger::info("[{}] Level2 Data will resume", get_name());
                        _ignore.store(false);
                    }
                }
            }
        }
        catch(const zmq::error_t& e){
            logger::error("[{}] Pipeline Exception : {}", get_name(), e.what());
        }
        catch(const std::exception& e){
            logger::error("[{}] Standard Exception : {}", get_name(), e.what());
        }
    }

}

void dk_level2_interface::_do_client_work(json parameters){

    logger::info("[{}] Trying to access to Level2 {}:{}", get_name(), _lv2_access_ip, _lv2_access_port);
    tcp_socket<>* _tcp_socket = nullptr;
    int alive_time = 0;
    bool is_connected = false;

    while(!_worker_stop.load()){
        try{
            
            /* tcp socket creation is required */
            if(!_tcp_socket){
                /* create new socket */
                _tcp_socket = new tcp_socket<>([this](int error_code, std::string error_msg){
                    logger::error("[{}] Socket creation error {}", get_name(), error_code);
                });
                _tcp_socket->on_socket_closed = [this](int error_code){
                    logger::info("[{}] Connection Closed({})", get_name(), error_code);
                };
            }
            else{

                /* if not connected */
                if(!is_connected){
                    int alive_time = 0;
                    _tcp_socket->connect(_lv2_access_ip, _lv2_access_port, [&] {
                        logger::info("[{}] Connected to Level2 server({}:{}) successfully", get_name(), _tcp_socket->get_remote_address(), _tcp_socket->get_remote_port());
                        alive_time = 0; // reset counter
                        is_connected = true;
                    },[&](int error_code, std::string error_msg){
                        _tcp_socket->close();
                        delete _tcp_socket;
                        _tcp_socket = nullptr;
                        is_connected = false;
                        logger::error("[{}] Level2 server connection failed(#{}), Retry to connect...", get_name(), error_code);
                        this_thread::sleep_for(chrono::milliseconds(1000)); // wait for a second
                    });
                }
                /* connected */
                else {
                    /* 1. send alive check packet for every 30s */
                    if(alive_time>=(_alive_interval*10)){
                        if(_tcp_socket && is_connected){
                            dk_sdd_alive alive_packet = generate_packet_alive();
                            char* packet = reinterpret_cast<char*>(&alive_packet);
                            ssize_t sent_bytes = _tcp_socket->send(packet, sizeof(alive_packet));
                            if(sent_bytes<=0){
                                logger::warn("[{}] Level2 Server connection is lost or closed.", get_name());
                                _tcp_socket->close(); // socket close & clear 
                                delete _tcp_socket;
                                _tcp_socket = nullptr;
                                is_connected = false;
                            }
                        }
                        alive_time = 0;
                    }
                    alive_time++;

                    /* 2. alarm message */
                    if(_tcp_socket && is_connected){
                        dk_sdd_alarm alarm_packet;
                        if(_sdd_alarm_queue.pop_async(alarm_packet)){
                            char* packet = reinterpret_cast<char*>(&alarm_packet);
                            ssize_t sent_bytes = _tcp_socket->send(packet, sizeof(alarm_packet));
                            if(sent_bytes<=0){
                                logger::warn("[{}] Level2 Server connection is lost or closed.", get_name());
                                _tcp_socket->close(); // socket close & clear 
                                delete _tcp_socket;
                                _tcp_socket = nullptr;
                                is_connected = false;
                            }
                        }
                    }

                    /* 3. job result(completed) */
                    if(_tcp_socket && is_connected){
                        dk_sdd_job_complete job_completed_packet;
                        if(_sdd_job_complete_queue.pop_async(job_completed_packet)){
                            char* packet = reinterpret_cast<char*>(&job_completed_packet);
                            ssize_t sent_bytes = _tcp_socket->send(packet, sizeof(job_completed_packet));
                            if(sent_bytes<=0){
                                logger::warn("[{}] Level2 Server connection is lost or closed.", get_name());
                                _tcp_socket->close(); // socket close & clear 
                                delete _tcp_socket;
                                _tcp_socket = nullptr;
                                is_connected = false;
                            }
                        }
                    }
                }
            }            
        }
        catch(const zmq::error_t& e){
            break;
        }

        this_thread::sleep_for(chrono::milliseconds(100));
    }

    /* clear socket */
    if(_tcp_socket){
        _tcp_socket->close();
        delete _tcp_socket;
    }
}

void dk_level2_interface::_do_server_work(json parameters){

    logger::info("[{}] Waiting for connection... {}:{}", get_name(), _sdd_host_ip, _sdd_host_port);
    tcp_server<>* _tcp_server = nullptr;

    while(!_worker_stop.load()){
        try{
            if(!_tcp_server){
                _tcp_server = new tcp_server<>([this](int error_code, string error_msg){
                    logger::error("[{}] Server socket creation error {}", get_name(), error_code);
                });
                
                _tcp_server->on_new_connection = [&](tcp_socket<> *client) {
                    logger::info("[{}] Connected client : {}:{}", get_name(), client->get_remote_address(), client->get_remote_port());

                    /* use raw byte packet */
                    client->on_raw_received = [this, client](const char* data, int length){
                        logger::info("[{}] Raw Received : {}bytes ", get_name(), length);

                        /* tc code : alive check */
                        if(!memcmp(data, "1099", 4)){
                            dk_lv2_mf_alive packet;
                            if(length==sizeof(packet)){
                                memcpy(&packet, data, sizeof(packet));
                                string str_packet(data, length);
                                logger::info("[{}] {}", get_name(), str_packet);

                                /* level2 connection status update for monitoring */
                                publish_status(true);
                            }
                            else {
                                logger::info("[{}] Wrong packet(TC code:1099) length", get_name());
                            }
                        }

                        /* tc code : clear? */
                        else if(!memcmp(data, "1098", 4)){
                            dk_lv2_mf_clear packet;
                            if(length==sizeof(packet)){
                                memcpy(&packet, data, sizeof(packet));
                                string str_packet(data, length);
                                logger::info("[{}] {}", get_name(), str_packet);
                            }
                            else {
                                logger::info("[{}] Wrong packet(TC code:1098) length", get_name());
                            }
                        }

                        /* tc code 1002 : labeled*/
                        else if(!memcmp(data, "1002", 4)){
                            dk_lv2_defect_labeled packet;
                            if(length==sizeof(packet)){
                                memcpy(&packet, data, sizeof(packet));
                                string str_packet(data, length);
                                logger::info("[{}] {}", get_name(), str_packet);

                                json data_pack;
                                data_pack["date"] = remove_space(packet.cDate, sizeof(packet.cDate));
                                data_pack["mt_no"] = remove_space(packet.cMtNo, sizeof(packet.cMtNo));
                                data_pack["mea_image1"] = remove_space(packet.cMea_Image1, sizeof(packet.cMea_Image1));
                                data_pack["mea_image2"] = remove_space(packet.cMea_Image2, sizeof(packet.cMea_Image2));
                                data_pack["mea_image3"] = remove_space(packet.cMea_Image3, sizeof(packet.cMea_Image3));
                                data_pack["mea_image4"] = remove_space(packet.cMea_Image4, sizeof(packet.cMea_Image4));
                                data_pack["mea_image5"] = remove_space(packet.cMea_Image5, sizeof(packet.cMea_Image5));
                                data_pack["mea_image6"] = remove_space(packet.cMea_Image6, sizeof(packet.cMea_Image6));
                                data_pack["mea_image7"] = remove_space(packet.cMea_Image7, sizeof(packet.cMea_Image7));
                                data_pack["mea_image8"] = remove_space(packet.cMea_Image8, sizeof(packet.cMea_Image8));
                                data_pack["mea_image9"] = remove_space(packet.cMea_Image9, sizeof(packet.cMea_Image9));
                                data_pack["mea_image10"] = remove_space(packet.cMea_Image10, sizeof(packet.cMea_Image10));
                                data_pack["mea_image11"] = remove_space(packet.cMea_Image11, sizeof(packet.cMea_Image11));
                                data_pack["mea_image12"] = remove_space(packet.cMea_Image12, sizeof(packet.cMea_Image12));
                                data_pack["mea_image13"] = remove_space(packet.cMea_Image13, sizeof(packet.cMea_Image13));
                                data_pack["mea_image14"] = remove_space(packet.cMea_Image14, sizeof(packet.cMea_Image14));
                                data_pack["mea_image15"] = remove_space(packet.cMea_Image15, sizeof(packet.cMea_Image15));
                                if(!_ignore.load()){
                                    logger::info("Level2 Labeled Defect Info : mt_no: {}", data_pack["mt_no"].get<string>());

                                    /* publish the level2 data via labeling_job_dispatch port */
                                    string topic = fmt::format("labeling_job_dispatch", get_name());
                                    string data = data_pack.dump();
                                    zmq::multipart_t msg_multipart;
                                    msg_multipart.addstr(topic);
                                    msg_multipart.addstr(data);
                                    msg_multipart.send(*get_port("labeling_job_dispatch"), ZMQ_DONTWAIT);
                                    logger::info("[{}] Publish to labeling_job_dispatch", get_name());
                                }

                            }
                            else {
                                logger::info("[{}] Wrong packet(TC code:1002) length", get_name());
                            }
                        }

                        /* tc code : job instruction */
                        else if(!memcmp(data, "1001", 4)){
                            dk_lv2_mf_instruction packet;
                            if(length==sizeof(packet)){
                                memcpy(&packet, data, sizeof(packet));
                                string str_packet(data, length);
                                logger::info("[{}] {}", get_name(), str_packet);

                                /* abstract data pack */
                                json data_pack;
                                data_pack["date"] = remove_space(packet.cDate, sizeof(packet.cDate));
                                data_pack["lot_no"] = remove_space(packet.cLotNo, sizeof(packet.cLotNo));
                                data_pack["mt_no"] = remove_space(packet.cMtNo, sizeof(packet.cMtNo));
                                //dk_h_standard_dim dim = extract_stand_dim(packet.cMtStand, sizeof(packet.cMtStand));
                                data_pack["mt_stand"] = remove_space(packet.cMtStand, sizeof(packet.cMtStand));
                                data_pack["mt_stand_raw"] = string(packet.cMtStand, sizeof(packet.cMtStand));
                                data_pack["mt_stand_height"] = stoi(remove_space(packet.cStandSize2, sizeof(packet.cStandSize2))); //B
                                data_pack["mt_stand_width"] = stoi(remove_space(packet.cStandSize1, sizeof(packet.cStandSize1))); // H
                                data_pack["mt_stand_t1"] = stoi(remove_space(packet.cStandSize3, sizeof(packet.cStandSize3))); //t1
                                data_pack["mt_stand_t2"] = stoi(remove_space(packet.cStandSize4, sizeof(packet.cStandSize4))); //t2
                                data_pack["fm_length"] = stol(remove_space(packet.cFMLength, sizeof(packet.cFMLength))); //fm length
                                data_pack["mt_type_cd"] = remove_space(packet.cMtTypeCd, sizeof(packet.cMtTypeCd)); // mt_type_cd
                                data_pack["fm_speed"] = stoi(remove_space(packet.cFMSpeed, sizeof(packet.cFMSpeed))); //fm_speed
                                if(!_ignore.load()){
                                    logger::info("Level2 Info : {}x{}x{}/{}, ({})(type:{})(raw:{})", 
                                                                        data_pack["mt_stand_height"].get<int>(),
                                                                        data_pack["mt_stand_width"].get<int>(),
                                                                        data_pack["mt_stand_t1"].get<int>(),
                                                                        data_pack["mt_stand_t2"].get<int>(),
                                                                        data_pack["fm_length"].get<long>(),
                                                                        data_pack["mt_type_cd"].get<string>(),
                                                                        data_pack["mt_stand_raw"].get<string>());

                                    /* publish the level2 data via lv2_dispatch port */
                                    string topic = fmt::format("lv2_dispatch", get_name());
                                    string data = data_pack.dump();
                                    zmq::multipart_t msg_multipart;
                                    msg_multipart.addstr(topic);
                                    msg_multipart.addstr(data);
                                    msg_multipart.send(*get_port("lv2_dispatch"), ZMQ_DONTWAIT);
                                    logger::info("[{}] Publish to lv2_dispatch", get_name());
                                }
                                
                            }
                            else {
                                logger::info("[{}] Wrong packet(TC code:1001) length", get_name());
                            }
                            
                        }
                        else {
                            logger::warn("[{}] Undefined TC Code : {}", get_name(), string(data,4));
                        }

                    };
                    
                    client->on_socket_closed = [this, client](int error_code) {
                        logger::info("[{}] Disconnected client : {}:{}", get_name(), client->get_remote_address(), client->get_remote_port());
                        publish_status(false);
                    };
                };

                /* bind */
                _tcp_server->bind(_sdd_host_port, [&](int error_code, string error_message){
                    logger::error("[{}] bind error({}))", get_name(), error_message);
                });

                _tcp_server->listen([&](int error_code, string error_message){
                    logger::error("[{}] Listen error", get_name());
                });

            }
        }
        catch(const zmq::error_t& e){
            logger::error("[{}] Pipeline Exception : {}", get_name(), e.what());
            break;
        }
        catch(const std::exception& e){
            logger::error("[{}] Standard Exception : {}", get_name(), e.what());
        }

        this_thread::sleep_for(chrono::milliseconds(100));
    }

    /* clear server */
    if(_tcp_server){
        _tcp_server->close();
        delete _tcp_server;
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
    if(_line_check_worker.joinable()){
        logger::info("[{}] waiting for line check...", get_name());
        _line_check_worker.join();
    }
    if(_job_check_worker.joinable()){
        logger::info("[{}] waiting for job check...", get_name());
        _job_check_worker.join();
    }

    logger::info("[{}] Level2 Interface is now closed", get_name());
    
}

void dk_level2_interface::on_message(){
    
}

dk_sdd_alive dk_level2_interface::generate_packet_alive(bool show){

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

    if(_show_raw_packet.load())
        show_raw_packet(reinterpret_cast<char*>(&packet), sizeof(packet));

    return packet;

}
dk_sdd_alarm dk_level2_interface::generate_packet_alarm(string alarm_code = "000", bool show){

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

    if(_show_raw_packet.load())
        show_raw_packet(reinterpret_cast<char*>(&packet), sizeof(packet));

    return packet;
}
dk_sdd_job_result dk_level2_interface::generate_packet_job_result(string lot_no, string mt_no, string mt_type_cd, string mt_stand, vector<dk_sdd_defect> defect_list, bool show){

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

    /* 9. cResult#_Code & cResult#_Pos */
    size_t index = 0;
    for(const auto& rst:defect_list){
        if(index>=MAX_RST_SIZE){ /* max size */
            logger::warn("[{}] Defects exceeds max size", get_name());
            break;
        }
        std::memcpy(&packet.cRst[index], &rst, sizeof(rst));
        index++;
    }

    if(_show_raw_packet.load())
        show_raw_packet(reinterpret_cast<char*>(&packet), sizeof(packet));

    return packet;

}

dk_sdd_job_complete dk_level2_interface::generate_packet_job_complete(string lot_no, string mt_no, string mt_type_cd, string mt_stand, int frames){

    dk_sdd_job_complete packet;
    std::stringstream ss;

    /* 1. cTcCode (4) */
    string code = "1101";
    std::memcpy(packet.cTcCode, code.c_str(), sizeof(packet.cTcCode));

    /* 2. cDate (14) */
    string date = get_current_time();
    std::memcpy(packet.cDate, date.c_str(), sizeof(packet.cDate));

    /* 3. cTcLength (6) */
    ss << std::setw(sizeof(packet.cTcLength)) << std::setfill('0') << std::right << sizeof(dk_sdd_job_complete);
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

    /* 8. cCount (5) */
    ss << std::setw(sizeof(packet.cCount)) << std::setfill('0') << std::right << frames;
    std::memcpy(packet.cCount, ss.str().c_str(), sizeof(packet.cCount));
    ss.str(""); ss.clear();

    /* 9. cSpare (10) */
    memset(packet.cSpare, '0', sizeof(packet.cSpare));

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

string dk_level2_interface::remove_space(const char* in, int size){
    string str = string(in, size);
    str.erase(std::remove_if(str.begin(), str.end(), ::isspace),str.end());
    return str;
}

dk_h_standard_dim dk_level2_interface::extract_stand_dim(const char* in, int size){
    string str_standard = remove_space(in, size);
    str_standard.erase(0, 1); // remove 'H'
    const string delimiters = "x/";
    dk_h_standard_dim result;

    std::vector<std::string> tokens;
    size_t start = 0, end;
    while((end = str_standard.find_first_of(delimiters, start))!=std::string::npos) {
        if(end != start){
            tokens.push_back(str_standard.substr(start, end - start));
        }
        start = end + 1;
    }
    if(start < str_standard.size()){
        tokens.push_back(str_standard.substr(start));
    }

    if(tokens.size()==4){
        try{
            result.width = stoi(tokens[0]); // H
            result.height = stoi(tokens[1]); // B
            result.t1 = stod(tokens[2]); //t1
            result.t2 = stod(tokens[3]); //t2
        }
        catch(const std::exception& e){
            logger::error("[{}] extraction error : {}", get_name(), e.what());
        }
    }
    else {
        logger::warn("[{}] Parse error (tokenization)", get_name());
        memset(&result, 0, sizeof(result));
    }

    return result;

}

/* publish status */
void dk_level2_interface::publish_status(bool lv2_connect){

    json data_pack;
    string topic = fmt::format("{}/status", get_name());
    data_pack["available"] = lv2_connect;
    string data = data_pack.dump();
    zmq::multipart_t msg_multipart;
    msg_multipart.addstr(topic);
    msg_multipart.addstr(data);
    msg_multipart.send(*get_port("status"), ZMQ_DONTWAIT);
}

std::vector<std::string> split(const std::string& str, const std::string& delimiters){
    std::vector<std::string> tokens;
    size_t start = 0, end;

    while((end = str.find_first_of(delimiters, start))!=std::string::npos) {
        if(end != start){
            tokens.push_back(str.substr(start, end - start));
        }
        start = end + 1;
    }
    if(start < str.size()){
        tokens.push_back(str.substr(start));
    }
    return tokens;
}
