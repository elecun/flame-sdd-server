
#include "dummy.image.pusher.hpp"
#include <flame/log.hpp>
#include <chrono>
#include <sstream>
#include <ctime>
#include <opencv2/opencv.hpp>
#include <fstream>

using namespace flame;

static dummy_image_pusher* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new dummy_image_pusher(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool dummy_image_pusher::on_init(){

    /* get parameters from profile */
    json parameters = get_profile()->parameters();

    /* image pusher worker */
    fs::path working_dir = fs::path(parameters["sample_path"]);
    if(parameters.contains("image_streams") && parameters["image_streams"].is_array()){
        json image_streams = parameters["image_streams"];

        for(const auto& stream:image_streams){
            int stream_id = stream["id"].get<int>();
            fs::path sample_path = working_dir / stream["sample"].get<string>();
            string pipename = stream["pipename"].get<string>();
            _push_worker[stream_id] = thread(&dummy_image_pusher::_image_push_task, this, stream_id, pipename, sample_path.string());
            logger::info("[{}] Stream #{} pusher is running...", get_name(), stream_id);
        }
    }

    logger::info("[{}] File Pusher is now running...", get_name());

    return true;
}

void dummy_image_pusher::on_loop(){

}

void dummy_image_pusher::on_close(){

    /* work stop signal */
    _worker_stop.store(true);

    /* wait for stopping workers */
    for_each(_push_worker.begin(), _push_worker.end(), [](auto& t) {
        if(t.second.joinable()){
            t.second.join();
            logger::info("Image File Pusher #{} is now stopped", t.first);
        }
    });

    /* clear */
    _push_worker.clear();
}

void dummy_image_pusher::on_message(const component::message_t& msg){
    
}

void dummy_image_pusher::_image_push_task(int stream_id, const string pipename, const string sample_image){
    try{

        while(!_worker_stop.load()){

            //load image with opencv
            cv::Mat image = cv::imread(sample_image, cv::IMREAD_UNCHANGED);

            if(!image.empty()){
                std::vector<unsigned char> serialized_image;
                cv::imencode(".jpg", image, serialized_image);

                string id_str = fmt::format("{}",stream_id);

                pipe_data msg_id(id_str.data(), id_str.size());
                pipe_data msg_image(serialized_image.data(), serialized_image.size());

                string image_stream_port = fmt::format("image_stream_{}", stream_id);
                if(get_port(image_stream_port)->handle()!=nullptr){
                    zmq::multipart_t msg_multipart_image;
                    msg_multipart_image.addstr(id_str);
                    msg_multipart_image.addmem(serialized_image.data(), serialized_image.size());
                    msg_multipart_image.send(*get_port(image_stream_port), ZMQ_DONTWAIT);
                }
                else{
                    logger::warn("[{}] {} socket handle is not valid ", get_name(), stream_id);
                }
            }

            std::this_thread::sleep_for(std::chrono::milliseconds(1000));
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

