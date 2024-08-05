
#include "dk.ni.daq.handler.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>

using namespace flame;

static dk_ni_daq_handler* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new dk_ni_daq_handler(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool dk_ni_daq_handler::on_init(){

    /* get info from profile */
    _daq_device_name = get_profile()->parameters().value("daq_device_name", "Dev1");
    _daq_counter_channel = get_profile()->parameters().value("daq_counter_channel", "ctr0");
    _daq_pulse_freq = get_profile()->parameters().value("daq_pulse_freq", 30);
    _daq_pulse_samples = get_profile()->parameters().value("daq_pulse_samples", 1000);
    _daq_pulse_duty = get_profile()->parameters().value("daq_pulse_duty", 0.5);
    logger::info("[{}] Camera Triggering via {}/{} at {}(samples:{}, duty:{})", get_name(), _daq_device_name, _daq_counter_channel, _daq_pulse_freq, _daq_pulse_samples, _daq_pulse_duty);



    //_start_pulse_generation(_daq_pulse_freq, _daq_pulse_samples, _daq_pulse_duty);
    thread subscriber = thread(&dk_ni_daq_handler::_subscribe, this, get_profile()->parameters());
    _subscriber_handle = subscriber.native_handle();
    subscriber.detach();

    return true;
}

void dk_ni_daq_handler::on_loop(){

    /* create message */
    map<string, unsigned long long> daq_status;
    daq_status.insert(make_pair("triggering", _triggering.load()));
    json info = daq_status;
    string status_message = info.dump();

    /* camera grabbing info publish */
    string topic = fmt::format("{}/{}", get_name(), "/status");
    pipe_data topic_msg(topic.data(), topic.size());
    pipe_data end_msg(status_message.data(), status_message.size());
    get_port("status")->send(topic_msg, zmq::send_flags::sndmore);
    get_port("status")->send(end_msg, zmq::send_flags::dontwait);
    
}

void dk_ni_daq_handler::on_close(){

    _stop_pulse_generation();

    /* cancel the subscriber thread */
    _thread_stop_signal.store(true);
    pthread_cancel(_subscriber_handle);
    pthread_join(_subscriber_handle, nullptr);
    
}

void dk_ni_daq_handler::on_message(){
    
}


bool dk_ni_daq_handler::_start_pulse_generation(double freq, unsigned long long n_pulses, double duty){

    string channel = fmt::format("{}/{}", _daq_device_name, _daq_counter_channel);

    /* create task handle */
    if(DAQmxCreateTask("camera_trigger", &_handle_pulsegen_task)){
        logger::error("[{}] Failed to create DAQ task", get_name());
        return false;
    }

    /* create counter config to generate pulse */
    if(DAQmxCreateCOPulseChanFreq(_handle_pulsegen_task, channel.c_str(),  // device_name / counter_channel
                                    "",               // Name of the virtual channel (optional)
                                    DAQmx_Val_Hz,     // units
                                    DAQmx_Val_Low,    // idle state
                                    0.0,              // initial delay
                                    freq,             // frequency
                                    duty               // Duty cycle
    )){
        logger::error("[{}] Failed to create pulse channel", get_name());
        DAQmxClearTask(_handle_pulsegen_task);
        return false;
    }

    /* set timing for infinite pulse generation */
    // Note! Finite sample : DAQmx_Val_FiniteSamps
    // Note! Infinite sample : DAQmx_Val_ContSamps
    if(DAQmxCfgImplicitTiming(_handle_pulsegen_task, DAQmx_Val_ContSamps, n_pulses)){
        logger::error("[{}] Failed to configure timing", get_name());
        DAQmxClearTask(_handle_pulsegen_task);
        return false;
    }

    /* start to run task */
    if(DAQmxStartTask(_handle_pulsegen_task)){
        logger::error("[{}] Failed to run the pulse generation", get_name());
        DAQmxClearTask(_handle_pulsegen_task);
        return false;
    }

    logger::info("[{}] Started the camera trigger pulse generation", get_name());
    _triggering.store(true);

    return true;
}

void dk_ni_daq_handler::_stop_pulse_generation(){

    if(_handle_pulsegen_task){
        if(DAQmxStopTask(_handle_pulsegen_task)) {
            logger::error("[{}] Failed to stop the pulse generation task", get_name());
        }
        
        DAQmxClearTask(_handle_pulsegen_task);
        _handle_pulsegen_task = nullptr;

        logger::info("[{}] Stopped the camera trigger pulse generation", get_name());
        _triggering.store(false);
    }
    
}

void dk_ni_daq_handler::_subscribe(json parameters){

    pthread_setcancelstate(PTHREAD_CANCEL_ENABLE, nullptr);
    pthread_setcanceltype(PTHREAD_CANCEL_DEFERRED, nullptr);

    while(!_thread_stop_signal.load()){
        try{
            pipe_data received_topic;
            pipe_data received_message;

            zmq::recv_result_t topic_result = get_port("manual_control")->recv(received_topic, zmq::recv_flags::none);
            zmq::recv_result_t message_result = get_port("manual_control")->recv(received_message, zmq::recv_flags::none);
            if(message_result){
                std::string message(static_cast<char*>(received_message.data()), received_message.size());
                auto json_data = json::parse(message);
                logger::info("{}", json_data.dump());

                if(json_data.contains("op_trigger")){
                    bool triggered = json_data["op_trigger"].get<bool>();
                    if(triggered){
                        _start_pulse_generation(_daq_pulse_freq, _daq_pulse_samples, _daq_pulse_duty);
                        // string json_string = json_data.dump();
                        // pipe_data message(json_string.size());
                        // memcpy(message.data(), json_string.data(), json_string.size());
                        // get_port("op_trigger")->send(message, zmq::send_flags::dontwait);
                    }
                    else {
                        _stop_pulse_generation();
                    }
                }
            }
        }
        catch(const json::parse_error& e){
            logger::error("[{}] message cannot be parsed. {}", get_name(), e.what());
        }
        catch(const std::runtime_error& e){
            logger::error("[{}] Runtime error occurred!", get_name());
        }
    }

}