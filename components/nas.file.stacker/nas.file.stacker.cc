
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

    _mount_path = fs::path(get_profile()->parameters().value("mount_path", ""));
    logger::info("[{}] Mounted NAS Storage Root Path : {}", get_name(), _mount_path.string());

    /* image stream data stacking */
    thread stacking_worker = thread(&nas_file_stacker::_image_stacker, this, get_profile()->parameters());
    _stacker_handle = stacking_worker.native_handle();
    stacking_worker.detach();

    
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
    pthread_cancel(_stacker_handle);
    pthread_join(_stacker_handle, nullptr);
}

void nas_file_stacker::on_message(){
    
}

void nas_file_stacker::_image_stacker(json parameters){

    pthread_setcancelstate(PTHREAD_CANCEL_ENABLE, nullptr);
    pthread_setcanceltype(PTHREAD_CANCEL_DEFERRED, nullptr);

    while(!_thread_stop_signal.load()){
        try{

            /* waiting for lot number from level2 terminal */
            pipe_data lot_info;
            string lot_number = "";
            auto level2_terminal_result = get_port("level2_terminal_out")->recv(lot_info, zmq::recv_flags::none);
            if(level2_terminal_result){
                std::string message(static_cast<char*>(lot_info.data()), lot_info.size());
                auto json_data = json::parse(message);
                if(json_data.contains("LOT")){
                    lot_number = json_data["LOT"].get<string>();
                    _mount_path.append(lot_number);
                    fs::create_directories(_mount_path);
                    logger::info("[{}] Changed NAS Path by LOT Number({}) : {}", get_name(), lot_number, _mount_path.string());
                }
            }


            if(!_mount_path.empty()){
                get_port("image_stream")->set(zmq::sockopt::rcvtimeo, 1000); // 1sec timeout
                while(true){
                    //1. rcv image info
                    pipe_data image_info;
                    auto result = get_port("image_stream")->recv(image_info, zmq::recv_flags::none);
                    if(result){
                        std::string message(static_cast<char*>(image_info.data()), image_info.size());
                        auto json_data = json::parse(message);

                        int camera_id = 0;
                        long long t_stamp = 0;
                        if(json_data.contains("camera_id") & json_data.contains("timestamp")){
                            camera_id = json_data["camera_id"].get<int>();
                            t_stamp = json_data["timestamp"].get<long long>();

                            // rcv image
                            bool more = get_port("image_stream")->get(zmq::sockopt::rcvmore);
                            if(more){
                                pipe_data image;
                                get_port("image_stream")->recv(image, zmq::recv_flags::none);
                                std::vector<uchar> serialized(static_cast<unsigned char*>(image.data()),static_cast<unsigned char*>(image.data()) + image.size());
                                cv::Mat deserialized = cv::imdecode(serialized, cv::IMREAD_GRAYSCALE);
                                if(!deserialized.empty()){
                                    cv::imwrite((_mount_path/fmt::format("{}_{}.jpg", camera_id, t_stamp)).string(), deserialized);
                                }
                            }
                        }
                    }
                    else {
                        // timeout
                        logger::warn("[{}] there is no more data coming into the port.", get_name());
                        _mount_path.clear();
                        break;
                    }
                } //while
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