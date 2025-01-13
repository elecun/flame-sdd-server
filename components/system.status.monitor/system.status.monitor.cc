#include "system.status.monitor.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>

using namespace flame;

static system_status_monitor* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new system_status_monitor(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool system_status_monitor::on_init(){
    _t1 = read_cpu_data();
    return true;
}

void system_status_monitor::on_loop(){

    CPU_stats _t2 = read_cpu_data();
    json system_usage;
    system_usage["cpu_usage"] = (100.0f * get_cpu_usage(_t1, _t2));
    system_usage["memory_usage"] = (100.f * read_memory_data().get_memory_usage());
    system_usage["storage_usage"] = (100.f * get_disk_usage("/"));

    string serialized = system_usage.dump(); //serialize
    pipe_data message(serialized.begin(), serialized.end());
    get_port("usage_stream")->send(message, zmq::send_flags::none);

}

void system_status_monitor::on_close(){

}

void system_status_monitor::on_message(){

}