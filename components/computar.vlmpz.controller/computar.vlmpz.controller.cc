
#include "computar.vlmpz.controller.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>

using namespace flame;

static computar_vlmpz_controller* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new computar_vlmpz_controller(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool computar_vlmpz_controller::on_init(){

    try {
        
        /* usb device scan and insert into container */
        _usb_device_scan();

        for (map<int, unique_ptr<controlImpl>>::iterator it=_device_map.begin(); it != _device_map.end(); ++it) {
            if(it->second->open()){
                logger::info("[{}] Lens #{} successfully opened", get_name(), it->first);
                logger::info("[{}] Lens #{} Focus Initializing...", get_name(), it->first);
                it->second->focus_initialize();
            }
            else{
                logger::warn("[{}] Lens #{} cannot be opened", get_name(), it->first);
            }
        }
        

        /* component status monitoring subtask */
        // thread status_monitor_worker = thread(&computar_vlmpz_controller::_subtask_status_publish, this, get_profile()->parameters());
        // _subtask_status_publisher = status_monitor_worker.native_handle();
        // status_monitor_worker.detach();

        /* lens control with req/rep processing */
        thread lens_control_responser = thread(&computar_vlmpz_controller::_lens_control_responser, this, get_profile()->parameters());
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

    /* close usb */
    // for(map<int, unique_ptr<controlImpl>>::iterator it=_device_map.begin(); it!=_device_map.end(); ++it){
    //     it->second->close();
    // }
    // _device_map.clear();

    /* terminate len control responser */
    _thread_stop_signal.store(true);
    pthread_cancel(_lens_control_responser_handle);
    pthread_join(_lens_control_responser_handle, nullptr);

    /* close usb connection */
    UsbClose();

    logger::info("close computar_vlmpz_controller");
}

void computar_vlmpz_controller::on_message(){
    
}

/* status publisher subtask impl. */
void computar_vlmpz_controller::_subtask_status_publish(json parameters){

}


void computar_vlmpz_controller::_usb_device_scan(){

    // 0. clear device map
    _device_map.clear();

    // 1. get number of connected devices
    unsigned long _n_devices = 0;
    UsbGetNumDevices(&_n_devices);
    logger::info("[{}] Found {} Lens connected", get_name(), _n_devices);

    // 2. get device information
    char serial_number[260] = {0, }; // device name is 260bytes according to the instructions of the USB IC
    json defined_devices = get_profile()->parameters()["devices"];
    if(_n_devices>0){
        for(uint16_t device_id=0; device_id<_n_devices; device_id++){
            int retval = UsbGetSnDevice(device_id, serial_number);
            if(!retval){ //success
                // UsbOpen(idx);
                // char model_name[25] = {0,};
                // ModelName(model_name);
                // // UserIDRead(); // not used, read user registered device name
                // UsbClose();

                _device_map.insert({device_id, make_unique<controlImpl>(get_name(), device_id, defined_devices)});
                _device_id_mapper.insert({device_id, -1}); //default = -1

                // string sn(serial_number);
                // bool found = false;
                // for(auto& device:defined_devices){
                //     if(!device["sn"].get<string>().compare(sn)){ // found
                //         found = true;
                //         int id = device["id"].get<int>();
                //         _device_map.insert({idx, make_unique<controlImpl>(id, sn)});
                //         logger::info("[{}] + Register Lens #{} : S/N({}), Model({}))", get_name(), id, serial_number, model_name);
                //     }   
                // }

                // if(!found){
                //     logger::warn("[{}] - Undefined Lens found : S/N({}), Model({}))", get_name(), serial_number, model_name);
                // }
            }
        }

        // id mapping
        for(const auto& device:_device_map){
            _device_id_mapper[device.first] = device.second->get_user_id();
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
                            string str_user_id = fmt::format("{}",it->second);
                            reply_data[str_user_id] = _device_map[it->first]->read_focus_position();
                        }
                    }
                    /* 2. for move focus function processing */
                    else if(!json_data["function"].get<string>().compare("move_focus")){
                        int user_id = json_data["id"].get<int>();
                        int value = json_data["value"].get<int>();

                        for(map<int,int>::iterator it=_device_id_mapper.begin(); it!=_device_id_mapper.end(); ++it){
                            if(it->second==user_id){
                                logger::info("[{}] Lens #{}(device:{}) moves focus to {}", get_name(), user_id, it->first, value);
                                _device_map[it->first]->focus_move(value);
                                reply_data["response"] = "ok";
                                break;
                            }
                            else{
                                logger::warn("[{}] Not found Lens ID #{}", get_name(), user_id);
                            }
                        }
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