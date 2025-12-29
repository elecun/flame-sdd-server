/**
 * @file general.file.stacker.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief General File Staker into Multi Directory
 * @version 0.1
 * @date 2025-05-12
 * 
 * @copyright Copyright (c) 2025
 * 
 */

#ifndef FLAME_GENERAL_FILE_STACKER_HPP_INCLUDED
#define FLAME_GENERAL_FILE_STACKER_HPP_INCLUDED

#include <flame/component/object.hpp>
#include <thread>
#include <string>
#include <unordered_map>
#include <queue>
#include <mutex>
#include <vector>
#include <filesystem>

using namespace std;
namespace fs = std::filesystem;

class general_file_stacker : public flame::component::object {
    public:
        general_file_stacker() = default;
        virtual ~general_file_stacker() = default;

        /* common interface function */
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message(const component::message_t& msg) override;

    private:
        /* worker */
        unordered_map<int, thread> _stacker_worker; // (stream id, thread)
        atomic<bool> _worker_stop {false};
        atomic<bool> _new_instruction {false}; // if new instruction is comming from lv2, should be set true
        unordered_map<int, atomic<bool>> _timeout_flag; // timeout flag for each image stream
        unordered_map<int, unsigned long> _stream_counter;
        thread _level2_dispatch_worker; //level2 data interface

        /* working(save) directory name (by lv2 interface) */
        vector<fs::path> _backup_dir_path; // image path for each stream
        

    private:
        /* subtasks */
        void _image_stacker_task(int stream_id, json stream_param);
        void _image_stacker_task_opt(int stream_id, json stream_param);
        void _level2_dispatch_task(json target_path);

}; /* class */

EXPORT_COMPONENT_API


#endif