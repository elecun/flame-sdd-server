/**
 * @file dk.sdd.inference.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief SDD model inference component
 * @version 0.1
 * @date 2025-04-22
 * 
 * @copyright Copyright (c) 2024
 * 
 */

#ifndef FLAME_DK_SDD_INFERENCE_HPP_INCLUDED
#define FLAME_DK_SDD_INFERENCE_HPP_INCLUDED

#include <flame/component/object.hpp>
#include <torch/script.h>
#include <torch/torch.h>


class dk_sdd_inference : public flame::component::object {
    public:
        dk_sdd_inference() = default;
        virtual ~dk_sdd_inference() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        void inference();

}; /* class */

EXPORT_COMPONENT_API


#endif  