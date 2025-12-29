
#include "general.file.stacker.hpp"
#include <flame/log.hpp>
#include <chrono>
#include <sstream>
#include <ctime>
#include <opencv2/opencv.hpp>
#include <fstream>

using namespace flame;

static general_file_stacker* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new general_file_stacker(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool general_file_stacker::on_init(){

    /* get parameters from profile */
    json parameters = get_profile()->parameters();

    json target_path = parameters["target_path"];


    /* image stacker worker */
    if(parameters.contains("image_streams") && parameters["image_streams"].is_array()){
        json image_streams = parameters["image_streams"];

        for(const auto& stream:image_streams){
            int stream_id = stream["id"].get<int>();
            _timeout_flag.emplace(stream_id, false);
            _stacker_worker[stream_id] = thread(&general_file_stacker::_image_stacker_task_opt, this, stream_id, stream);
            logger::info("[{}] Stream #{} stacker is running...", get_name(), stream_id);
            
            /* set stream counter */
            _stream_counter[stream_id] = 0;
        }
    }

    /* level2 interface worker */
    if(parameters.contains("use_level2_interface")){
        bool enable = parameters.value("use_level2_interface", false);
        if(enable){
            _level2_dispatch_worker = thread(&general_file_stacker::_level2_dispatch_task, this, target_path);
            logger::info("[{}] Level2 Data interface is running...", get_name());
        }
        else{
            logger::debug("[{}] Level2 Data interface is not running...", get_name());
        }
    }
    else{
        logger::debug("[{}] Level2 Data interface has no use_level2_interface...", get_name());
    }

    logger::info("[{}] File Stacker is now running...", get_name());

    return true;
}

void general_file_stacker::on_loop(){

}

void general_file_stacker::on_close(){

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

void general_file_stacker::on_message(const component::message_t& msg){
    
}


void general_file_stacker::_image_stacker_task_opt(int stream_id, json stream_param){
    try{
        string portname = fmt::format("image_stream_{}", stream_id);
        string working_dirname = stream_param.value("dirname", fmt::format("tmp_{}", stream_id));

        while(!_worker_stop.load()){
            try{

                /* recv stream data */
                zmq::multipart_t msg_multipart;
                bool success = msg_multipart.recv(*get_port(portname));

                /* received success */
                if(success){

                    /* pop 2 data chunk from message */
                    string camera_id = msg_multipart.popstr();
                    zmq::message_t msg_image = msg_multipart.pop();
                    string filename = fmt::format("{}_{}.jpg", camera_id, ++_stream_counter[stream_id]);

                    /* save into multiple directories (camera_*)*/
                    for(auto& path:_backup_dir_path){
                        fs::path camera_working_dir = path / working_dirname;
                        if(!fs::exists(camera_working_dir)){
                            fs::create_directories(camera_working_dir);
                            logger::info("[{}] Stream #{} data saves into {}", get_name(), stream_id, camera_working_dir.string());
                        }

                        std::ofstream out(fmt::format("{}/{}", camera_working_dir.string(), filename), std::ios::binary);
                        out.write(static_cast<char*>(msg_image.data()), msg_image.size());
                        out.close();
                    }

                    // release explicit
                    msg_image = zmq::message_t();
                    msg_multipart.clear();
                }
            }
            catch(const zmq::error_t& e){
                logger::error("[{}] stacking pipeline error {}", get_name(), e.what());
            }
            catch(std::exception& e){
                logger::error("[{}] stacking general error {}", get_name(), e.what());
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

void general_file_stacker::_image_stacker_task(int stream_id, json stream_param)
{
    try{
        string portname = fmt::format("image_stream_{}", stream_id);
        string working_dirname = stream_param.value("dirname", fmt::format("tmp_{}", stream_id));

        while(!_worker_stop.load()){
            try{

                /* recv stream data */
                zmq::multipart_t msg_multipart;
                bool success = msg_multipart.recv(*get_port(portname));

                /* received success */
                if(success){

                    /* pop 2 data chunk from message */
                    string camera_id = msg_multipart.popstr();
                    zmq::message_t msg_image = msg_multipart.pop();
                    vector<unsigned char> image(static_cast<unsigned char*>(msg_image.data()), static_cast<unsigned char*>(msg_image.data())+msg_image.size());

                    /* decode image & save */
                    cv::Mat decoded = cv::imdecode(image, cv::IMREAD_UNCHANGED);                        
                    string filename = fmt::format("{}_{}.jpg", camera_id, ++_stream_counter[stream_id]);

                    /* save into multiple directories (camera_*)*/
                    for(auto& path:_backup_dir_path){
                        fs::path camera_working_dir = path / working_dirname;
                        if(!fs::exists(camera_working_dir)){
                            fs::create_directories(camera_working_dir);
                            logger::info("[{}] Stream #{} data saves into {}", get_name(), stream_id, camera_working_dir.string());
                        }

                        cv::imwrite(fmt::format("{}/{}",camera_working_dir.string(), filename), decoded);
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

void general_file_stacker::_level2_dispatch_task(json target_path){
    try{
        string target_dirname {""};

        while(!_worker_stop.load()){
            try{
                zmq::multipart_t msg_multipart;
                bool success = msg_multipart.recv(*get_port("lv2_dispatch"));

                /* if level2 data comes from level2 */
                if(success){
                    _backup_dir_path.clear(); // clear previous backup dir path

                    string topic = msg_multipart.popstr();
                    string data = msg_multipart.popstr();
                    auto json_data = json::parse(data);

                    /* generate target dir & name */
                    if(json_data.contains("date") && json_data.contains("mt_stand_height") and json_data.contains("mt_stand_width")){
                        string date = json_data["date"].get<string>().substr(0, 8);
                        target_dirname = fmt::format("{}_{}x{}",json_data["date"].get<string>(),
                                                                int(json_data["mt_stand_width"].get<int>()/10),
                                                                int(json_data["mt_stand_height"].get<int>()/10));

                        /* create directory & save level2 info (if backup only)*/
                        for(const auto& target:target_path){
                            try{
                                fs::path dest = fs::path(target.value("path", "/tmp")) / date / target_dirname;
                                if(target.value("use",false)){
                                    if(!fs::exists(dest)){
                                        fs::create_directories(dest);
                                        _backup_dir_path.push_back(dest);
                                        logger::info("[{}] Created destination directory : {}", get_name(), dest.string());

                                        /* save level2 info */
                                        if(!target.value("image_only", false)){
                                            string lv2_path = fmt::format("{}/level2.txt", dest.string());
                                            ofstream lv2_file(lv2_path);
                                            if(lv2_file.is_open()){
                                                lv2_file << "date : " << json_data["date"].get<string>() << endl;
                                                lv2_file << "lot_no : " << json_data["lot_no"].get<string>() << endl;
                                                lv2_file << "mt_no : " << json_data["mt_no"].get<string>() << endl;
                                                lv2_file << "mt_stand : " << json_data["mt_stand"].get<string>() << endl;
                                                lv2_file << "mt_stand_height : " << json_data["mt_stand_height"].get<int>() << endl;
                                                lv2_file << "mt_stand_width : " << json_data["mt_stand_width"].get<int>() << endl;
                                                lv2_file << "mt_stand_t1 : " << json_data["mt_stand_t1"].get<int>() << endl;
                                                lv2_file << "mt_stand_t2 : " << json_data["mt_stand_t2"].get<int>() << endl;
                                                lv2_file << "fm_length : " << json_data["fm_length"].get<long>() << endl;
                                                lv2_file << "fm_speed : " << json_data["fm_speed"].get<int>() << endl;
                                                lv2_file.flush();
                                                lv2_file.close();
                                                logger::info("[{}] Saved level2 info file : {}", get_name(), lv2_path);
                                            }
                                        }
                                    }
                                }

                            }
                            catch(const std::exception& e){
                                logger::error("[{}] Standard Exception : {}", get_name(), e.what());
                            }
                            catch(const fs::filesystem_error& e){
                                logger::error("[{}] Create directory error : {}", get_name(), e.what());
                            }
                            catch(const json::parse_error& e){
                                logger::error("[{}] message cannot be parsed. {}", get_name(), e.what());
                            }
                        }

                        /* stream counter reset */
                        for(auto it=_stream_counter.begin(); it!=_stream_counter.end(); ++it){
                            it->second = 0;
                            logger::debug("[{}] Stream #{} counter reset to 0", get_name(), it->first);
                        }
                    }
                    else{
                        logger::warn("[{}] missed parameters to set target directory name.", get_name());
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
