
#include "autonics.temp.controller.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>

using namespace flame;

static autonics_temp_controller* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new autonics_temp_controller(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

#define READ_PRESENT_VALUE 0x03E8

bool autonics_temp_controller::on_init(){
    try{

        _init_modbus();

        /* read parameters */
        json param = get_profile()->parameters();
        string device = param.value("device", "/dev/ttyS0");
        int baudrate = param.value("baudrate", 9600);
        string parity = param.value("parity", "N");
        int data_bit = param.value("data_bit", 8);
        int stop_bit = param.value("stop_bit", 1);
        double timeout_sec = param.value("timeout_sec", 1.0);

        logger::info("[{}] Use device : {}({}/{}/{}/{})", get_name(), device, baudrate, parity, data_bit, stop_bit);
        _modbus_ctx = modbus_new_rtu(device.c_str(), baudrate, parity.c_str()[0], data_bit, stop_bit);
        if(_modbus_ctx==nullptr){
            logger::error("[{}] Modbus RTU context creation failed", get_name());
            return false;
        }

        /* set timeout */
        struct timeval timeout;
        timeout.tv_sec = static_cast<int>(timeout_sec);
        timeout.tv_usec = static_cast<int>((timeout_sec - timeout.tv_sec) * 1e6);
        modbus_set_response_timeout(_modbus_ctx, timeout.tv_sec, timeout.tv_usec);

        /* open port */
        if(modbus_connect(_modbus_ctx)==-1){
            logger::error("[{}] Modbus RTU connection failed", get_name());
            return false;
        }

        /* camera status ready with default profile */
        json slave_controllers = get_profile()->parameters()["slaves"];
        _slave_addrs = slave_controllers.get<std::vector<int>>();

        /* component status monitoring subtask */
        thread status_monitor_worker = thread(&autonics_temp_controller::_subtask_status_publish, this, get_profile()->parameters());
        _subtask_status_publisher = status_monitor_worker.native_handle();
        status_monitor_worker.detach();

    }
    catch(json::exception& e){
        logger::error("Profile Error : {}", e.what());
        return false;
    }

    return true;
}

void autonics_temp_controller::on_loop(){
    json data_pack;
    for(int slave_addr : _slave_addrs){
        modbus_set_slave(_modbus_ctx, slave_addr);

        uint16_t reg[2];
        int rc = modbus_read_input_registers(_modbus_ctx, READ_PRESENT_VALUE, 2, reg); // read PV
        if(rc==-1){
            logger::error("[{}] Modbus RTU read failed (Address : {})", get_name(), slave_addr);
            logger::error("[{}] {}", get_name(), modbus_strerror(errno));
            continue;
        }
        else {
            float temperature = (float)reg[0] + (float)reg[1] / 10.0;
            data_pack[fmt::format("{}", slave_addr)] = temperature;
            logger::info("[{}] Slave({}) Temperature : {} ({},{})", get_name(), slave_addr, temperature, (int)reg[0], (int)reg[1]);
        }

        usleep(70000); // 70ms
    }

    /* publish all packed data */
    try{
        string data = data_pack.dump();
        string topic = fmt::format("{}/{}", get_name(), "temp_stream");
        pipe_data topic_msg(topic.data(), topic.size());
        pipe_data data_msg(data.data(), data.size());
        get_port("temp_stream")->send(topic_msg, zmq::send_flags::sndmore);
        get_port("temp_stream")->send(data_msg, zmq::send_flags::dontwait);
    }
    catch(std::runtime_error& e){
        logger::error("[{}] {}", get_name(), e.what());
    }
}

void autonics_temp_controller::on_close(){
    modbus_close(_modbus_ctx);
    modbus_free(_modbus_ctx);
}

void autonics_temp_controller::on_message(){
    
}

/* status publisher subtask impl. */
void autonics_temp_controller::_subtask_status_publish(json parameters){

}

/* update status */
void autonics_temp_controller::_update_status(){


}

bool autonics_temp_controller::_init_modbus(){
    return true;
}