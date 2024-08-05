/**
 * @file dk.data.aggregator.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief Data Aggregator for GUI
 * @version 0.1
 * @date 2024-07-10
 * 
 * @copyright Copyright (c) 2024
 * 
 */

#ifndef FLAME_DK_DATA_AGGREGATOR_HPP_INCLUDED
#define FLAME_DK_DATA_AGGREGATOR_HPP_INCLUDED

#include <flame/component/object.hpp>


class dk_data_aggregator : public flame::component::object {
    public:
        dk_data_aggregator() = default;
        virtual ~dk_data_aggregator() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

}; /* class */

EXPORT_COMPONENT_API


#endif