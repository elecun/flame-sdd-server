
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

        /* read parameters */
        json param = get_profile()->parameters();
        if(param.contains("stream_method")){ 
            string _set_method = param["stream_method"];
            std::transform(_set_method.begin(), _set_method.end(), _set_method.begin(), ::tolower);
            _stream_method = _method_type[_set_method];
        }

        /* publish image for monitoring in realtime */
        if(param.contains("realtime_monitoring")){
            _monitoring = param["realtime_monitoring"].get<bool>();
        }

        /* if stream method is 'batch' mode, buffer reservation is required for memory optimization */
        if(_stream_method==_method_type["batch"]){
            if(param.contains("stream_batch_reserved")){
                _stream_batch_buffer_size = param["stream_batch_reserved"].get<int>();
            }
        }

        //1. pylon initialization
        PylonInitialize();

        //2. find GigE cameras
        CTlFactory& tlFactory = CTlFactory::GetInstance();
        DeviceInfoList_t devices;
        tlFactory.EnumerateDevices(devices);
        if(devices.size()>=1)
            logger::info("[{}] Found {} cameras", get_name(), devices.size());

        //3. create device & insert to device map
        for(int idx=0;idx<(int)devices.size();idx++){
            _device_map.insert(make_pair(stoi(devices[idx].GetUserDefinedName().c_str()), 
                            new CBaslerUniversalInstantCamera(tlFactory.CreateDevice(devices[idx]))));
            // _monitoring[stoi(devices[idx].GetUserDefinedName().c_str())].store(false);
            logger::info("[{}] Found User ID {}, (SN:{}, Address : {})", get_name(), devices[idx].GetUserDefinedName().c_str(), devices[idx].GetSerialNumber().c_str(), devices[idx].GetIpAddress().c_str());
        }

        //4. device control handle assign for each camera
        for(const auto& camera:_device_map){
            thread worker = thread(&basler_gige_cam_grabber::_image_stream_task, this, camera.first, camera.second, get_profile()->parameters());
            _camera_grab_worker[camera.first] = worker.native_handle();
            _camera_grab_counter[camera.first] = 0;
            worker.detach();
            logger::info("[{}] worker #{} detached", get_name(), camera.first);
        }

        /* camera status ready with default profile */
        json defined_cameras = get_profile()->parameters()["cameras"];
        for(auto& camera:defined_cameras){
            int id = camera["id"].get<int>();
            _camera_status.insert(make_pair(id, camera));
            _camera_status[id]["frames"] = 0;  // add frames (unsigned long long)
            _camera_status[id]["status"] = "-"; // add status (-|working|connected)

            // image container reserve
            if(_stream_method==_method_type["batch"]){
                _image_container[id].reserve(_stream_batch_buffer_size);
            }
        }

        /* component status monitoring subtask */
        // thread status_monitor_worker = thread(&basler_gige_cam_grabber::_subtask_status_publish, this, get_profile()->parameters());
        // _subtask_status_publisher = status_monitor_worker.native_handle();
        // status_monitor_worker.detach();

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

/* status publisher subtask impl. */
void basler_gige_cam_grabber::_subtask_status_publish(json parameters){
    while(!_thread_stop_signal){
        _publish_status();
        this_thread::sleep_for(chrono::seconds(1));
    }
}

void basler_gige_cam_grabber::on_loop(){


}

void basler_gige_cam_grabber::on_close(){

    /* thread stop */
    _thread_stop_signal = true;

    /* show container size */
    for (map<int, vector<vector<unsigned char>>>::iterator it = _image_container.begin(); it != _image_container.end(); ++it){
        logger::info("[{}] Image Container size : {}", it->first, _image_container[it->first].size());
    }

    /* camera grab thread will be killed */
    for(auto& worker:_camera_grab_worker){
        pthread_cancel(worker.second);
        pthread_join(worker.second, nullptr);
    }
    _camera_grab_worker.clear();

    /* camera close and delete */
    for(auto& camera:_device_map){
        if(camera.second->IsOpen()){
            camera.second->StopGrabbing();
            camera.second->Close();
            delete camera.second;
        }
        
    }

    /* close status monitoring subtask */
    pthread_cancel(_subtask_status_publisher);
    pthread_join(_subtask_status_publisher, nullptr);

    PylonTerminate();
}

