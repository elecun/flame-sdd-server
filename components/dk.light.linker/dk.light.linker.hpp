/**
 * @file remote.light.linker.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief Light device linker working on remote-side controller
 * @version 0.1
 * @date 2024-06-30
 * 
 * @copyright Copyright (c) 2024
 * 
 */


#ifndef FLAME_DK_REMOTE_LIGHT_LINKER_HPP_INCLUDED
#define FLAME_DK_REMOTE_LIGHT_LINKER_HPP_INCLUDED

#include <flame/component/object.hpp>

const char ARTNET_ID[] = "Art-Net";
const uint16_t ARTNET_PORT = 6454;
const int DMX_CHANNELS = 512;

#pragma pack(push, 1)
struct ArtnetPacket {
    char id[8];
    uint16_t opcode;
    uint16_t protocolVersion;
    uint8_t sequence;
    uint8_t physical;
    uint16_t universe;
    uint16_t length;
    uint8_t data[DMX_CHANNELS];
};
#pragma pack(pop)


class dk_light_linker : public flame::component::object {
    public:
        dk_light_linker() = default;
        virtual ~dk_light_linker() = default;

        // default interface functions
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:

}; /* class */

EXPORT_COMPONENT_API


#endif