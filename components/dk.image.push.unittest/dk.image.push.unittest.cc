
#include "dk.image.push.unittest.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>

#include <opencv2/opencv.hpp>
#include <filesystem>

using namespace flame;
using namespace cv;
namespace fs = std::filesystem;

static dk_image_push_unittest* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new dk_image_push_unittest(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool dk_image_push_unittest::on_init(){

    try {

        // get image path
        fs::path current_path = fs::current_path();
        string dirname = get_profile()->raw()["parameters"]["dirname"].get<string>();
        fs::path _image_path = current_path / fs::path(dirname);

        //find images
        for(const auto& entry : fs::directory_iterator(_image_path)){
            if(entry.is_regular_file() && entry.path().extension()==".PNG"){
                _files.emplace_back(entry.path().string());
                logger::info("file : {}", entry.path().string());
            }
        }

        // load image
        for(const auto& file:_files){
            _container.emplace_back(cv::imread(file, IMREAD_GRAYSCALE));
        }

        //zmq context
        _context = new zmq::context_t(1);
        _socket = new zmq::socket_t(*_context, ZMQ_PUB);
        _socket->bind("tcp://*:5555");
        
    }
    catch (const fs::filesystem_error& e){
        logger::error("{}", e.what());
    }
    
    return true;
}

void dk_image_push_unittest::on_loop(){

    string topic = "image_bus";
    static int count = 0;
    for(auto& image:_container){

        vector<uchar> buffer;
        imencode(".jpg", image, buffer);

        zmq::message_t topic_msg(topic.size());
        memcpy(topic_msg.data(), topic.data(), topic.size());
        _socket->send(topic_msg, zmq::send_flags::sndmore);

        zmq::message_t message(buffer.size());
        memcpy(message.data(), buffer.data(), buffer.size());
        _socket->send(message);

        logger::info("Sent data {} bytes ({})", buffer.size(), count++);
    }
}

void dk_image_push_unittest::on_close(){
    
    _socket->close();
    _context->close();

    for(auto& image:_container){
        image.release();
    }
}

void dk_image_push_unittest::on_message(){
    
}
