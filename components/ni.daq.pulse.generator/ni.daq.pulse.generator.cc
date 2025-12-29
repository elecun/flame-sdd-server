
#include "ni.daq.pulse.generator.hpp"
#include <flame/log.hpp>

using namespace flame;

static ni_daq_pulse_generator* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new ni_daq_pulse_generator(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool ni_daq_pulse_generator::on_init(){

    /* get info from profile */
    _daq_device_name = get_profile()->parameters().value("daq_device_name", "Dev1");
    _daq_counter_channel = get_profile()->parameters().value("daq_counter_channel", "ctr0");
    _daq_pulse_freq = get_profile()->parameters().value("daq_pulse_freq", 30);
    _daq_pulse_samples = get_profile()->parameters().value("daq_pulse_samples", 1000);
    _daq_pulse_duty = get_profile()->parameters().value("daq_pulse_duty", 0.5);
    logger::info("[{}] Camera Triggering via {}/{} at {}(samples:{}, duty:{})", get_name(), _daq_device_name, _daq_counter_channel, _daq_pulse_freq, _daq_pulse_samples, _daq_pulse_duty);


    //_start_pulse_generation(_daq_pulse_freq, _daq_pulse_samples, _daq_pulse_duty);

    /* for manual control with pub/sub */
    // thread subscriber = thread(&ni_daq_pulse_generator::_subscribe, this, get_profile()->parameters());
    // _subscriber_handle = subscriber.native_handle();
    // subscriber.detach();

    /* for manual control with req/rep */
    thread responser = thread(&ni_daq_pulse_generator::_response, this, get_profile()->parameters());
    _responser_handle = responser.native_handle();
    responser.detach();

    return true;
}

void ni_daq_pulse_generator::on_loop(){

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

void ni_daq_pulse_generator::on_close(){

    _stop_pulse_generation();

    /* cancel the subscriber thread */
    _thread_stop_signal.store(true);
    
    // pthread_cancel(_subscriber_handle);
    // pthread_join(_subscriber_handle, nullptr);
    pthread_cancel(_responser_handle);
    pthread_join(_responser_handle, nullptr);
    
}

void ni_daq_pulse_generator::on_message(const component::message_t& msg){
    
}


bool ni_daq_pulse_generator::_start_pulse_generation(double freq, unsigned long long n_pulses, double duty){

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

void ni_daq_pulse_generator::_stop_pulse_generation(){

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

void ni_daq_pulse_generator::_subscribe(json parameters){

    pthread_setcancelstate(PTHREAD_CANCEL_ENABLE, nullptr);
    pthread_setcanceltype(PTHREAD_CANCEL_DEFERRED, nullptr);

    while(!_thread_stop_signal.load()){
        try{
            pipe_data topic;
            pipe_data json_msg;

            zmq::recv_result_t topic_result = get_port("manual_control")->recv(topic, zmq::recv_flags::none);
            zmq::recv_result_t message_result = get_port("manual_control")->recv(json_msg, zmq::recv_flags::none);

            if(message_result){
                std::string message(static_cast<char*>(json_msg.data()), json_msg.size());
                auto json_data = json::parse(message);

                if(json_data.contains("op_trigger")){
                    bool triggered = json_data["op_trigger"].get<bool>();
                    if(triggered){
                        _start_pulse_generation(_daq_pulse_freq, _daq_pulse_samples, _daq_pulse_duty);
                        logger::info("[{}] Start generating camera triggering...", get_name());
                    }
                    else {
                        _stop_pulse_generation();
                        logger::info("[{}] Stop generating camera triggering...", get_name());
                    }
                }

                logger::info("Received Message : {}", json_data.dump());
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

void ni_daq_pulse_generator::_response(json parameters){

    pthread_setcancelstate(PTHREAD_CANCEL_ENABLE, nullptr);
    pthread_setcanceltype(PTHREAD_CANCEL_DEFERRED, nullptr);

    while(!_thread_stop_signal.load()){
        try{
            pipe_data request;

            zmq::recv_result_t request_result = get_port("manual_control")->recv(request, zmq::recv_flags::none);

            if(request_result){
                std::string message(static_cast<char*>(request.data()), request.size());
                auto json_data = json::parse(message);

                if(json_data.contains("op_trigger")){
                    bool triggered = json_data["op_trigger"].get<bool>();
                    if(triggered){
                        _start_pulse_generation(_daq_pulse_freq, _daq_pulse_samples, _daq_pulse_duty);
                        logger::info("[{}] Start generating camera triggering...", get_name());
                    }
                    else {
                        _stop_pulse_generation();
                        logger::info("[{}] Stop generating camera triggering...", get_name());
                    }
                }

                logger::info("Received Message : {}", json_data.dump());

                // reply
                json reply_message = {
                    {"response_code", 1}
                };
                pipe_data reply(reply_message.dump().size());
                memcpy(reply.data(), reply_message.dump().data(), reply_message.dump().size());
                get_port("manual_control")->send(reply, zmq::send_flags::none);
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