/**
 * @file dk.level2.interface.hpp
 * @author Byunghun Hwang <bh.hwang@iae.re.kr>
 * @brief DK Level2 Data Interface component
 * @version 0.1
 * @date 2024-06-30
 * 
 * @copyright Copyright (c) 2024
 * 
 */

#ifndef FLAME_DK_LEVEL2_INTERFACE_HPP_INCLUDED
#define FLAME_DK_LEVEL2_INTERFACE_HPP_INCLUDED

#include <flame/component/object.hpp>
#include <iostream>
#include <boost/asio.hpp>
#include <boost/bind/bind.hpp>
#include "protocol.hpp"
#include <memory>

using namespace std;
using namespace boost::asio::ip;
using namespace boost::system

// class tcp_server;
class tcp_client;
class dk_level2_interface : public flame::component::object {
    public:
        dk_level2_interface() = default;
        virtual ~dk_level2_interface() = default;

        /* common interface functions */
        bool on_init() override;
        void on_loop() override;
        void on_close() override;
        void on_message() override;

    private:
        /* local vairables */
        unsigned long _alive_msg_counter {0};
        atomic<bool> _show_raw_packet {false};

        /* tcp-client related */
        unique_ptr<tcp::socket> _client_socket;
        tcp::endpoint _lv2_endpoint;
        boost::asio::steady_timer _reconnect_timer;

        /* tcp-server related */

    private:
        /* useful functions */
        string get_current_time();                      /* return localtime to string */
        void show_raw_packet(char* data, size_t size);  /* show raw packet data */

        /* packet generation */
        dk_sdd_alive generate_packet_alive();

        /* client-related */
        void lv2_connect();

    private:
        void _server_proc();

    private:
        boost::asio::io_context _io_context;

        string lv2_access_ip {"127.0.0.1"};
        int lv2_access_port;
        string sdd_host_ip {"127.0.0.1"} ;
        int sdd_host_port;

    private:
        vector<thread> _worker_container;
        atomic<bool> _worker_stop {false};


}; /* class */

class tcp_client {
    public:
    tcp_client(boost::asio::io_context& io_context, const std::string& host, int port)
    : _io_context(io_context),_endpoint(make_address(host), port) {
        start_connect();
    }

    virtual ~tcp_client() = default;
    
    private:
        void start_connect() {
            _socket = make_unique<boost::asio::ip::tcp::socket>(_io_context);
            boost::asio::async_connect(*_socket, _endpoint,
            [this](const boost::system::error_code& error, const tcp::endpoint& /*endpoint*/) {
                if (!error) {
                    std::cout << "Connected to server!" << std::endl;
                    start_read();
                } else {
                    std::cerr << "Connect failed: " << error.message() << std::endl;
                    reconnect();
                }
            });
        }
    
        void start_read() {
            boost::asio::async_read(*_socket, boost::asio::buffer(data_, max_length),
                [this](const boost::system::error_code& error, std::size_t bytes_transferred) {
                    if (!error) {
                        std::cout << "Read " << bytes_transferred << " bytes: " << data_ << std::endl;
                        start_read(); // Keep reading
                    } else {
                        std::cerr << "Read error: " << error.message() << std::endl;
                        _socket->close();
                        reconnect();
                    }
                });
        }
    
        void reconnect() {
            std::cout << "Reconnecting in 5 seconds..." << std::endl;
            _socket.reset();  // Close old socket if it exists
    
            // 재접속을 위한 타이머 설정
            _reconnect_timer.expires_after(std::chrono::seconds(5));
            _reconnect_timer.async_wait([this](const boost::system::error_code& error) {
                if (!error) {
                    start_connect();
                } else {
                    std::cerr << "Reconnect timer error: " << error.message() << std::endl;
                }
            });
        }
    
    private:
        boost::asio::io_context& _io_context;
        tcp::endpoint _endpoint;
        std::unique_ptr<boost::asio::ip::tcp::socket> _socket;
        boost::asio::steady_timer _reconnect_timer{_io_context};
        std::string _host;
        int _port;

        char data_[1024];
        static const int max_length = 1024;
}; /* tcp client class */


// class tcp_server {
//     public:
//     tcp_server(boost::asio::io_context& io_context, const string& host_ip, int port):
//         _acceptor(io_context, tcp::endpoint(boost::asio::ip::make_address(host_ip), port)){
//             start_accept();
//     }
//     virtual ~tcp_server() = default;

//     private:
//         void start_accept(){
//             _acceptor.async_accept(_socket, boost::bind(&tcp_server::handle_accept, this, boost::asio::placeholders::error));
//         }

//         void handle_accept(const boost::system::error_code& error){
//             if(!error){
//                 logger::info("client connected");
//                 start_read();
//             }

//             start_accept();

//         }

//         void start_read(){
//             // socket_.async_read_some(boost::asio::buffer(data_),
//             // boost::bind(&TCPServer::handleRead, this,
//             //             boost::asio::placeholders::error,
//             //             boost::asio::placeholders::bytes_transferred));
//         }

//         void handle_read(const boost::system::error_code& error, size_t bytes_transferred){
//             if(!error){
//                 logger::info("received {}bytes", bytes_transferred);
//                 start_read();
//             }
//             else {
//                 logger::info("client is disconnected");
//                 _socket.close();
//             }
//         }

//     private:
//         tcp::acceptor _acceptor;
//         tcp::socket _socket;
// }; /* class */

// class tcp_client {
//     public:
//     tcp_client(boost::asio::io_context& io_context, const std::string& server_ip, int port)
//             : _socket(io_context), _endpoint(boost::asio::ip::make_address(server_ip), port) {
//             start_connect();
//         }
    
//     private:
//         void start_connect() {
//             _socket.async_connect(_endpoint,
//                 boost::bind(&tcp_client::handle_connect, this, boost::asio::placeholders::error));
//         }
    
//         void handle_connect(const boost::system::error_code& error) {
//             if (!error) {
//                 std::cout << "서버에 연결되었습니다." << std::endl;
//                 start_write();
//             } else {
//                 std::cerr << "연결 실패: " << error.message() << std::endl;
//             }
//         }
    
//         void start_write() {
//             std::string message = "Hello from Client";
//             boost::asio::async_write(_socket, boost::asio::buffer(message),
//                 boost::bind(&tcp_client::handle_write, this, boost::asio::placeholders::error));
    
//             // 3초마다 메시지 전송
//             std::thread([this]() {
//                 while (true) {
//                     std::this_thread::sleep_for(std::chrono::seconds(3));
//                     std::string msg = "Ping";
//                     boost::asio::write(_socket, boost::asio::buffer(msg));
//                     logger::info("message transferred");
//                 }
//             }).detach();
//         }
    
//         void handle_write(const boost::system::error_code& error) {
//             if (error) {
//                 logger::info("message transfer is failed : {}", error.message());
//             }
//         }
    
//         tcp::socket _socket;
//         tcp::endpoint _endpoint;
//     };

EXPORT_COMPONENT_API


#endif