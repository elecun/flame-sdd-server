/**
 * @file synology.nas.file.stacker.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief File Stacker for Synology NAS Device
 * @version 0.1
 * @date 2024-06-30
 * 
 * @copyright Copyright (c) 2024
 * 
 */

#ifndef FLAME_SYNOLOGY_NAS_FILE_STACKER_HPP_INCLUDED
#define FLAME_SYNOLOGY_NAS_FILE_STACKER_HPP_INCLUDED

#include <flame/component/object.hpp>
#include <thread>
#include <string>
#include <condition_variable>
#include <unordered_map>
#include <queue>
#include <mutex>
#include <flame/component/port.hpp>
#include <atomic>
#include <filesystem>

using namespace std;
namespace fs = std::filesystem;

class synology_nas_file_stacker : public flame::component::object {
    public:
        nas_file_stacker() = default;
        virtual ~nas_file_stacker() = default;

        /* common interface function */
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        /* worker */
        unordered_map<int, thread> _stacker_worker; // (stream id, thread)
        atomic<bool> _worker_stop {false};

    private:
        void _image_stacker_task(int stream_id, json param);



    private:
        void _image_stacker(int id, json parameters); /* realtime image data stacker thread callback */
        void _response(json paramters);


    private:
        pthread_t _stacker_handle;
        unordered_map<int, pthread_t> _stacker_worker;  // image stream id, stacker thread
        
        bool _thread_stop_signal { false };
        fs::path _mount_path;
        fs::path _destination_path;


}; /* class */

EXPORT_COMPONENT_API


#endif