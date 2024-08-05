
#include "image.flow.handler.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>

using namespace flame;
using namespace cv;
namespace fs = std::filesystem;

static image_flow_handler* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new image_flow_handler(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool image_flow_handler::on_init(){

    /* create & run image puller thread */
    thread puller = thread(&image_flow_handler::_image_puller, this, get_profile()->parameters());
    _stream_puller_handle = puller.native_handle();
    puller.detach();

    
    return true;
}

void image_flow_handler::on_loop(){

}

void image_flow_handler::on_close(){

    /* cancel the stream puller thread */
    _thread_stop_signal.store(true);
    pthread_cancel(_stream_puller_handle);
    pthread_join(_stream_puller_handle, nullptr);

}

void image_flow_handler::on_message(){
    
}

void image_flow_handler::_image_puller(json parameters){

    pthread_setcancelstate(PTHREAD_CANCEL_ENABLE, nullptr);
    pthread_setcanceltype(PTHREAD_CANCEL_DEFERRED, nullptr);

    while(!_thread_stop_signal.load()){
        try {
            pipe_data recv_info;
            pipe_data recv_data;

            zmq::recv_result_t data_info = get_port("image_stream")->recv(recv_info, zmq::recv_flags::none);
            string info(static_cast<char*>(recv_info.data()), recv_info.size());
            auto json_info = json::parse(info);

            zmq::recv_result_t data = get_port("image_stream")->recv(recv_data, zmq::recv_flags::none);
            vector<uint8_t> encoded_image(recv_data.size());
            std::memcpy(encoded_image.data(), recv_data.data(), recv_data.size());

            /* push data into the container */
            _image_container.push(std::move(encoded_image));

            logger::info("Container size : {}", _image_container.size());

        }
        catch(const json::parse_error& e){
            logger::error("[{}] message cannot be parsed. {}", get_name(), e.what());
        }
        catch(const std::runtime_error& e){
            logger::error("[{}] Runtime error occurred!", get_name());
        }
    }

}