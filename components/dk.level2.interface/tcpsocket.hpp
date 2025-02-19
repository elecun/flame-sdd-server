/**
 * @file tcpsocket.hpp
 * @author your name (you@domain.com)
 * @brief 
 * @version 0.1
 * @date 2025-02-18
 * 
 * @copyright Copyright (c) 2025
 * 
 */

 #ifndef FLAME_COMPONENT_DK_LEVEL2_INTERFACE_TCP_SOCKET_HPP_INCLUDED
 #define FLAME_COMPONENT_DK_LEVEL2_INTERFACE_TCP_SOCKET_HPP_INCLUDED

#include "basesocket.hpp"
#include <string>
#include <string.h>
#include <functional>
#include <thread>

template <unsigned short _buffer_size_ = AS_DEFAULT_BUFFER_SIZE>
class tcp_socket : public base_socket
{
public:
    
    /* event listener*/
    std::function<void(std::string)> on_message_received;
    std::function<void(const char*, ssize_t)> on_raw_message_received;
    std::function<void(int)> on_socket_closed;

    /* constructor */
    explicit tcp_socket(FDR_ON_ERROR, int socket_id = -1) : base_socket(onError, TCP, socket_id){}

    /* send */
    ssize_t send(const char* bytes, size_t byteslength) { return ::send(this->sock, bytes, byteslength, 0); } /* send raw bytes */
    ssize_t send(const std::string& message) { return this->send(message.c_str(), message.length()); } /* send string (std::string)*/

    // Connect to a TCP Server with `uint32_t ipv4` & `uint16_t port` values
    void connect(uint32_t ipv4, uint16_t port, std::function<void()> on_connected = [](){}, FDR_ON_ERROR)
    {
        this->address.sin_family = AF_INET;
        this->address.sin_port = htons(port);
        this->address.sin_addr.s_addr = ipv4;

        this->set_timeout(1);

        int status = ::connect(this->sock, (const sockaddr*)&this->address, sizeof(sockaddr_in));
        if(status == -1)
        {
            onError(errno, "Connection failed to the host.");
            this->set_timeout(0);
            return;
        }

        this->set_timeout(0);

        // Connected to the server, fire the event.
        on_connected();

        // Start listening from server:
        //this->listen();
    }
    // Connect to a TCP Server with `const char* host` & `uint16_t port` values
    void connect(const char* host, uint16_t port, std::function<void()> on_connected = [](){}, FDR_ON_ERROR)
    {
        struct addrinfo hints, *res, *it;
        memset(&hints, 0, sizeof(hints));
        hints.ai_family = AF_INET;
        hints.ai_socktype = SOCK_STREAM;

        // Get address info from DNS
        int status = getaddrinfo(host, NULL, &hints, &res);
        if ( status != 0 ) {
            onError(errno, "Invalid address." + std::string(gai_strerror(status)));
            return;
        }

        for(it = res; it != NULL; it = it->ai_next)
        {
            if (it->ai_family == AF_INET) { // IPv4
                memcpy((void*)(&this->address), (void*)it->ai_addr, sizeof(sockaddr_in));
                break; // for now, just get the first ip (ipv4).
            }
        }

        freeaddrinfo(res);

        this->connect((uint32_t)this->address.sin_addr.s_addr, port, on_connected, onError);
    }
    // Connect to a TCP Server with `const std::string& ipv4` & `uint16_t port` values
    void connect(const std::string& host, uint16_t port, std::function<void()> on_connected = [](){}, FDR_ON_ERROR){
        this->connect(host.c_str(), port, on_connected, onError);
    }

    // Start another thread to listen the socket
    void listen()
    {
        std::thread t(tcp_socket::receive, this);
        t.detach();
    }

    void setAddressStruct(sockaddr_in addr) {this->address = addr;}
    sockaddr_in getAddressStruct() const {return this->address;}

    bool deleteAfterClosed = false;

private:
    atomic<bool> _opened { false };

private:
    static void receive(tcp_socket* socket)
    {
        char tempBuffer[_buffer_size_+1];
        ssize_t messageLength;

        while ((messageLength = recv(socket->sock, tempBuffer, _buffer_size_, 0)) > 0)
        {
            tempBuffer[messageLength] = '\0';
            if(socket->on_message_received)
                socket->on_message_received(std::string(tempBuffer, messageLength));
            
            if(socket->on_raw_message_received)
                socket->on_raw_message_received(tempBuffer, messageLength);
        }

        socket->close();

        if(socket->on_socket_closed)
            socket->on_socket_closed(errno);
        
        if (socket->deleteAfterClosed && socket != nullptr)
            delete socket;
    }

    /* send & receive timeout */
    void set_timeout(int seconds)
    {
        struct timeval tv;      
        tv.tv_sec = seconds;
        tv.tv_usec = 0;

        setsockopt(this->sock, SOL_SOCKET, SO_RCVTIMEO, (char*)&tv, sizeof(tv));
        setsockopt(this->sock, SOL_SOCKET, SO_SNDTIMEO, (char*)&tv, sizeof(tv));
    }
};

#endif