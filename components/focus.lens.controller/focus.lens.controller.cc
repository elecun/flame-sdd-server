
#include "focus.lens.controller.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>

using namespace flame;

static focus_lens_controller* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new focus_lens_controller(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool focus_lens_controller::on_init(){

    try {

        json param = get_profile()->parameters();

        /* component status monitoring subtask */
        thread status_monitor_worker = thread(&autonics_temp_controller::_subtask_status_publish, this, get_profile()->parameters());
        _subtask_status_publisher = status_monitor_worker.native_handle();
        status_monitor_worker.detach();

    }
    catch(json::exception& e){
        logger::error("[{}] Profile Error : {}", get_name(), e.what());
        return false;
    }
    return true;
}

void focus_lens_controller::on_loop(){
    
}

void focus_lens_controller::on_close(){
    
}

void focus_lens_controller::on_message(){
    
}

/* status publisher subtask impl. */
void focus_lens_controller::_subtask_status_publish(json parameters){

}

