
#include "computar.vlmpz.controller.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>

using namespace flame;

static computar_vlmpz_controller* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new computar_vlmpz_controller(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool computar_vlmpz_controller::on_init(){

    try {
        
        /* usb device scan and insert into container, lens controller map will be built*/
        _usb_device_scan();

        for (map<int, controlImpl*>::iterator it=_lens_controller_map.begin(); it != _lens_controller_map.end(); ++it) {
            if(it->second->open()){
                logger::info("[{}] Lens #{} successfully opened", get_name(), it->second->get_camera_id());
                logger::info("[{}] Lens #{} Focus Initializing...", get_name(), it->second->get_camera_id());
                it->second->focus_initialize();
            }
            else{
                logger::warn("[{}] Lens #{} cannot be opened", get_name(), it->second->get_camera_id());
            }
        }

        /* lens control with req/rep processing */
        thread lens_control_responser = thread(&computar_vlmpz_controller::_lens_control_subscribe, this, get_profile()->parameters());
        _lens_control_responser_handle = lens_control_responser.native_handle();
        lens_control_responser.detach();


    }
    catch(json::exception& e){
        logger::error("[{}] Profile Error : {}", get_name(), e.what());
        return false;
    }
    return true;
}

void computar_vlmpz_controller::on_loop(){
    
}

void computar_vlmpz_controller::on_close(){

    for(map<int, controlImpl*>::iterator it=_lens_controller_map.begin(); it!=_lens_controller_map.end(); ++it){
        it->second->close();
    }
    _lens_controller_map.clear();

    /* terminate len control responser */
    _thread_stop_signal.store(true);
    pthread_cancel(_lens_control_responser_handle);
    pthread_join(_lens_control_responser_handle, nullptr);

    /* close usb connection */
    //UsbClose();

    logger::info("close computar_vlmpz_controller");
}

void computar_vlmpz_controller::on_message(){
    
}

/* status publisher subtask impl. */
void computar_vlmpz_controller::_subtask_status_publish(json parameters){

}


void computar_vlmpz_controller::_usb_device_scan(){

    // 0. clear device map
    _lens_controller_map.clear();

    // 1. get number of connected devices
    unsigned int _n_devices = 0;
    UsbGetNumDevices(&_n_devices);
    logger::info("[{}] Found {} Lens connected", get_name(), _n_devices);

    // 2. get device information
    json defined_devices = get_profile()->parameters()["devices"];
    if(_n_devices>0){
        for(uint16_t device_id=0; device_id<_n_devices; device_id++){ //start index from 0
            char serial_number[260] = {0, }; // device name is 260bytes according to the instructions of the USB IC
            int retval = UsbGetSnDevice(device_id, serial_number);
            string sn = string(serial_number);

            if(!retval){ // no error
                logger::info("[{}] Found USB Lens Controller #{} - SN {}", get_name(), device_id, sn);

                // found camera id with device id
                for(auto& device:defined_devices){ // find in parameters
                    if(!device["sn"].get<string>().compare(sn)){ //found
                        int cid = device["camera_id"].get<int>();
                        _lens_controller_map.insert({cid, new controlImpl(get_name(), (int)device_id, cid)});
                        _device_id_mapper.insert({cid, device_id});
                        logger::info("[{}] Registered Lens Controller, User ID({})-Device ID({})-SN({})",get_name(), device["camera_id"].get<int>(), (int)device_id, sn);
                        break;
                    }
                }
            }
        }
    }
    else{
        logger::error("[{}] No device found");
    }
}

void computar_vlmpz_controller::_lens_control_subscribe(json parameters){
    pthread_setcancelstate(PTHREAD_CANCEL_ENABLE, nullptr);
    pthread_setcanceltype(PTHREAD_CANCEL_DEFERRED, nullptr);

    while(!_thread_stop_signal.load()){
        try{
            zmq::multipart_t msg_multipart;
            if(msg_multipart.recv(*get_port("focus_control"))){
                string topic = msg_multipart.popstr();
                std::string message(static_cast<char*>(msg_multipart.at(0).data()), msg_multipart.at(0).size()); //jsonized message
                auto json_data = json::parse(message);

                if(json_data.contains("function")){

                    /* 1. for move focus function processing */
                    if(!json_data["function"].get<string>().compare("move_focus")){
                        int camera_id = json_data["id"].get<int>();
                        int value = json_data["value"].get<int>();
                        logger::info("[{}] Move focus ID:{} (Device ID : {})",get_name(), camera_id, _device_id_mapper[camera_id]);
                        _lens_controller_map[_device_id_mapper[camera_id]]->focus_move(value);
                    }
                }

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

void computar_vlmpz_controller::_lens_control_responser(json parameters){
    pthread_setcancelstate(PTHREAD_CANCEL_ENABLE, nullptr);
    pthread_setcanceltype(PTHREAD_CANCEL_DEFERRED, nullptr);

    while(!_thread_stop_signal.load()){
        try{
            pipe_data request;
            zmq::recv_result_t request_result = get_port("focus_control")->recv(request, zmq::recv_flags::none);
            if(request_result){
                std::string message(static_cast<char*>(request.data()), request.size());
                auto json_data = json::parse(message);

                // control processing
                json reply_data;
                if(json_data.contains("function")){
                    /* 1. for read focus function processing */
                    if(!json_data["function"].get<string>().compare("read_focus")){

                        // read lens focus value
                        for(map<int,int>::iterator it=_device_id_mapper.begin(); it!=_device_id_mapper.end(); ++it){
                            string str_camera_id = fmt::format("{}",it->first);
                            reply_data[str_camera_id] = _lens_controller_map[it->second]->read_focus_position();
                        }
                    }

                    /* 2. for move focus function processing */
                    else if(!json_data["function"].get<string>().compare("move_focus")){
                        int camera_id = json_data["id"].get<int>();
                        int value = json_data["value"].get<int>();
                        logger::info("[{}] Move focus ID:{} (Device ID : {})",get_name(), camera_id, _device_id_mapper[camera_id]);
                        _lens_controller_map[_device_id_mapper[camera_id]]->focus_move(value);

                        // response
                        string str_camera_id = fmt::format("{}", camera_id);
                        reply_data["message"] = fmt::format("{} works done.",str_camera_id);
                    }
                }

                // reply
                pipe_data reply(reply_data.dump().size());
                memcpy(reply.data(), reply_data.dump().data(), reply_data.dump().size());
                get_port("focus_control")->send(reply, zmq::send_flags::dontwait);
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

int computar_vlmpz_controller::UsbGetNumDevices(unsigned int* numDevices){
	int retval = HidSmbus_GetNumDevices(numDevices, VID, PID);
	return retval;
}

int computar_vlmpz_controller::UsbGetSnDevice(unsigned short index, char* SnString){
	int retval = HidSmbus_GetString(index, VID, PID, SnString, HID_SMBUS_GET_SERIAL_STR);
	return retval;
}