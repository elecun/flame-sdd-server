
#include "basler.gige.cam.grabber.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>
#include <opencv2/opencv.hpp>
#include <chrono>

using namespace flame;
using namespace std;
using namespace cv;

/* create component instance */
static basler_gige_cam_grabber* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new basler_gige_cam_grabber(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}


bool basler_gige_cam_grabber::on_init(){

    try{

        /* get parameters from profile */
        json parameters = get_profile()->parameters();

        /* read profile */
        _prof_realtime_monitoring.store(parameters.value("realtime_monitoring", false));

        /* read preset path */
        if(get_profile()->parameters().contains("preset_path")){
            _preset_path = get_profile()->parameters()["preset_path"].get<string>();
            logger::info("[{}] Preset path : {}", get_name(), _preset_path);
        }

        /* pylon initialize */
        PylonInitialize();

        /* find GigE cameras in same netwrok */
        CTlFactory& tlFactory = CTlFactory::GetInstance();
        DeviceInfoList_t devices;
        tlFactory.EnumerateDevices(devices);
        if(devices.size()>=1)
            logger::info("[{}] Found {} cameras", get_name(), devices.size());

        /* create device & insert to device container */
        for(int idx=0;idx<(int)devices.size();idx++){
            _device_map.insert(make_pair(stoi(devices[idx].GetUserDefinedName().c_str()), new CBaslerUniversalInstantCamera(tlFactory.CreateDevice(devices[idx]))));
            logger::info("[{}] Found Camera ID {}, (SN:{}, Address : {})", get_name(), devices[idx].GetUserDefinedName().c_str(), devices[idx].GetSerialNumber().c_str(), devices[idx].GetIpAddress().c_str());
        }

        /* device control handle assign for each camera */
        for(const auto& camera:_device_map){
            _camera_grab_worker[camera.first] = thread(&basler_gige_cam_grabber::_image_stream_task, this, camera.first, camera.second, get_profile()->parameters());
            _camera_control_worker[camera.first] = thread(&basler_gige_cam_grabber::_camera_control_task, this, camera.first, camera.second);
            logger::info("[{}] Camera #{} Grabber is running...", get_name(), camera.first);
        }

        /* image stream control worker */
        _image_stream_control_worker = thread(&basler_gige_cam_grabber::_image_stream_control_task, this);

        /* level2 interface worker */
        if(parameters.contains("use_level2_interface")){
            bool enable = parameters.value("use_level2_interface", false);
            if(enable){
                _level2_dispatch_worker = thread(&basler_gige_cam_grabber::_level2_dispatch_task, this);
                logger::info("[{}] Level2 Data interface is running...", get_name());
            }
        }

        if(parameters.contains("use_entry_signal")){
            bool enable = parameters.value("use_entry_signal", false);
            if(enable){
                _entry_signal_worker = thread(&basler_gige_cam_grabber::_entry_signal_subscribe, this);
                logger::info("[{}] Entry Signal subscriber is running...", get_name());
            }
        }

    }
    catch(const GenericException& e){
        logger::error("[{}] Pylon Generic Exception : {}", get_name(), e.GetDescription());
        return false;
    }
    catch(json::exception& e){
        logger::error("Profile Error : {}", e.what());
        return false;
    }

    return true;
}

void basler_gige_cam_grabber::on_loop(){

    /* camera status update (publish) */
    for(auto& camera:_device_map){
        json status_data;
        status_data["frames"] = _camera_grab_counter[camera.first].load();
        _camera_status[fmt::format("{}",camera.first)] = status_data;
    }

    /* message serialize */
    zmq::multipart_t msg_multipart;
    json status = _camera_status;
    string serialized_data = status.dump();
    string topic = fmt::format("{}/status", get_name());

    msg_multipart.addstr(topic);
    msg_multipart.addstr(serialized_data);

    /* send status */
    msg_multipart.send(*get_port("status"), ZMQ_DONTWAIT);

}


