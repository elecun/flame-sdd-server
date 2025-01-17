
#include "nas.file.stacker.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>
#include <chrono>
#include <sstream>
#include <ctime>
#include <opencv2/opencv.hpp>

using namespace flame;

static nas_file_stacker* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new nas_file_stacker(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool nas_file_stacker::on_init(){

    _mount_path = fs::path(get_profile()->parameters().value("mount_path", ""));
    logger::info("[{}] Mounted NAS Storage Root Path : {}", get_name(), _mount_path.string());

    /* image stream data stacking */
    // thread stacking_worker = thread(&nas_file_stacker::_image_stacker, this, get_profile()->parameters());
    // _stacker_handle = stacking_worker.native_handle();
    // stacking_worker.detach();

    json streams = get_profile()->parameters()["image_streams"];
    for(auto& stream_id:streams){
        int id = stream_id["id"].get<int>();
        thread worker = thread(&nas_file_stacker::_image_stacker, this, id, get_profile()->parameters());
        _stacker_worker[id] = worker.native_handle();
        worker.detach();
        logger::info("[{}] worker #{} detached", get_name(), id);
    }

    return true;
}

void nas_file_stacker::on_loop(){

    // 1. component working status publish

    static int count = 0;
    string topic = "status_out";
    string str_message = fmt::format("{} message {}", topic, count++);
    pipe_data data(str_message.data(), str_message.size());
    if(this->get_port("status_out")){
        this->get_port("status_out")->send(data, zmq::send_flags::none);
    }

}

void nas_file_stacker::on_close(){

    _thread_stop_signal = true;
    pthread_cancel(_stacker_handle);
    pthread_join(_stacker_handle, nullptr);
}

void nas_file_stacker::on_message(){
    
}

void nas_file_stacker::_image_stacker(int id, json parameters){
    try{
        pthread_setcancelstate(PTHREAD_CANCEL_ENABLE, nullptr);
        pthread_setcanceltype(PTHREAD_CANCEL_DEFERRED, nullptr);

        //get_port("image_stream")->set(zmq::sockopt::rcvtimeo, 1000); // 1sec timeout
        string save_dir = parameters["mount_path"].get<string>();
        string port_direction = fmt::format("image_stream_{}",id);
        while(!_thread_stop_signal){

            /* receive data pack from pipeline */
            pipe_data msg_id;
            pipe_data msg_image;

            
            zmq::multipart_t msg_multipart;
            bool ret = msg_multipart.recv(*get_port(port_direction));
            logger::info("[{}] recv from image_stream ({})", get_name(), ret);

            if(ret){
                string camera_id = msg_multipart.popstr();
                zmq::message_t msg_image = msg_multipart.pop();
                vector<unsigned char> image(static_cast<unsigned char*>(msg_image.data()), static_cast<unsigned char*>(msg_image.data())+msg_image.size());

                logger::info("[{}] received image : {}", get_name(), camera_id);

                /* get current time */
                auto now = std::chrono::system_clock::now();
                auto milliseconds = std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()) % 1000;
                time_t now_time = std::chrono::system_clock::to_time_t(now);
                tm local_time = *std::localtime(&now_time);

                /* time formatted filename */
                std::ostringstream oss;
                oss << std::put_time(&local_time, "%Y%m%d_%H%M%S");
                oss << "_" << std::setfill('0') << std::setw(3) << milliseconds.count();

                /* save into directory */
                string filename = fmt::format("{}_{}.jpg", camera_id, oss.str());

                /* decode image & save */
                cv::Mat decoded = cv::imdecode(image, cv::IMREAD_UNCHANGED);                        
                cv::imwrite(fmt::format("{}/{}",save_dir, filename), decoded);

                logger::info("[{}] Saved image : {}", get_name(), filename);
            }
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