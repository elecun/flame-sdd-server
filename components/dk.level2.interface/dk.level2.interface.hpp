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

using namespace std;
using namespace boost::asio::ip;

class dk_level2_interface : public flame::component::object {
    public:
        dk_level2_interface() = default;
        virtual ~dk_level2_interface() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        void _server_proc();

    private:
        boost::asio::io_context _io_context;

        string lv2_access_ip;
        int lv2_access_port;
        string sdd_host_ip;
        int sdd_host_port;

    private:
        vector<thread> _worker_container;
        atomic<bool> _worker_stop {false};


}; /* class */

EXPORT_COMPONENT_API


#endif