void basler_gige_cam_grabber::on_close(){

    /* stop grabbing (must be first!!!) */
    for_each(_device_map.begin(), _device_map.end(), [](auto& camera){
        camera.second->StopGrabbing();
    });

    /* work stop signal */
    _image_stream_enable.store(false);
    _worker_stop.store(true);


    /* stop image control workers */
    if(_image_stream_control_worker.joinable()){
        _image_stream_control_worker.join();
        logger::info("[{}] Image Stream Control Worker is now stopped", get_name());
    }

    /* stop the level2 interface worker */
    if(_level2_dispatch_worker.joinable()){
        _level2_dispatch_worker.join();
        logger::info("[{}] Level2 Interface Data dispatcher is now stopped", get_name());
    }

    /* stio the entry signal subscriber worker */
    if(_entry_signal_worker.joinable()){
        _entry_signal_worker.join();
        logger::info("[{}] Entry Signal subscriber is now stopped", get_name());
    }

    /* stop camera control workers */
    for_each(_camera_control_worker.begin(), _camera_control_worker.end(), [](auto& t) {
        if(t.second.joinable()){
            t.second.join();
            logger::info("- Camera #{} Controller is now stopped", t.first);
        }
    });

    /* stop camera grab workers */
    for_each(_camera_grab_worker.begin(), _camera_grab_worker.end(), [](auto& t) {
        if(t.second.joinable()){
            t.second.join();
            logger::info("- Camera #{} Grabber is now stopped", t.first);
        }
    });

    _camera_grab_worker.clear();

    /* camera close and delete */
    for(auto& camera:_device_map){
        if(camera.second->IsOpen()){
            camera.second->Close();
            delete camera.second;
        }
    }

    PylonTerminate();
}

void basler_gige_cam_grabber::on_message(){
    
}

