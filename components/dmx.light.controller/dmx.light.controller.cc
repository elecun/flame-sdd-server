
#include "dk.light.linker.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>
#include <arpa/inet.h>
#include <sys/socket.h>

using namespace flame;

static dk_light_linker* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new dk_light_linker(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool dk_light_linker::on_init(){

    int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if(sockfd < 0) {
        logger::error("[{}] Failed socket create", get_name());
        return false;
    }
    

    //connect
    return true;
}

void dk_light_linker::on_loop(){

    // 수신자 주소 설정
    // struct sockaddr_in destAddr;
    // memset(&destAddr, 0, sizeof(destAddr));
    // destAddr.sin_family = AF_INET;
    // destAddr.sin_port = htons(ARTNET_PORT);
    // inet_pton(AF_INET, "192.168.0.100", &destAddr.sin_addr); // 수신할 장치의 IP 주소 입력

    // // Artnet 패킷 생성
    // ArtnetPacket packet;
    // memcpy(packet.id, ARTNET_ID, sizeof(ARTNET_ID));
    // packet.opcode = htons(0x5000);  // ArtDMX 패킷
    // packet.protocolVersion = htons(14);
    // packet.sequence = 0;
    // packet.physical = 0;
    // packet.universe = htons(0);     // Universe 0
    // packet.length = htons(DMX_CHANNELS);

    // // DMX 데이터 설정 (예: 첫 번째 채널을 최대 밝기로 설정)
    // memset(packet.data, 0, DMX_CHANNELS);
    // packet.data[0] = 255; // 첫 번째 DMX 채널 값 설정

    // // 패킷 전송
    // ssize_t bytesSent = sendto(sockfd, &packet, sizeof(packet), 0,
    //                            reinterpret_cast<struct sockaddr*>(&destAddr), sizeof(destAddr));
    // if (bytesSent < 0) {
    //     std::cerr << "패킷 전송 실패" << std::endl;
    // } else {
    //     std::cout << "패킷 전송 성공: " << bytesSent << " bytes" << std::endl;
    // }

    // // 소켓 닫기
    // close(sockfd);
    

}

void dk_light_linker::on_close(){
    
}

void dk_light_linker::on_message(){
    
}
