
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

        /* read parameters */
        json param = get_profile()->parameters();

        _simulation_mode.store(param.value("simulation_mode", false));

        if(!_simulation_mode.load()){

            /* modbus RTU initialize */
            _init_modbus();

            /* read parameters */
            string device = param.value("device", "/dev/ttyS0");
            int baudrate = param.value("baudrate", 9600);
            string parity = param.value("parity", "N");
            int data_bit = param.value("data_bit", 8);
            int stop_bit = param.value("stop_bit", 1);
            double timeout_sec = param.value("timeout_sec", 1.0);

            logger::info("[{}] Set FieldBus Interface : {}({}/{}/{}/{})", get_name(), device, baudrate, parity, data_bit, stop_bit);
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
        }
        else{
            logger::info("[{}] Working in Simulation Mode..", get_name());
        }

        /* read controll slaves */
        if(get_profile()->parameters().contains("slaves")){
            json slave_controllers = get_profile()->parameters()["slaves"];
            _slave_addrs = slave_controllers.get<std::vector<int>>();
        }

    }
    catch(json::exception& e){
        logger::error("[{}] Profile Error : {}", get_name(), e.what());
        return false;
    }

    return true;
}

void autonics_temp_controller::on_loop(){

    try{
        json data_pack;

        if(!_simulation_mode.load()){ //real mode
            for(int slave_addr : _slave_addrs){
                if(_modbus_ctx==nullptr)
                    break;

                modbus_set_slave(_modbus_ctx, slave_addr);

                uint16_t reg[2];
                int rc = modbus_read_input_registers(_modbus_ctx, READ_PRESENT_VALUE, 2, reg); // read PV
                if(rc==-1){
                    logger::error("[{}] Modbus RTU read failed (Address : {}), {}", get_name(), slave_addr, modbus_strerror(errno));
                    continue;
                }
                else {
                    float temperature = (float)reg[0] + (float)reg[1] / 10.0;
                    data_pack[fmt::format("{}", slave_addr)] = fmt::format("{:.1f}", (int)temperature*0.1f);
                    //logger::info("[{}] Slave({}) Temperature : {} ({},{})", get_name(), slave_addr, temperature, (int)reg[0], (int)reg[1]);
                }
                usleep(70000); // 70ms
            }
        }
        else { //simulation mode
            std::srand(static_cast<unsigned int>(std::time(nullptr)));
            for(int slave_addr : _slave_addrs){
                int random_temperature = std::rand() % 1001;
                data_pack[fmt::format("{}", slave_addr)] = fmt::format("{:.1f}", (int)random_temperature*0.1f);
            }
        }

        /* publish all packed data */
        if(!data_pack.empty()){
            string topic = fmt::format("{}/temp_stream", get_name());
            string data = data_pack.dump();

            zmq::multipart_t msg_multipart;
            msg_multipart.addstr(topic);
            msg_multipart.addstr(data);

            /* send data */
            msg_multipart.send(*get_port("temp_stream"), ZMQ_DONTWAIT);
        }
    }
    catch(std::runtime_error& e){
        logger::error("[{}] {}", get_name(), e.what());
    }
    catch(const zmq::error_t& e){
        logger::error("[{}] {}", get_name(), e.what());
    }
}

void autonics_temp_controller::on_close(){
    modbus_close(_modbus_ctx);
    modbus_free(_modbus_ctx);
}

void autonics_temp_controller::on_message(){
    
}


bool autonics_temp_controller::_init_modbus(){
    return true;
}
