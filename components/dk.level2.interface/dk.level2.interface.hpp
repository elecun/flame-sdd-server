/**
 * @file dk.level2.interface.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief DK Level2 Data Interface component
 * @version 0.1
 * @date 2024-06-30
 * 
 * @copyright Copyright (c) 2024
 * 
 */

#ifndef FLAME_DK_LEVEL2_INTERFACE_HPP_INCLUDED
#define FLAME_DK_LEVEL2_INTERFACE_HPP_INCLUDED

#include <flame/component/object.hpp>
#include <iostream>
#include "protocol.hpp"
#include <memory>

#include "tcpsocket.hpp"
#include "tcpserver.hpp"
#include "concurrent_queue.hpp"

using namespace std;
// using namespace boost;

class dk_level2_interface : public flame::component::object {
    public:
        dk_level2_interface() = default;
        virtual ~dk_level2_interface() = default;

        /* common interface functions */
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        atomic<bool> _show_raw_packet {false}; /* if true, show packet via logger*/
        int _alive_interval {1000}; /* alive packet send interval */

    private:
        /* worker */
        thread _client_worker;
        thread _server_worker;
        atomic<bool> _worker_stop {false};
        concurrent_queue<dk_sdd_alarm> _sdd_alarm_queue;
        concurrent_queue<dk_sdd_job_result> _sdd_job_result_queue;

        /* worker callback functions */
        void _do_client_work(json parameters);
        void _do_server_work(json parameters);

    private:
        /* useful functions */
        string get_current_time();                      /* return localtime to string */
        void show_raw_packet(char* data, size_t size);  /* show raw packet data */
        string remove_space(const char* in, int size);
        dk_h_standard_dim extract_stand_dim(const char* in, int size); /* extract lot no. from packet */
        std::vector<std::string> split(const std::string& str, const std::string& delimiters);

        /* packet generation */
        dk_sdd_alive generate_packet_alive(bool show = false);
        dk_sdd_alarm generate_packet_alarm(string alarm_code, bool show = false);
        dk_sdd_job_result generate_packet_job_result(string lot_no, string mt_no, string mt_type_cd, string mt_stand, vector<dk_sdd_defect> defect_list, bool show = false);

        /* status udpate */
        void publish_status(bool lv2_connect);

    private:
        string _lv2_access_ip {"127.0.0.1"};
        int _lv2_access_port;
        string _sdd_host_ip {"127.0.0.1"} ;
        int _sdd_host_port;


}; /* class */

EXPORT_COMPONENT_API


#endif