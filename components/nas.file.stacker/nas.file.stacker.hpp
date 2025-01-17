/**
 * @file nas.file.stacker.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief File Stacker for Synology NAS Device
 * @version 0.1
 * @date 2024-06-30
 * 
 * @copyright Copyright (c) 2024
 * 
 */

#ifndef FLAME_NAS_FILE_STACKER_HPP_INCLUDED
#define FLAME_NAS_FILE_STACKER_HPP_INCLUDED

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

class nas_file_stacker : public flame::component::object {
    public:
        nas_file_stacker() = default;
        virtual ~nas_file_stacker() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        void _image_stacker(json parameters); /* realtime image data stacker thread callback */
        void _response(json paramters);


    private:
        pthread_t _stacker_handle;
        
        bool _thread_stop_signal { false };
        fs::path _mount_path;
        fs::path _destination_path;


}; /* class */

EXPORT_COMPONENT_API


#endif