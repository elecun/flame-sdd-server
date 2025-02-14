
#include "ni.daq.controller.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>
#include <algorithm>
#include <execution> // parallel

using namespace flame;

static ni_daq_controller* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new ni_daq_controller(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}


bool ni_daq_controller::on_init(){

    /* read profile */
    _daq_device_name = get_profile()->parameters().value("device_name", "Dev1");
    _daq_counter_channel = get_profile()->parameters().value("counter_channel", "ctr0:1");
    _daq_di_channel = get_profile()->parameters().value("di_channel", "PFI0");
    _daq_pulse_freq = get_profile()->parameters().value("counter_pulse_freq", 30.0);
    _daq_pulse_duty = get_profile()->parameters().value("counter_pulse_duty", 0.5);

    /* start workers */
    bool auto_start = get_profile()->parameters().value("auto_start", false);
    if(auto_start){

        /* create pulse generation task */
        if(DAQmxCreateTask("camera_trigger", &_task_handle_pulse_generation)){
            logger::error("[{}] Failed to create DAQ task : Pulse Generation", get_name());
            return false;
        }

        if(DAQmxCreateCOPulseChanFreq(_task_handle_pulse_generation, _daq_counter_channel.c_str(),  // device_name / counter_channel
                                    "",               // Name of the virtual channel (optional)
                                    DAQmx_Val_Hz,     // units
                                    DAQmx_Val_Low,    // idle state
                                    0.0,              // initial delay
                                    _daq_pulse_freq,  // frequency
                                    _daq_pulse_duty   // Duty cycle
        )!=DAQmxSuccess){
            logger::error("[{}] Failed to create pulse channel", get_name());
            DAQmxClearTask(_task_handle_pulse_generation);
            return false;
        }

        if(DAQmxCfgImplicitTiming(_task_handle_pulse_generation, DAQmx_Val_ContSamps, 1000)){
            logger::error("[{}] Failed to set continuous sampling mode", get_name());
            return false;
        }

        /* create hmd signal reader task */
        if(DAQmxCreateTask("hmd_signal_reader", &_task_handle_dio_reader)!=DAQmxSuccess){
            logger::error("[{}] Failed to create DAQ task : Pulse Generation", get_name());
            return false;
        }

        if(DAQmxCreateDIChan(_task_handle_dio_reader, _daq_counter_channel.c_str(), "", DAQmx_Val_ChanPerLine)!=DAQmxSuccess){
            logger::error("[{}] Failed to DIO read channel", get_name());
            DAQmxClearTask(_task_handle_dio_reader);
            return false;
        }

        /* start thread */
        _daq_control_worker = thread(&ni_daq_controller::_daq_control_task, this);
        _daq_pulse_generation_worker = thread(&ni_daq_controller::_daq_pulse_gen_task, this);
        _daq_dio_read_worker = thread(&ni_daq_controller::_daq_dio_read_task, this);
    }

    return true;
}

void ni_daq_controller::on_loop(){

    
    
}

void ni_daq_controller::on_close(){

    /* NI DAQ Task stop */
    if(_task_handle_pulse_generation!=0){
        DAQmxStopTask(_task_handle_pulse_generation);
        DAQmxClearTask(_task_handle_pulse_generation);
    }

    if(_task_handle_dio_reader!=0){
        DAQmxStopTask(_task_handle_dio_reader);
        DAQmxClearTask(_task_handle_dio_reader);
    }

    /* work stop signal */
    _worker_stop.store(true);

    /* wait for thread termination */
    if(_daq_control_worker.joinable())
    _daq_control_worker.join();
}

void ni_daq_controller::on_message(){
    
}

void ni_daq_controller::_daq_control_task(){

    try {
        while(!_worker_stop.load()){
            try{

                /* read control message */
                zmq::multipart_t msg_multipart;
                bool success = msg_multipart.recv(*get_port("manual_control"));
                if(success){
                    string topic = msg_multipart.popstr();
                    string data = msg_multipart.popstr();
                    auto json_data = json::parse(data);

                    if(json_data.contains("function")){

                        /* 1. for move focus function processing */
                        // if(!json_data["function"].get<string>().compare("move_focus")){
                        //     int camera_id = json_data["camera_id"].get<int>();
                        //     int value = json_data["value"].get<int>();
                        //     if(_lens_controller_map.contains(camera_id)){
                        //         if(_lens_controller_map[camera_id]->_is_opened.load()){
                        //             _lens_controller_map[camera_id]->focus_move(value);
                        //             logger::info("[{}] Focus Lens moves for Camera ID #{}", get_name(), camera_id);
                        //         }
                        //     }
                        // }
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

void ni_daq_controller::_daq_pulse_gen_task(){

    /* start task */
    DAQmxStartTask(_task_handle_pulse_generation);

    try {
        while(!_worker_stop.load()){
            if(_task_handle_pulse_generation!=0){
                
                //this_thread::sleep_for(chrono::milliseconds)
            }
            else {
                logger::info("[{}] Pulse Generation Task is stopped", get_name());
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

void ni_daq_controller::_daq_dio_read_task(){

    /* start task */
    DAQmxStartTask(_task_handle_dio_reader);
    unsigned char dio_value;
    int read_samples;
    unsigned char prev_dio_value = 0;

    try {
        while(!_worker_stop.load()){
            if(_task_handle_dio_reader!=0){
                if(DAQmxReadDigitalU8(_task_handle_dio_reader, 1, 5.0, DAQmx_Val_GroupByChannel, &dio_value, 1, &read_samples, nullptr)==DAQmxSuccess){
                    if(dio_value==1 && prev_dio_value==0){ //rising edge
                        _publish_hmd_signal("hmd_signal", true);                      
                    }
                    else if(dio_value=0 && prev_dio_value==1){ //falling edge
                        _publish_hmd_signal("hmd_signal", false);
                    }

                    /* value update */
                    prev_dio_value = dio_value;
                }
            }
            else {
                logger::info("[{}] DIO Read Task is stopped", get_name());
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

void ni_daq_controller::_publish_hmd_signal(const char* portname, bool value){
    /* publish data */
    if(get_port(portname)->handle()!=nullptr){
        zmq::multipart_t msg_multipart;
        string topic = portname;

        json data_pack;
        data_pack["signal_on"] = value;
        string data = data_pack.dump();
        
        msg_multipart.addstr(topic);
        msg_multipart.addstr(data);
        msg_multipart.send(*get_port(portname), ZMQ_DONTWAIT);
    } 
}