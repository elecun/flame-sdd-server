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
#include <boost/asio.hpp>
#include "protocol.hpp"
#include <memory>
#include "tcp.hpp"

using namespace std;
using namespace boost;
using namespace boost::asio::ip;
using namespace boost::system;

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
        asio::io_context _io_context;
        unique_ptr<tcp_client> _tcp_client;
        unique_ptr<tcp_server> _tcp_server;

        /* local vairables */
        int _alive_interval {1};
        atomic<bool> _show_raw_packet {false};

    private:
        void on_server_connected(const tcp::endpoint& endpoint);
        void on_server_disconnected(const tcp::endpoint& endpoint);
        void on_server_received(const std::string& data);

    private:
        /* useful functions */
        string get_current_time();                      /* return localtime to string */
        void show_raw_packet(char* data, size_t size);  /* show raw packet data */

        /* packet generation */
        dk_sdd_alive generate_packet_alive();
        dk_sdd_alarm generate_packet_alarm();
        dk_sdd_job_result generate_packet_job_result();

    private:
        boost::asio::io_context _io_context;

        string lv2_access_ip {"127.0.0.1"};
        int lv2_access_port;
        string sdd_host_ip {"127.0.0.1"} ;
        int sdd_host_port;

    private:
        vector<thread> _worker_container;
        atomic<bool> _worker_stop {false};


}; /* class */

EXPORT_COMPONENT_API


#endif