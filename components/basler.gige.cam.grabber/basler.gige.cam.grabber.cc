
#include "basler.gige.cam.grabber.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>
#include <opencv2/opencv.hpp>
#include <chrono>

using namespace flame;
using namespace std;

static basler_gige_cam_grabber* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new basler_gige_cam_grabber(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}


bool basler_gige_cam_grabber::on_init(){

    try{

        //stream method check
        json param = get_profile()->parameters();
        if(param.contains("stream_method")){ 
            string _set_method = param["stream_method"];
            std::transform(_set_method.begin(), _set_method.end(), _set_method.begin(), ::tolower);
            _stream_method = _method_type[_set_method];
        }

        if(_stream_method==0){ // batch stream mode
            if(param.contains("stream_batch_buffer")){
                _stream_batch_buffer_size = param["stream_batch_buffer"].get<int>();
            }
        }

        //1. initialization
        PylonInitialize();

        //2. find cameras
        CTlFactory& tlFactory = CTlFactory::GetInstance();
        DeviceInfoList_t devices;
        tlFactory.EnumerateDevices(devices);
        if(devices.size()>1)
            logger::info("[{}] Found {} cameras", get_name(), devices.size());

        //3. create device
        for(int idx=0;idx<(int)devices.size();idx++){
            _cameras.insert(make_pair(stoi(devices[idx].GetUserDefinedName().c_str()), 
                            new CBaslerUniversalInstantCamera(tlFactory.CreateDevice(devices[idx]))));
            logger::info("[{}] Found User ID {}, (SN:{}, Address : {})", get_name(), devices[idx].GetUserDefinedName().c_str(), devices[idx].GetSerialNumber().c_str(), devices[idx].GetIpAddress().c_str());
        }

        for(const auto& camera:_cameras){
            thread worker = thread(&basler_gige_cam_grabber::_image_stream_task, this, camera.first, camera.second, get_profile()->parameters());
            _camera_grab_worker[camera.first] = worker.native_handle();
            _camera_grab_counter[camera.first] = 0;
            worker.detach();
        }

        /* camera status ready with default profile */
        json defined_cameras = get_profile()->parameters()["cameras"];
        for(auto& camera:defined_cameras){
            int id = camera["id"].get<int>();
            _camera_status.insert(make_pair(id, camera));
            _camera_status[id]["frames"] = 0;  // add frames (unsigned long long)
            _camera_status[id]["status"] = "-"; // add status (-|working|connected)

            //image container reserve
            // if(_stream_method==0){
            //     _image_container[id].reserve(_stream_batch_buffer_size);
            // }
        }

        // thread monitor = thread(&basler_gige_cam_grabber::_status_monitor_task, this, get_profile()->parameters());

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

    /* camera component status update */
    _publish_status();

}

void basler_gige_cam_grabber::on_close(){

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
    for(auto& camera:_cameras){
        if(camera.second->IsOpen()){
            camera.second->StopGrabbing();
            camera.second->Close();
            delete camera.second;
        }
        
    }

    PylonTerminate();
}

void basler_gige_cam_grabber::on_message(){
    
}

void basler_gige_cam_grabber::_publish_status(){

    /* update the camera working status */
    for(auto& camera:_cameras){
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
        string topic = fmt::format("{}/{}", get_name(), "status");
        pipe_data topic_msg(topic.data(), topic.size());
        pipe_data end_msg(status_message.data(), status_message.size());
        get_port("status")->send(topic_msg, zmq::send_flags::sndmore);
        get_port("status")->send(end_msg, zmq::send_flags::dontwait);

        //logger::info("published the camera status ({})", topic);
    }
    catch(std::runtime_error& e){
        logger::error("{}", e.what());
    }
}

void basler_gige_cam_grabber::_status_monitor_task(json parameters){
    while(!_thread_stop_signal.load()){
        this_thread::sleep_for(chrono::milliseconds(1000));
    }
}

void basler_gige_cam_grabber::_image_stream_task(int camera_id, CBaslerUniversalInstantCamera* camera, json parameters){
    try{
        pthread_setcancelstate(PTHREAD_CANCEL_ENABLE, nullptr);
        pthread_setcanceltype(PTHREAD_CANCEL_DEFERRED, nullptr);

        camera->Open();
        string acqusition_mode = parameters.value("acqusition_mode", "Continuous");
        string trigger_selector = parameters.value("trigger_selector", "FrameStart");
        string trigger_mode = parameters.value("trigger_mode", "On");
        string trigger_source = parameters.value("trigger_source", "Line2");
        string trigger_activation = parameters.value("trigger_activation", "RisingEdge");
        int heartbeat_timeout = parameters.value("heartbeat_timeout", 5000);

        camera->AcquisitionMode.SetValue(acqusition_mode.c_str());
        camera->TriggerSelector.SetValue(trigger_selector.c_str());
        camera->TriggerMode.SetValue(trigger_mode.c_str());
        camera->TriggerSource.SetValue(trigger_source.c_str());
        camera->TriggerActivation.SetValue(trigger_activation.c_str());
        camera->GevHeartbeatTimeout.SetValue(heartbeat_timeout);
        camera->StartGrabbing(Pylon::GrabStrategy_OneByOne, Pylon::GrabLoop_ProvidedByUser);
        CGrabResultPtr ptrGrabResult;

        while(camera->IsGrabbing() && !_thread_stop_signal.load()){
            try{
                camera->RetrieveResult(5000, ptrGrabResult, Pylon::TimeoutHandling_ThrowException); //trigger mode makes it blocked
                if(ptrGrabResult.IsValid()){
                    if(ptrGrabResult->GrabSucceeded()){
                        const uint8_t* pImageBuffer = (uint8_t*)ptrGrabResult->GetBuffer();
                        _camera_grab_counter[camera_id]++;

                        size_t size = ptrGrabResult->GetWidth() * ptrGrabResult->GetHeight() * 1;
                        cv::Mat image(ptrGrabResult->GetHeight(), ptrGrabResult->GetWidth(), CV_8UC1, (void*)pImageBuffer);

                        //jpg encoding
                        std::vector<unsigned char> buffer;
                        cv::imencode(".jpg", image, buffer);

                        //save temporary
                        std::string filename = "image_" + std::to_string(camera_id) + "_" + std::to_string(std::chrono::system_clock::now().time_since_epoch().count()) + ".jpg";
                        cv::imwrite(fmt::format("/home/dk/sddnas/{}",filename), image);

                        // batch stream method
                        if(_stream_method==0){
                            _image_container[camera_id].push_back(buffer);
                        }
                        // realtime stream method with multipart
                        else {

                            //1. image information (camera id, timestamp)
                            auto now = std::chrono::system_clock::now();
                            long long timestamp = chrono::duration_cast<chrono::milliseconds>(now.time_since_epoch()).count();
                            json image_info = {
                                {"camera_id", camera_id},
                                {"timestamp", timestamp}
                            };
                            string image_info_dump = image_info.dump();
                            pipe_data image_info_msg(image_info_dump.size());
                            memcpy(image_info_msg.data(), image_info_dump.c_str(), image_info_dump.size());
                            get_port("image_stream")->send(image_info_msg, zmq::send_flags::sndmore);

                            //2. real image bytearray
                            pipe_data image_data(buffer.data(), buffer.size());
                            get_port("image_stream")->send(image_data, zmq::send_flags::none);
                        }


                        //logger::info("Captured image resolution : {}x{}({})", image.cols, image.rows, image.channels());
                        
                        // image stream monitoring.. publish
                        // set topic
                        string topic = fmt::format("{}", "image_stream_monitor");
                        pipe_data topic_msg(topic.data(), topic.size());

                        // string cid = fmt::format("{}",camera_id);
                        // pipe_data idMessage(cid.size());
                        // memcpy(idMessage.data(), cid.c_str(), cid.size());

                        json cam_id = {{"camera_id", camera_id}};
                        string str_cam_id = cam_id.dump();
                        pipe_data id_message(str_cam_id.size());
                        memcpy(id_message.data(), str_cam_id.c_str(), str_cam_id.size());

                        pipe_data image_message(buffer.size());
                        memcpy(image_message.data(), buffer.data(), buffer.size());

                        get_port("image_stream_monitor")->send(topic_msg, zmq::send_flags::sndmore);
                        get_port("image_stream_monitor")->send(id_message, zmq::send_flags::sndmore);
                        get_port("image_stream_monitor")->send(image_message, zmq::send_flags::dontwait);

                        logger::info("[{}] {}", camera_id, _camera_grab_counter[camera_id]);

                    }
                    else{
                        logger::warn("[{}] Error-code({}) : {}", get_name(), ptrGrabResult->GetErrorCode(), ptrGrabResult->GetErrorDescription().c_str());
                    }
                }
                else
                    break;
            }
            catch(Pylon::TimeoutException& e){
                logger::error("[{}] Camera {} Timeout exception occurred! {}", get_name(), camera_id, e.GetDescription());
                break;
            }
        }

        camera->StopGrabbing();
        camera->Close();
    }
    catch(const GenericException& e){
        logger::error("[{}] {}", get_name(), e.GetDescription());
    }
}
