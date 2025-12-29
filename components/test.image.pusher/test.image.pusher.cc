
#include "test.image.pusher.hpp"
#include <flame/log.hpp>
#include <opencv2/opencv.hpp>
#include <chrono>

using namespace flame;
using namespace std;
using namespace cv;

/* create component instance */
static test_image_pusher* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new test_image_pusher(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}


bool test_image_pusher::on_init(){

    try{

        /* get parameters from profile */
        json parameters = get_profile()->parameters();

        /* device control handle assign for each camera */
        for(int i=0;i<10;i++){
            _camera_grab_worker[i+1] = thread(&test_image_pusher::_image_stream_task, this, i+1, get_profile()->parameters());
            logger::info("[{}] Camera #{} Grabber is running...", get_name(), i+1);
        }

        /* image stream control worker */
        _image_stream_enable.store(true);


    }
    catch(json::exception& e){
        logger::error("Profile Error : {}", e.what());
        return false;
    }

    return true;
}

void test_image_pusher::on_loop(){

    

}


void test_image_pusher::on_close(){


    /* work stop signal */
    _image_stream_enable.store(false);
    _worker_stop.store(true);


    /* stop camera grab workers */
    for_each(_camera_grab_worker.begin(), _camera_grab_worker.end(), [](auto& t) {
        if(t.second.joinable()){
            t.second.join();
            logger::info("- Camera #{} Grabber is now stopped", t.first);
        }
    });

    _camera_grab_worker.clear();


}

void test_image_pusher::on_message(const component::message_t& msg){
    
}


void test_image_pusher::_image_stream_task(int camera_id, json parameters){

    //load image with opencv
    cv::Mat image = cv::imread("test.jpg", cv::IMREAD_UNCHANGED);
    int max = 10000;
    int n = 0;

    while(!_worker_stop.load()){
        try{

            if(!image.empty()){
                //jpg encoding
                std::vector<unsigned char> serialized_image;
                cv::imencode(".jpg", image, serialized_image);

                /* common transport parameters */
                string id_str = fmt::format("{}",camera_id);

                /* push image data */
                if(_image_stream_enable.load()){

                    // pipe_data msg_id(id_str.data(), id_str.size());
                    // pipe_data msg_image(serialized_image.data(), serialized_image.size());

                    if(n<max){

                        string image_stream_port = fmt::format("image_stream_{}", camera_id);
                        if(get_port(image_stream_port)->handle()!=nullptr){
                            zmq::multipart_t msg_multipart_image;
                            msg_multipart_image.addstr(id_str);
                            msg_multipart_image.addmem(serialized_image.data(), serialized_image.size());
                            bool sent = msg_multipart_image.send(*get_port(image_stream_port), ZMQ_DONTWAIT);
                            if (!sent) {
                                logger::warn("[{}] Failed to send image for camera {}", get_name(), camera_id);
                            }
                            else {
                                logger::info("({}) send message for camera {}", n, camera_id);
                            }
                            msg_multipart_image.clear();
                        }
                        else{
                            logger::warn("[{}] {} socket handle is not valid ", get_name(), camera_id);
                        }
                        std::this_thread::sleep_for(std::chrono::milliseconds(33));
                    }
                    else {
                        n=0;
                        std::this_thread::sleep_for(std::chrono::milliseconds(15000));
                    }
                    n++;
                }

                serialized_image.clear();
            }
            else {
                logger::warn("Cannot load image");
            }

        }
        catch(const zmq::error_t& e){
            logger::error("[{}] {}", get_name(), e.what());
            break;
        }
    }
    
}
