
#include "ni.daq.controller.hpp"
#include <flame/log.hpp>
#include <algorithm>
#include <execution> // parallel
#include <iostream>

using namespace flame;

static ni_daq_controller* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new ni_daq_controller(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}


bool ni_daq_controller::on_init(){

    /* read profile */
    _daq_device_name = get_profile()->parameters().value("device_name", "Dev1");
    _daq_counter_channel = get_profile()->parameters().value("counter_channel", "ctr0:1");
    _daq_md_signal_channel_1 = get_profile()->parameters().value("md_signal_channel_1", "port1/line0");
    _daq_md_signal_channel_2 = get_profile()->parameters().value("md_signal_channel_2", "port1/line1");
    _daq_offline_signal_channel = get_profile()->parameters().value("offline_signal_channel", "port1/line2");
    _daq_online_signal_channel = get_profile()->parameters().value("online_signal_channel", "port1/line3");
    _daq_pulse_freq = get_profile()->parameters().value("counter_pulse_freq", 30.0);
    _daq_pulse_duty = get_profile()->parameters().value("counter_pulse_duty", 0.5);

    string counter_dev_channel = fmt::format("{}/{}", _daq_device_name, _daq_counter_channel);
    string di_dev_channel = fmt::format("{}/{},{}/{},{}/{},{}/{}", _daq_device_name, _daq_md_signal_channel_1,
                                                             _daq_device_name, _daq_md_signal_channel_2,
                                                             _daq_device_name, _daq_offline_signal_channel, 
                                                             _daq_device_name, _daq_online_signal_channel);

    /* start workers */
    bool auto_start = get_profile()->parameters().value("auto_start", false);
    if(auto_start){

        /* create pulse generation task */
        if(DAQmxCreateTask("camera_trigger", &_task_handle_pulse_generation)){
            logger::error("[{}] Failed to create DAQ task : Pulse Generation", get_name());
            return false;
        }

        if(DAQmxCreateCOPulseChanFreq(_task_handle_pulse_generation, counter_dev_channel.c_str(),  // device_name / counter_channel
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

        if(DAQmxCfgImplicitTiming(_task_handle_pulse_generation, DAQmx_Val_ContSamps, 1000)!=DAQmxSuccess){
            logger::error("[{}] Failed to set continuous sampling mode", get_name());
            return false;
        }

        /* create hmd signal reader task */
        if(DAQmxCreateTask("line_signal_reader", &_task_handle_dio_reader)!=DAQmxSuccess){
            logger::error("[{}] Failed to create DAQ task : Pulse Generation", get_name());
            return false;
        }

        if(DAQmxCreateDIChan(_task_handle_dio_reader, di_dev_channel.c_str(), "", DAQmx_Val_ChanPerLine)!=DAQmxSuccess){
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

    /* work stop signal */
    _worker_stop.store(true);

    /* wait for thread termination */
    if(_daq_control_worker.joinable()){
        _daq_control_worker.join();
        logger::info("[{}] DAQ Control worker is now stopped.", get_name());
    }
    if(_daq_dio_read_worker.joinable()){
        _daq_dio_read_worker.join();
        logger::info("[{}] DI Reader worker is now stopped.", get_name());
    }
    if(_daq_pulse_generation_worker.joinable()){
        _daq_pulse_generation_worker.join();
        logger::info("[{}] Pulse Generation worker is now stopped.", get_name());
    }
}

void ni_daq_controller::on_message(const component::message_t& msg){
    
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
    catch(const std::exception& e){
        logger::error("[{}] Standard Exception : {}", get_name(), e.what());
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
                // no code
            }
            else {
                logger::info("[{}] Pulse Generation Task is stopped", get_name());
                break;
            }

            this_thread::sleep_for(chrono::milliseconds(1000));
        }
    }
    catch(const zmq::error_t& e){
        logger::error("[{}] Pipeline error : {}", get_name(), e.what());
    }
    catch(const std::exception& e){
        logger::error("[{}] Standard Exception : {}", get_name(), e.what());
    }
    catch(const json::parse_error& e){
        logger::error("[{}] message cannot be parsed. {}", get_name(), e.what());
    }

    /* stop task */
    DAQmxStopTask(_task_handle_pulse_generation);  
    DAQmxClearTask(_task_handle_pulse_generation);  
}

void ni_daq_controller::_daq_dio_read_task(){

    /* start task */
    DAQmxStartTask(_task_handle_dio_reader);
    unsigned char dio_values[4] = {0,};
    int read_samples;
    unsigned char prev_dio_values[4] = {0, };

    try {
        while(!_worker_stop.load()){
            try{
                if(_task_handle_dio_reader!=0){

                    if(DAQmxReadDigitalLines(_task_handle_dio_reader, 1, 10.0, DAQmx_Val_GroupByChannel, dio_values, sizeof(dio_values), &read_samples, nullptr, nullptr)==DAQmxSuccess){

                        // line signal changed
                        if(!std::equal(dio_values, dio_values + sizeof(dio_values), prev_dio_values)){
                            _publish_line_signal("line_signal", dio_values);
                            logger::info("[{}] MD_1({}), MD_2({}), Online({}), Offline({})", get_name(), dio_values[1], dio_values[0], dio_values[3], dio_values[2]);
                        }

                        /* value updates */
                        memcpy(prev_dio_values, dio_values, sizeof(dio_values));
                    }
                }
            }
            catch(const zmq::error_t& e){
                logger::error("[{}] Pipeline error : {}", get_name(), e.what());
                break;
            }

            this_thread::sleep_for(chrono::milliseconds(100));
        }
    }
    catch(const zmq::error_t& e){
        logger::error("[{}] Pipeline error : {}", get_name(), e.what());
    }
    catch(const std::exception& e){
        logger::error("[{}] Standard Exception : {}", get_name(), e.what());
    }
    catch(const json::parse_error& e){
        logger::error("[{}] message cannot be parsed. {}", get_name(), e.what());
    }

    /* stop task */
    DAQmxStopTask(_task_handle_dio_reader);    
    DAQmxClearTask(_task_handle_dio_reader);
}


void ni_daq_controller::_publish_line_signal(const char* portname, unsigned char* value){
    /* publish data */
    if(get_port(portname)->handle()!=nullptr){
        zmq::multipart_t msg_multipart;
        string topic = fmt::format("{}/{}",get_name(), portname);

        json data_pack;
        data_pack["online_signal_on"] = static_cast<bool>(value[3]); //online
        data_pack["offline_signal_on"] = static_cast<bool>(value[2]); // offline
        data_pack["hmd_signal_1_on"] = static_cast<bool>(value[1]); //md signal
        data_pack["hmd_signal_2_on"] = static_cast<bool>(value[0]); //md signal
        string data = data_pack.dump();
        
        msg_multipart.addstr(topic);
        msg_multipart.addstr(data);
        msg_multipart.send(*get_port(portname), ZMQ_DONTWAIT);
    }
}