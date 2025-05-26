
#include "computar.vlmpz.controller.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>
#include <cmath>

using namespace flame;

static computar_vlmpz_controller* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new computar_vlmpz_controller(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool computar_vlmpz_controller::on_init(){

    try {
        
        /* usb device scan and insert into container, lens controller map will be built*/
        _usb_device_scan();

        for(map<int, controlImpl*>::iterator it=_lens_controller_map.begin(); it != _lens_controller_map.end(); ++it) {
            if(it->second->open()){
                logger::info("[{}] Lens #{} successfully opened", get_name(), it->second->get_camera_id());
                logger::info("[{}] Lens #{} Focus Initializing...", get_name(), it->second->get_camera_id());
                it->second->focus_initialize();
                it->second->_is_opened.store(true);
            }
            else{
                it->second->_is_opened.store(false);
                logger::warn("[{}] Lens #{} cannot be opened", get_name(), it->second->get_camera_id());
            }
        }

        /* worker */
        _lens_control_worker = thread(&computar_vlmpz_controller::_lens_control_subscribe, this, get_profile()->parameters());
        // _level2_dispatch_worker = thread(&computar_vlmpz_controller::_level2_dispatch_subscribe, this, get_profile()->parameters());
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

    /* work stop signal */
    _worker_stop.store(true);

    /* wait for thread termination */
    if(_lens_control_worker.joinable())
        _lens_control_worker.join();
    // if(_level2_dispatch_worker.joinable())
    // _level2_dispatch_worker.join();

    /* device close */
    for(map<int, controlImpl*>::iterator it=_lens_controller_map.begin(); it!=_lens_controller_map.end(); ++it){
        it->second->close();
    }

    /* clear */
    _lens_controller_map.clear();

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

    // device map from profile
    if(get_profile()->parameters().contains("devices")){
        json defined_devices = get_profile()->parameters()["devices"];
        for(auto& device:defined_devices){
            int cam_id = device["camera_id"].get<int>();
            int dev_id = device["device_id"].get<int>();
            _lens_controller_map.insert({cam_id, new controlImpl(get_name(), dev_id, cam_id)});
            _device_id_mapper.insert({cam_id, dev_id});

            char serial_number[260] = {0, };
            int retval = UsbGetSnDevice(dev_id, serial_number);
            if(!retval){
                logger::info("[{}] Found USB Lens Controller Device ID#{} - SN {}", get_name(), dev_id, string(serial_number));
            }
        }
    }
}

void computar_vlmpz_controller::_level2_dispatch_subscribe(json parameters){
    try {
        while(!_worker_stop.load()){
            try{

                /* read control message */
                zmq::multipart_t msg_multipart;
                bool success = msg_multipart.recv(*get_port("lv2_dispatch"));
                if(success){
                    string topic = msg_multipart.popstr();
                    string data = msg_multipart.popstr();
                    auto json_data = json::parse(data);

                    if(json_data.contains("mt_stand_height") && json_data.contains("mt_stand_width") && json_data.contains("mt_stand_t1") && json_data.contains("mt_stand_t2")){

                        /* 1. for move focus function processing */
                        int height = json_data["mt_stand_height"].get<int>();
                        int width = json_data["mt_stand_width"].get<int>();
                        int t1 = json_data["mt_stand_t1"].get<int>();
                        int t2 = json_data["mt_stand_t2"].get<int>();

                        /* find file */
                        string preset_file = fmt::format("{}/{}_{}_{}_{}.preset", _preset_path, height, width, t1, t2);
                        if(!std::filesystem::exists(preset_file)){
                            logger::error("[{}] Preset file not found : {}", get_name(), preset_file);
                        }
                        else{
                            logger::info("[{}] Applying preset file : {}", get_name(), preset_file);
                            try{
                                std::ifstream file(preset_file);
                                json focus_preset;
                                file >> focus_preset;
                                
                                if(focus_preset.contains("focus_value")){
                                    for(auto& [camera_id, focus_value]:focus_preset["focus_value"].items()){
                                        int id = stoi(camera_id);
                                        if(_lens_controller_map.contains(id)){
                                            if(_lens_controller_map[id]->_is_opened.load()){
                                                _lens_controller_map[id]->focus_move(focus_value.get<int>());
                                                logger::info("[{}] Focus Lens moves for Camera ID #{}", get_name(), id);
                                            }
                                        }
                                    }
                                }
                            }
                            catch(const json::exception& e){
                                logger::error("[{}] Preset file parse error : {}", get_name(), e.what());
                            }
                        }
                    }
                }
            }
            catch(const zmq::error_t& e){
                break;
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

void computar_vlmpz_controller::_lens_control_subscribe(json parameters){

    try {
        while(!_worker_stop.load()){
            try{

                /* read control message */
                zmq::multipart_t msg_multipart;
                bool success = msg_multipart.recv(*get_port("focus_control"));
                if(success){
                    string topic = msg_multipart.popstr();
                    string data = msg_multipart.popstr();
                    auto json_data = json::parse(data);

                    logger::info("recv from {}", topic);

                    if(json_data.contains("function")){

                        /* 1. for move focus function processing */
                        if(!json_data["function"].get<string>().compare("move_focus")){
                            int camera_id = json_data["camera_id"].get<int>();
                            int value = json_data["value"].get<int>();
                            if(_lens_controller_map.contains(camera_id)){
                                if(_lens_controller_map[camera_id]->_is_opened.load()){
                                    _lens_controller_map[camera_id]->focus_move(value);
                                    logger::info("[{}] Focus Lens moves for Camera ID #{}", get_name(), camera_id);
                                }
                            }
                        }
                    }
                }
            }
            catch(const zmq::error_t& e){
                break;
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

int computar_vlmpz_controller::UsbGetNumDevices(unsigned int* numDevices){
	int retval = HidSmbus_GetNumDevices(numDevices, VID, PID);
	return retval;
}

int computar_vlmpz_controller::UsbGetSnDevice(unsigned short index, char* SnString){
	int retval = HidSmbus_GetString(index, VID, PID, SnString, HID_SMBUS_GET_SERIAL_STR);
	return retval;
}