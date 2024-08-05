
#include "nas.file.stacker.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>
#include <chrono>
#include <opencv2/opencv.hpp>

using namespace flame;

static nas_file_stacker* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new nas_file_stacker(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool nas_file_stacker::on_init(){

    fs::path save_path = fs::path(get_profile()->parameters().value("save_root", "/mnt/sddnas"));
    logger::info("[{}] Mounted NAS Storage : {}", get_name(), save_path.string());

    _thread_image_stream = new thread(&nas_file_stacker::_subscribe_image_stream_task, this);
    
    //connect
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
    _thread_stop_signal.store(true);
    _thread_image_stream->join();

    if(_thread_image_stream)
        delete _thread_image_stream;
}

void nas_file_stacker::on_message(){
    
}


void nas_file_stacker::_subscribe_image_stream_task()
{
    while(!_thread_stop_signal.load()){
        
        // 1. receive data
        pipe_data msg;
        auto result = this->get_port("image_stream")->recv(msg, zmq::recv_flags::dontwait);
        static int count = 0;

        if(result){
            std::vector<uchar> serialized(static_cast<unsigned char*>(msg.data()),static_cast<unsigned char*>(msg.data()) + msg.size());

            cv::Mat deserialized = cv::imdecode(serialized, cv::IMREAD_GRAYSCALE);
            if(!deserialized.empty()){
                fs::path _save = _save_root / fmt::format("test_{}.jpg", count++);
                cv::imwrite(_save.string(), deserialized);
            }
        }
        else {
            this_thread::sleep_for(chrono::milliseconds(200));
        }

    }
}