void basler_gige_cam_grabber::_camera_control_task(int camera_id, CBaslerUniversalInstantCamera* camera){
    try{
        while(!_worker_stop.load()){
            try{
                pipe_data message;
                string portname = fmt::format("camera_control_{}", camera_id);
                
                vector<pipe_data> recv_msg;
                zmq::recv_result_t result = zmq::recv_multipart(*get_port(portname), std::back_inserter(recv_msg));

                
                if(result.has_value()){
                    if(recv_msg.size()==2){
                        string topic(static_cast<char*>(recv_msg[0].data()), recv_msg[0].size());
                        string msg_data(static_cast<char*>(recv_msg[1].data()), recv_msg[1].size());

                        /* camera_control_<> port */
                        if(!topic.compare(portname)){
                            auto msg_param = json::parse(msg_data);
                            if(msg_param.contains("function")){

                                // set_exposure_time function
                                if(!msg_param["function"].get<string>().compare("set_exposure_time")){
                                    CFloatParameter exposureTime(camera->GetNodeMap(), "ExposureTime");
                                    double exposure_time = msg_param.value("value", 5000.0);
                                    if(exposureTime.IsWritable()) {
                                        exposureTime.SetValue(exposure_time);
                                        logger::info("[{}] Set Camera #{} exposure time to {}", get_name(), camera_id, exposure_time);
                                    }
                                }
                            }
                            else {
                                logger::warn("[{}] 'function' does not contained in message");
                            }
                        }       
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

void basler_gige_cam_grabber::_image_stream_control_task(){
    try{
        while(!_worker_stop.load()){
            try{
                /* wait for hmd_signal subscription */
                zmq::multipart_t msg_multipart;
                bool success = msg_multipart.recv(*get_port("hmd_signal"));

                if(success){
                    string topic = msg_multipart.popstr();
                    string data = msg_multipart.popstr();
                    auto json_data = json::parse(data);

                    if(json_data.contains("signal_on")){
                        bool signal_on = json_data["signal_on"].get<bool>();
                        _image_stream_enable.store(signal_on);
                        logger::info("[{}] HMD Signal : {}", get_name(), signal_on);
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

void basler_gige_cam_grabber::_image_stream_task(int camera_id, CBaslerUniversalInstantCamera* camera, json parameters){
    try{
        camera->Open();
        string acquisition_mode = parameters.value("acquisition_mode", "Continuous"); // Continuous, SingleFrame, MultiFrame
        double acquisition_fps = parameters.value("acquisition_fps", 30.0);
        string trigger_selector = parameters.value("trigger_selector", "FrameStart");
        string trigger_mode = parameters.value("trigger_mode", "On");
        string trigger_source = parameters.value("trigger_source", "Line2");
        string trigger_activation = parameters.value("trigger_activation", "RisingEdge");
        int heartbeat_timeout = parameters.value("heartbeat_timeout", 5000);
        
        
        // camera exposure time set (initial)
        for(auto& param:parameters["cameras"]){
            int id = param["id"].get<int>();
            if(id==camera_id){
                double exposure_time = param.value("exposure_time", 5000.0);
                CEnumerationPtr(camera->GetNodeMap().GetNode("ExposureAuto"))->FromString("Off");
                CFloatParameter exposureTime(camera->GetNodeMap(), "ExposureTime");
                if(exposureTime.IsWritable()) {
                    exposureTime.SetValue(exposure_time);
                    logger::info("[{}] Camera #{} Exposure Time set : {}", get_name(), camera_id, exposure_time);
                }
            }
        }

        /* camera setting parameters notification */
        logger::info("[{}]* Camera Acquisition Mode : {} (Continuous|SingleFrame)", get_name(), acquisition_mode);
        logger::info("[{}]* Camera Acqusition Framerate : {}", get_name(), acquisition_fps);
        logger::info("[{}]* Camera Trigger Mode : {}", get_name(), trigger_mode);
        logger::info("[{}]* Camera Trigger Selector : {}", get_name(), trigger_selector);
        logger::info("[{}]* Camera Trigger Activation : {}", get_name(), trigger_activation);
        
        /* set camera parameters */
        camera->AcquisitionMode.SetValue(acquisition_mode.c_str());
        camera->AcquisitionFrameRate.SetValue(acquisition_fps);
        camera->AcquisitionFrameRateEnable.SetValue(false);
        camera->TriggerSelector.SetValue(trigger_selector.c_str());
        camera->TriggerMode.SetValue(trigger_mode.c_str());
        camera->TriggerSource.SetValue(trigger_source.c_str());
        camera->TriggerActivation.SetValue(trigger_activation.c_str());
        camera->GevHeartbeatTimeout.SetValue(heartbeat_timeout);

        /* start grabbing */
        camera->StartGrabbing(Pylon::GrabStrategy_OneByOne, Pylon::GrabLoop_ProvidedByUser);
        CGrabResultPtr ptrGrabResult;

        logger::info("[{}] Camera #{} grabber is now running...",get_name(), camera_id);
        unsigned long long camera_grab_counter = 0;
        while(!_worker_stop.load()){
            try{
                if(!camera->IsGrabbing())
                    break;

                //change camera exposure time value by level2 info.
                if(_camera_exposure_time.contains(camera_id)){
                    int extime = _camera_exposure_time[camera_id].load();
                    if(extime!=0){
                        CFloatParameter param(camera->GetNodeMap(), "ExposureTime");
                        if(param.IsWritable()) {
                            param.SetValue((double)extime);
                            logger::info("[{}] Camera #{} Exposure Time set : {}", get_name(), camera_id, extime);
                            _camera_exposure_time[camera_id].store(0);
                        }
                    }
                }
                
                bool success = camera->RetrieveResult(5000, ptrGrabResult, Pylon::TimeoutHandling_ThrowException); //trigger mode makes it blocked
                if(!success){
                    logger::warn("[{}] Camera #{} will be terminated by force.", get_name(), camera_id);
                    break;
                }
                else { // no timeout, success
                    if(ptrGrabResult.IsValid()){
                        if(ptrGrabResult->GrabSucceeded()){
    
                            auto start = std::chrono::system_clock::now();
    
                            /* grabbed imgae stores into buffer */
                            const uint8_t* pImageBuffer = (uint8_t*)ptrGrabResult->GetBuffer();
    
                            /* get image properties */
                            size_t size = ptrGrabResult->GetWidth() * ptrGrabResult->GetHeight();
                            cv::Mat image(ptrGrabResult->GetHeight(), ptrGrabResult->GetWidth(), CV_8UC1, (void*)pImageBuffer);
    
                            //jpg encoding
                            std::vector<unsigned char> serialized_image;
                            cv::imencode(".jpg", image, serialized_image);
    
                            /* common transport parameters */
                            string id_str = fmt::format("{}",camera_id);
    
                            /* push image data */
                            if(_image_stream_enable.load() && _entry_signal_on.load()){
                                /* camera grab status update */
                                _camera_grab_counter[camera_id].store(++camera_grab_counter);
    
                                pipe_data msg_id(id_str.data(), id_str.size());
                                pipe_data msg_image(serialized_image.data(), serialized_image.size());
    
                                string image_stream_port = fmt::format("image_stream_{}", camera_id);
                                if(get_port(image_stream_port)->handle()!=nullptr){
                                    zmq::multipart_t msg_multipart_image;
                                    msg_multipart_image.addstr(id_str);
                                    msg_multipart_image.addmem(serialized_image.data(), serialized_image.size());
                                    msg_multipart_image.send(*get_port(image_stream_port), ZMQ_DONTWAIT);
                                }
                                else{
                                    logger::warn("[{}] {} socket handle is not valid ", get_name(), camera_id);
                                }
                            }
    
    
                            /* publish for monitoring (size reduction for performance)*/
                            if(_prof_realtime_monitoring.load()){
                                string topic_str = fmt::format("image_stream_monitor_{}", camera_id);
                                pipe_data msg_topic(topic_str.data(), topic_str.size());
                                cv::Mat monitor_image;
                                cv::resize(image, monitor_image, cv::Size(image.cols/6, image.rows/6));
                                std::vector<unsigned char> serialized_monitor_image;
                                cv::imencode(".jpg", monitor_image, serialized_monitor_image);
                                pipe_data msg_monitor_image(serialized_monitor_image.data(), serialized_monitor_image.size());
    
                                zmq::multipart_t msg_multipart;
                                msg_multipart.addstr(topic_str);
                                msg_multipart.addstr(id_str);
                                msg_multipart.addmem(serialized_monitor_image.data(), serialized_monitor_image.size());
    
                                string camera_port = fmt::format("image_stream_monitor_{}", camera_id); //portname = topic
                                msg_multipart.send(*get_port(camera_port), ZMQ_DONTWAIT);
    
                                auto end = std::chrono::system_clock::now();
                                //spdlog::info("Processing Time : {} sec", std::chrono::duration<double, std::chrono::seconds::period>(end - start).count());
                                //logger::info("[{}] {} sent monitor image", get_name(), camera_id);
                            }
                        }
                        else{
                            logger::warn("[{}] Error-code({}) : {}", get_name(), ptrGrabResult->GetErrorCode(), ptrGrabResult->GetErrorDescription().c_str());
                        }
                    }
                }
                
            }
            catch(Pylon::RuntimeException& e){
                logger::error("[{}] Camera {} Runtime Exception ({})", get_name(), camera_id, e.what());
                break;
            }
            catch(const Pylon::GenericException& e){
                logger::error("[{}] Camera {} Generic Exception ({})", get_name(), camera_id, e.what());
                break;
            }
            catch(const zmq::error_t& e){
                logger::error("[{}] {}", get_name(), e.what());
                break;
            }
        }

        /* stop grabbing */
        camera->StopGrabbing();
        camera->Close();
        logger::info("[{}] Camera #{} grabber is now closed", get_name(), camera_id);
    }
    catch(const GenericException& e){
        logger::error("[{}] {}", get_name(), e.GetDescription());
    }
}


void basler_gige_cam_grabber::_level2_dispatch_task(){
    try{
        while(!_worker_stop.load()){
            try{
                zmq::multipart_t msg_multipart;
                bool success = msg_multipart.recv(*get_port("lv2_dispatch"));
                if(success){
                    string topic = msg_multipart.popstr();
                    string data = msg_multipart.popstr();
                    auto json_data = json::parse(data);

                    // level2 data processing
                    if(json_data.contains("mt_stand_height") && json_data.contains("mt_stand_width") && json_data.contains("mt_stand_t1") && json_data.contains("mt_stand_t2")){

                        /* 1. for move focus function processing */
                        int height = json_data["mt_stand_height"].get<int>();
                        int width = json_data["mt_stand_width"].get<int>();
                        double t1 = json_data["mt_stand_t1"].get<double>();
                        double t2 = json_data["mt_stand_t2"].get<double>();

                        /* find file */
                        string preset_file = fmt::format("{}/{}_{}_{}_{}.preset", _preset_path, height, width, t1, t2);
                        if(!std::filesystem::exists(preset_file)){
                            logger::error("[{}] Preset file not found : {}", get_name(), preset_file);
                        }
                        else{
                            logger::info("[{}] Applying preset file : {}", get_name(), preset_file);
                            try{
                                std::ifstream file(preset_file);
                                json et_preset;
                                file >> et_preset;
                                
                                if(et_preset.contains("camera_exposure_time")){
                                    for(auto& [camera_id, et_value]:et_preset["camera_exposure_time"].items()){
                                        int id = stoi(camera_id);
                                        _camera_exposure_time[id].store(et_value.get<int>());
                                        logger::info("[{}] ready to change camera exposure time", get_name(), id);
                                    }
                                }
                            }
                            catch(const json::exception& e){
                                logger::error("[{}] Preset file parse error : {}", get_name(), e.what());
                            }
                        }
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

void basler_gige_cam_grabber::_entry_signal_subscribe(){
    try{
        while(!_worker_stop.load()){
            try{
                zmq::multipart_t msg_multipart;
                bool success = msg_multipart.recv(*get_port("entry_signal"));
                if(success){
                    string topic = msg_multipart.popstr();
                    string data = msg_multipart.popstr();
                    auto json_data = json::parse(data);

                    if(json_data.contains("signal_on")){
                        bool signal_on = json_data["signal_on"].get<bool>();
                        _entry_signal_on.store(signal_on);
                        logger::info("[{}] Entry Signal(Online) ON : {}", get_name(), signal_on);
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