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
#include <unordered_map>
#include <queue>
#include <mutex>
#include <filesystem>

using namespace std;
namespace fs = std::filesystem;

class synology_nas_file_stacker : public flame::component::object {
    public:
        synology_nas_file_stacker() = default;
        virtual ~synology_nas_file_stacker() = default;

        /* common interface function */
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        /* worker */
        unordered_map<int, thread> _stacker_worker; // (stream id, thread)
        atomic<bool> _worker_stop {false};
        atomic<bool> _new_instruction {false}; // if new instruction is comming from lv2, should be set true
        unordered_map<int, atomic<bool>> _timeout_flag; // timeout flag for each image stream
        unordered_map<int, unsigned long> _stream_counter;
        thread _level2_dispatch_worker; //level2 data interface

        /* working(save) directory name (by lv2 interface) */
        // string _target_dirname {""}; //date + dimension
        string _mount_path {""}; //mount abs. path
        fs::path _job_path; //target full path (without stream id)

    private:
        /* subtasks */
        void _image_stacker_task(int stream_id, string mount_path, json stream_param);
        void _level2_dispatch_task(string mount_path);

        /* useful functions */
        string get_current_time();


}; /* class */

EXPORT_COMPONENT_API


#endif