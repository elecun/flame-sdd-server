/**
 * @file dk.level2.gateway.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief DK Level2 Data Interface component
 * @version 0.1
 * @date 2024-06-30
 * 
 * @copyright Copyright (c) 2024
 * 
 */

#ifndef FLAME_DK_LEVEL2_GATEWAY_HPP_INCLUDED
#define FLAME_DK_LEVEL2_GATEWAY_HPP_INCLUDED

#include <flame/component/object.hpp>


class dk_level2_gateway : public flame::component::object {
    public:
        dk_level2_gateway() = default;
        virtual ~dk_level2_gateway() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

}; /* class */

EXPORT_COMPONENT_API


#endif