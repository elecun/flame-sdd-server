/**
 * @file dk.level2.terminal.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief DK Level2 Data Interface Terminal component
 * @version 0.1
 * @date 2024-06-30
 * 
 * @copyright Copyright (c) 2024
 * 
 */

#ifndef FLAME_DK_LEVEL2_TERMINAL_HPP_INCLUDED
#define FLAME_DK_LEVEL2_TERMINAL_HPP_INCLUDED

#include <flame/component/object.hpp>
#include <atomic>


class dk_level2_terminal : public flame::component::object {
    public:
        dk_level2_terminal() = default;
        virtual ~dk_level2_terminal() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        /* level2 data request response */
        void _response(json parameters);

        /* parse received packet into internal data */
        string _parse(json data);

        void _request(string port_name, json data);
        void _reply(string port_name, int response_code);
        bool _wait_response(string port_name);

    private:
        pthread_t _responser_handle;
        std::atomic<bool> _thread_stop_signal { false };

}; /* class */

EXPORT_COMPONENT_API


#endif