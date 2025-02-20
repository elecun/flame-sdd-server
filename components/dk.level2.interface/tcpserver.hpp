
/**
 * @file tcpserver.hpp
 * @author your name (you@domain.com)
 * @brief 
 * @version 0.1
 * @date 2025-02-17
 * 
 * @copyright Copyright (c) 2025
 * 
 */

#ifndef FLAME_DK_LEVLE2_INTERFACE_TCP_SERVER_HPP_INCLUDED
#define FLAME_DK_LEVLE2_INTERFACE_TCP_SERVER_HPP_INCLUDED

#pragma once

#include "tcpsocket.hpp"
#include <thread>

template <uint16_t _buffer_size_ = AS_DEFAULT_BUFFER_SIZE>
class tcp_server : public base_socket
{
public:
    // Event Listeners:
    std::function<void(tcp_socket<_buffer_size_>*)> on_new_connection = [](tcp_socket<_buffer_size_>* sock){FDR_UNUSED(sock)};

    explicit tcp_server(FDR_ON_ERROR): base_socket(onError, type_socket::TCP)
    {
        int opt = 1;
        setsockopt(this->sock,SOL_SOCKET,SO_REUSEADDR,&opt,sizeof(int));
        setsockopt(this->sock,SOL_SOCKET,SO_REUSEPORT,&opt,sizeof(int));
    }

    // Bind the custom address & port of the server.
    void bind(const char* address, uint16_t port, FDR_ON_ERROR)
    {
        int status = inet_pton(AF_INET, address, &this->address.sin_addr);
        switch (status) {
            case -1:
                onError(errno, "Invalid address. Address type not supported.");
                return;
            case 0:
                onError(errno, "AF_INET is not supported. Please send message to developer.");
                return;
            default:
                break;
        }

        this->address.sin_family = AF_INET;
        this->address.sin_port = htons(port);

        if(::bind(this->sock, (const sockaddr*)&this->address, sizeof(this->address)) == -1)
        {
            onError(errno, "Cannot bind the socket.");
            return;
        }
    }
    // Bind the address(0.0.0.0) & port of the server.
    void bind(uint16_t port, FDR_ON_ERROR) { this->bind("0.0.0.0", port, onError); }

    // Start listening incoming connections.
    void listen(FDR_ON_ERROR)
    {
        if(::listen(this->sock, 1) == -1)
        {
            onError(errno, "Error: Server can't listen the socket.");
            return;
        }

        std::thread t(accept, this, onError);
        t.detach();
    }

private:
    static void accept(tcp_server<_buffer_size_>* server, FDR_ON_ERROR)
    {
        sockaddr_in new_sock_info;
        socklen_t new_sock_info_len = sizeof(new_sock_info);

        int new_fd = -1;
        while(true)
        {
            new_fd = ::accept(server->sock, (sockaddr*)&new_sock_info, &new_sock_info_len);
            if (new_fd == -1)
            {
                if(errno == EBADF || errno == EINVAL) return;
                onError(errno, "Error while accepting a new connection.");
                return;
            }

            tcp_socket<_buffer_size_>* new_sock = new tcp_socket<_buffer_size_>(onError, new_fd);
            new_sock->deleteAfterClosed = true;
            new_sock->setAddressStruct(new_sock_info);

            server->on_new_connection(new_sock);
            new_sock->listen();
        }
    }
};

#endif