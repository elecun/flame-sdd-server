/**
 * @file dk.local.temp.indicator.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief Temperature Read from RS485 and push message
 * @version 0.1
 * @date 2024-07-02
 * 
 * @copyright Copyright (c) 2024
 * 
 */

#ifndef FLAME_DK_LOCAL_TEMP_INDICATOR_HPP_INCLUDED
#define FLAME_DK_LOCAL_TEMP_INDICATOR_HPP_INCLUDED

#include <flame/component/object.hpp>
#include <libserial/SerialStream.h>

using namespace LibSerial;

class dk_local_temp_indicator : public flame::component::object {
    public:
        dk_local_temp_indicator() = default;
        virtual ~dk_local_temp_indicator() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        LibSerial::SerialStream _port;

}; /* class */

EXPORT_COMPONENT_API


#endif