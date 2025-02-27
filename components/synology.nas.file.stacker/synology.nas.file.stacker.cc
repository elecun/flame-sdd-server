
#include "synology.nas.file.stacker.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>
#include <chrono>
#include <sstream>
#include <ctime>
#include <opencv2/opencv.hpp>

using namespace flame;

static synology_nas_file_stacker* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new synology_nas_file_stacker(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool synology_nas_file_stacker::on_init(){

    /* get parameters from profile */
    json parameters = get_profile()->parameters();

    /* get mount path from profile */
    string mount_path {""};
    if(parameters.contains("mount_path")){
        mount_path = parameters.value("mount_path", "");
        logger::info("[{}] Mounted NAS Storage Root Path : {}", get_name(), mount_path);
    }
    else {
        logger::error("[{}] Mount path is not defined. It must be required to store images.", get_name());
    }

    /* image stacker worker */
    if(parameters.contains("image_streams") && parameters["image_streams"].is_array()){
        json image_streams = parameters["image_streams"];

        for(const auto& stream:image_streams){
            int stream_id = stream["id"].get<int>();
            _timeout_flag.emplace(stream_id, false);
            _stacker_worker[stream_id] = thread(&synology_nas_file_stacker::_image_stacker_task, this, stream_id, mount_path, stream);
            logger::info("[{}] Stream #{} stacker is running...", get_name(), stream_id);
        }
    }

    /* level2 interface worker */
    if(parameters.contains("use_level2_interface")){
        bool enable = parameters.value("use_level2_interface", false);
        if(enable){
            _level2_dispatch_worker = thread(&synology_nas_file_stacker::_level2_dispatch_task, this);
            logger::info("[{}] Level2 Data interface is running...", get_name());
        }
    }

    return true;
}

void synology_nas_file_stacker::on_loop(){

}

void synology_nas_file_stacker::on_close(){

    /* work stop signal */
    _worker_stop.store(true);

    /* wait for stopping workers */
    for_each(_stacker_worker.begin(), _stacker_worker.end(), [](auto& t) {
        if(t.second.joinable()){
            t.second.join();
            logger::info("- File Stacker #{} is now stopped", t.first);
        }
    });

    if(_level2_dispatch_worker.joinable()){
        _level2_dispatch_worker.join();
        logger::info("[{}] Level2 Interface Data dispatcher is now stopped", get_name());
    }

    /* clear */
    _stacker_worker.clear();
}

void synology_nas_file_stacker::on_message(){
    
}


void synology_nas_file_stacker::_image_stacker_task(int stream_id, string root, json stream_param)
{
    try{
        string portname = fmt::format("image_stream_{}", stream_id);
        fs::path root_path = fs::path(root);
        fs::path temp_save_path = root_path / "tmp";// / get_current_time() / stream_param["dirname"].get<string>();
        unsigned long stream_counter = 0;

        string working_dirname = stream_param.value("dirname", fmt::format("tmp_{}", stream_id));

        while(!_worker_stop.load()){
            try{

                /* recv stream data */
                zmq::multipart_t msg_multipart;
                bool success = msg_multipart.recv(*get_port(portname));

                if(success){
                    
                    /* renew save path */
                    if(_timeout_flag[stream_id].load()){
                        string working_tmp_job_path = get_current_time();
                        temp_save_path = root_path / working_tmp_job_path / working_dirname;
                        if(!fs::exists(temp_save_path)){
                            fs::create_directories(temp_save_path);
                            logger::info("[{}] Stream #{} data saves into {}", get_name(), stream_id, temp_save_path.string());
                        }
                        /* timeout flag set false */
                        _timeout_flag[stream_id].store(false);

                        /* counter reset */
                        stream_counter = 0;
                    }

                    /* pop 2 data chunk from message */
                    string camera_id = msg_multipart.popstr();
                    zmq::message_t msg_image = msg_multipart.pop();
                    vector<unsigned char> image(static_cast<unsigned char*>(msg_image.data()), static_cast<unsigned char*>(msg_image.data())+msg_image.size());

                    /* decode image & save */
                    cv::Mat decoded = cv::imdecode(image, cv::IMREAD_UNCHANGED);                        
                    string filename = fmt::format("{}_{}.jpg", camera_id, ++stream_counter);
                    cv::imwrite(fmt::format("{}/{}",temp_save_path.string(), filename), decoded);
                }
                else {
                    /* set timeout flag true (timeout value set to profile )*/
                    if(!_timeout_flag[stream_id].load()){
                        _timeout_flag[stream_id].store(true);

                        try{
                            if(!_renamed_target_dirname.empty()){
                                fs::path dest = root_path / _renamed_target_dirname;
                                if(!fs::exists(dest)){
                                    fs::create_directories(dest);
                                }
                                fs::rename(temp_save_path, dest/working_dirname);
                                logger::info("[{}] Rename target dir name with LOT No. {}", get_name(), _renamed_target_dirname);
                            }
                            else {
                                logger::warn("[{}] No target directory name to replace the temporary dir.", get_name());
                            }
                        }
                        catch(const fs::filesystem_error& e){
                            logger::error("[{}] File rename error : {}", get_name(), e.what());
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

void synology_nas_file_stacker::_level2_dispatch_task(){
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
                    if(json_data.contains("lot_no")){
                        _renamed_target_dirname = json_data["lot_no"].get<string>();
                        logger::info("[{}] Set Dir name to {} later", get_name(), _renamed_target_dirname);
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

string synology_nas_file_stacker::get_current_time(){

    /* get current local time */
    auto now = std::chrono::system_clock::now();
    auto milliseconds = std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()) % 1000;
    time_t now_time = std::chrono::system_clock::to_time_t(now);
    tm local_time = *std::localtime(&now_time);

    /* time to string */
    std::stringstream ss_time;
    ss_time << std::put_time(&local_time, "%Y%m%d%H%M%S");
    // ss_time << "_" << std::setfill('0') << std::setw(3) << milliseconds.count();

    return ss_time.str();
}