void basler_gige_cam_grabber::on_message(){
    
}

void basler_gige_cam_grabber::_publish_status(){

    /* update the camera working status */
    for(auto& camera:_device_map){
        if(camera.second->IsGrabbing())
            _camera_status[camera.first]["status"] = "working";
        else {
            _camera_status[camera.first]["status"] = "not working";
        }
    }

    /* update the camera frame for each */
    for(auto& camera:_camera_grab_counter){
        _camera_status[camera.first]["frames"] = camera.second;
    }

    /* combine camera status */
    json combined_status;
    for(auto& camera:_camera_status){
        combined_status.push_back(_camera_status[camera.first]);
    }

    /* transfer(publish) status data */
    try{
        string status_message = combined_status.dump();
        string topic = fmt::format("{}", get_name(), "status");
        pipe_data topic_msg(topic.data(), topic.size());
        pipe_data end_msg(status_message.data(), status_message.size());
        get_port("status")->send(topic_msg, zmq::send_flags::sndmore);
        get_port("status")->send(end_msg, zmq::send_flags::dontwait);

        logger::info("published the camera status ({})", topic);
    }
    catch(std::runtime_error& e){
        logger::error("{}", e.what());
    }
}

void basler_gige_cam_grabber::_status_monitor_task(json parameters){
    while(!_thread_stop_signal){
        this_thread::sleep_for(chrono::milliseconds(1000));
    }
}

// camera status publish
void basler_gige_cam_grabber::_status_publish(){
    json defined_cameras = get_profile()->parameters()["cameras"];
    for(auto& camera:defined_cameras){
        int id = camera["id"].get<int>();
        _camera_status.insert(make_pair(id, camera));
        _camera_status[id]["frames"] = 0;  // add frames (unsigned long long)
        _camera_status[id]["status"] = "-"; // add status (-|working|connected)
    }
}


