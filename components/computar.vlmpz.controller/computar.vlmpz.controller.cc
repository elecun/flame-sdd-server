
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
            if(it->second->open(it->first)){
                logger::info("[{}] Lens #{} successfully opened", get_name(), it->first);
                logger::info("[{}] Lens #{} Focus Initializing...", get_name(), it->first);
                it->second->focus_initialize();
                // logger::info("[{}] Lens #{} Iris Initializing...", get_name(), it->first);
                // it->second->iris_initialize();
            }
        }
        

        /* component status monitoring subtask */
        // thread status_monitor_worker = thread(&computar_vlmpz_controller::_subtask_status_publish, this, get_profile()->parameters());
        // _subtask_status_publisher = status_monitor_worker.native_handle();
        // status_monitor_worker.detach();

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
    for(map<int, unique_ptr<controlImpl>>::iterator it=_device_map.begin(); it!=_device_map.end(); ++it){
        it->second->close();
    }
    _device_map.clear();
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
    unsigned int _n_devices = 0;
    UsbGetNumDevices(&_n_devices);
    logger::info("[{}] Found {} Lens connected", get_name(), _n_devices);

    // 2. get device information
    char serial_number[260] = {0, }; // device name is 260bytes according to the instructions of the USB IC
    json defined_devices = get_profile()->parameters()["devices"];
    if(_n_devices>0){
        for(uint16_t idx=0; idx<_n_devices; idx++){
            int retval = UsbGetSnDevice(idx, serial_number);
            if(!retval){ //success
                UsbOpen(idx);
                char model_name[25] = {0,};
                ModelName(model_name);
                // UserIDRead(); // not used, read user registered device name
                UsbClose();

                string sn(serial_number);
                bool found = false;
                for(auto& device:defined_devices){
                    if(!device["sn"].get<string>().compare(sn)){ // found
                        found = true;
                        int id = device["id"].get<int>();
                        _device_map.insert({idx, make_unique<controlImpl>(id, sn)});
                        logger::info("[{}] + Register Lens #{} : S/N({}), Model({}))", get_name(), id, serial_number, model_name);
                    }   
                }

                if(!found){
                    logger::warn("[{}] - Undefined Lens found : S/N({}), Model({}))", get_name(), serial_number, model_name);
                }
            }
        }
    }
}

