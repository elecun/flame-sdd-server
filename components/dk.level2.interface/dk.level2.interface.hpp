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
        /* tcp client & server */
        tcp_socket<> _tcp_client { nullptr };
        tcp_server<> _tcp_server { nullptr };

        /* optional */
        atomic<bool> _show_raw_packet {false};
        
    private:

        /* local vairables */
        int _alive_interval {1};
        

    private:
        // /* server callback */
        // static void on_server_connected(const tcp::endpoint& endpoint);
        // static void on_server_disconnected(const tcp::endpoint& endpoint);
        // static void on_server_received(const std::string& data);

        // /* client callback */
        // static void on_client_connected(const tcp::endpoint& endpoint);
        // static void on_client_disconnected(const tcp::endpoint& endpoint);
        // static void on_client_received(const std::string& data);

        /* worker */
        thread _client_worker;
        thread _server_worker;
        atomic<bool> _worker_stop {false};
        concurrent_queue<dk_sdd_alarm> _sdd_alarm_queue;
        concurrent_queue<dk_sdd_job_result> _sdd_job_result_queue;

        void _do_client_work(json parameters);
        void _do_server_work(json parameters);

    private:
        /* useful functions */
        string get_current_time();                      /* return localtime to string */
        void show_raw_packet(char* data, size_t size);  /* show raw packet data */

        /* packet generation */
        dk_sdd_alive generate_packet_alive();
        dk_sdd_alarm generate_packet_alarm(string alarm_code);
        dk_sdd_job_result generate_packet_job_result(string lot_no, string mt_no, string mt_type_cd, string mt_stand, vector<dk_sdd_defect>* defect_list);

    private:
        string lv2_access_ip {"127.0.0.1"};
        int lv2_access_port;
        string sdd_host_ip {"127.0.0.1"} ;
        int sdd_host_port;


}; /* class */

EXPORT_COMPONENT_API


#endif