void basler_gige_cam_grabber::_image_stream_task(int camera_id, CBaslerUniversalInstantCamera* camera, json parameters){
    try{
        //pthread_setcancelstate(PTHREAD_CANCEL_ENABLE, nullptr);
        //pthread_setcanceltype(PTHREAD_CANCEL_DEFERRED, nullptr);

        camera->Open();
        string acquisition_mode = parameters.value("acquisition_mode", "Continuous"); // Continuous, SingleFrame, MultiFrame
        double acquisition_fps = parameters.value("acquisition_fps", 30.0);
        string trigger_selector = parameters.value("trigger_selector", "FrameStart");
        string trigger_mode = parameters.value("trigger_mode", "On");
        string trigger_source = parameters.value("trigger_source", "Line2");
        string trigger_activation = parameters.value("trigger_activation", "RisingEdge");
        int heartbeat_timeout = parameters.value("heartbeat_timeout", 5000);

        /* camera setting parameters notification */
        logger::info("[{}]* Camera Acquisition Mode : {} (Continuous|SingleFrame)", get_name(), acquisition_mode);
        //logger::info("[{}]* Camera Acqusition Framerate : {}", get_name(), acquisition_fps);
        logger::info("[{}]* Camera Trigger Mode : {}", get_name(), trigger_mode);
        logger::info("[{}]* Camera Trigger Selector : {}", get_name(), trigger_selector);
        logger::info("[{}]* Camera Trigger Activation : {}", get_name(), trigger_activation);
        
        /* set camera parameters */
        camera->AcquisitionMode.SetValue(acquisition_mode.c_str());
        camera->AcquisitionFrameRate.SetValue(acquisition_fps);
        //camera->AcquisitionFrameRateEnable.setValue(false);
        camera->TriggerSelector.SetValue(trigger_selector.c_str());
        camera->TriggerMode.SetValue(trigger_mode.c_str());
        camera->TriggerSource.SetValue(trigger_source.c_str());
        camera->TriggerActivation.SetValue(trigger_activation.c_str());
        //camera->GevHeartbeatTimeout.SetValue(heartbeat_timeout);

        /* start grabbing */
        camera->StartGrabbing(Pylon::GrabStrategy_OneByOne, Pylon::GrabLoop_ProvidedByUser);
        CGrabResultPtr ptrGrabResult;

        while(camera->IsGrabbing() && !_thread_stop_signal){
            //logger::info("[{}] worker #{} start", get_name(), camera_id);
            try{
                camera->RetrieveResult(5000, ptrGrabResult, Pylon::TimeoutHandling_ThrowException); //trigger mode makes it blocked
                if(ptrGrabResult.IsValid()){
                    if(ptrGrabResult->GrabSucceeded()){

                        //logger::info("[{}] worker #{} grabbed", get_name(), camera_id);

                        auto start = std::chrono::system_clock::now();

                        /* grabbed imgae stores into buffer */
                        const uint8_t* pImageBuffer = (uint8_t*)ptrGrabResult->GetBuffer();
                        _camera_grab_counter[camera_id]++;

                        /* get image properties */
                        size_t size = ptrGrabResult->GetWidth() * ptrGrabResult->GetHeight();
                        cv::Mat image(ptrGrabResult->GetHeight(), ptrGrabResult->GetWidth(), CV_8UC1, (void*)pImageBuffer);

                        //jpg encoding
                        std::vector<unsigned char> serialized_image;
                        cv::imencode(".jpg", image, serialized_image);

                        // save into image data container
                        // if(_stream_method==0) // batch mode
                        //     _image_container[camera_id].emplace_back(buffer);

                        /* common transport parameters */
                        string id_str = fmt::format("{}",camera_id);
                        pipe_data msg_id(id_str.data(), id_str.size());
                        pipe_data msg_image(serialized_image.data(), serialized_image.size());

                        // /* push image data */
                        string nas_port = fmt::format("image_stream_{}", camera_id);
                        if(get_port(nas_port)->handle()!=nullptr){
                            zmq::multipart_t msg_multipart_image;
                            msg_multipart_image.addstr(id_str);
                            msg_multipart_image.addmem(serialized_image.data(), serialized_image.size());
                            msg_multipart_image.send(*get_port(nas_port), ZMQ_DONTWAIT);
                            logger::info("[{}] {} sent image to pipieline ", get_name(), camera_id);
                        }
                        else{
                            logger::warn("[{}] {} socket handle is not valid ", get_name(), camera_id);
                        }
                        // get_port("image_stream")->send(msg_id, zmq::send_flags::sndmore);
                        // get_port("image_stream")->send(msg_image, zmq::send_flags::dontwait);



                        /* publish for monitoring (size reduction for performance)*/
                        if(_monitoring){
                            string topic_str = fmt::format("camera_{}", camera_id);
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

                            string camera_port = fmt::format("image_stream_monitor_{}", camera_id);
                            msg_multipart.send(*get_port(camera_port), ZMQ_DONTWAIT);

                            auto end = std::chrono::system_clock::now();
                            spdlog::info("Processing Time : {} sec", std::chrono::duration<double, std::chrono::seconds::period>(end - start).count());
                            logger::info("[{}] {} sent monitor image", get_name(), camera_id);
                        }

                        //logger::info("[{}] {} image grabbed", get_name(), camera_id);
                    }
                    else{
                        logger::warn("[{}] Error-code({}) : {}", get_name(), ptrGrabResult->GetErrorCode(), ptrGrabResult->GetErrorDescription().c_str());
                    }
                }
                else{
                    logger::warn("[{}] Grab result is invalid",get_name());
                    break;
                }
            }
            catch(Pylon::TimeoutException& e){
                logger::error("[{}] Camera {} Timeout exception occurred! {}", get_name(), camera_id, e.GetDescription());
                break;
            }
            catch(Pylon::RuntimeException& e){
                logger::error("[{}] Camera {} Runtime Exception ({})", get_name(), camera_id, e.what());
            }
            catch(const zmq::error_t& e){
                logger::error("[{}] {}", get_name(), e.what());
            }
        }

        camera->StopGrabbing();
        camera->Close();
    }
    catch(const GenericException& e){
        logger::error("[{}] {}", get_name(), e.GetDescription());
    }
}
