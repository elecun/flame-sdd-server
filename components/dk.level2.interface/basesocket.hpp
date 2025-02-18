/**
 * @file basesocket.hpp
 * @author Byunghun Hwang<bh.hwang@iae.re.kr>
 * @brief Base Socket class
 * @version 0.1
 * @date 2025-02-17
 * 
 * @copyright Copyright (c) 2025
 * 
 */

#ifndef FLAME_DK_LEVLE2_INTERFACE_BASE_SOCKET_HPP_INCLUDED
#define FLAME_DK_LEVLE2_INTERFACE_BASE_SOCKET_HPP_INCLUDED

#include <arpa/inet.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>
#include <netdb.h>
#include <string>
#include <functional>
#include <cerrno>
#include <flame/log.hpp>


#define FDR_UNUSED(expr){ (void)(expr); } 
#define FDR_ON_ERROR std::function<void(int, std::string)> onError = [](int errorCode, std::string errorMessage){FDR_UNUSED(errorCode); FDR_UNUSED(errorMessage)}

#ifndef AS_DEFAULT_BUFFER_SIZE
#define AS_DEFAULT_BUFFER_SIZE 0x1000 /*4096 bytes*/
#endif

class base_socket {

    public:
        /* socket type */
        enum type_socket
        {
            TCP = SOCK_STREAM,
            UDP = SOCK_DGRAM
        };
        sockaddr_in address;

    public:
        /* close socket */
        void close_socket(){
            shutdown(this->sock, SHUT_RDWR);
            close(this->sock);
        }

        std::string get_remote_address() const { return addr_to_string(this->address); }
        int get_remote_port() const { return ntohs(this->address.sin_port); }
        int get_file_descriptor() const { return this->sock; }

    protected:
        /* class constructor */
        base_socket(FDR_ON_ERROR, type_socket sockType = TCP, int socketId = -1){
            if (socketId == -1){
                this->sock = socket(AF_INET, sockType, 0);
                if ( this->sock == -1 ){
                    logger::error("Socket create error");
                }
            }
            else{
                this->sock = socketId;
            }
        }
        
        /* ip address to string */
        static std::string addr_to_string(const sockaddr_in& addr){
            char ip[INET_ADDRSTRLEN];
            inet_ntop(AF_INET, &(addr.sin_addr), ip, INET_ADDRSTRLEN);
            return std::string(ip);
        }

        virtual ~base_socket() = default;
        
    protected:
        int sock {0};

}; /* class */

#endif