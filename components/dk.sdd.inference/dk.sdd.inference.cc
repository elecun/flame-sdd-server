
#include "dk.sdd.inference.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>
#include <onnxruntime/core/providers/cuda

using namespace flame;

static dk_sdd_inference* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new dk_sdd_inference(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool dk_sdd_inference::on_init(){

    //connect
    return true;
}

void dk_sdd_inference::on_loop(){
    

}

void dk_sdd_inference::on_close(){
    
}

void dk_sdd_inference::on_message(){
    
}

void dk_sdd_inference::inference(){
    
    
}