/**
 * @brief 
 * 
 */

#ifndef FLAME_DK_LEVEL2_INTERFACE_TCP_CLIENT_HPP_INCLUDED
#define FLAME_DK_LEVEL2_INTERFACE_TCP_CLIENT_HPP_INCLUDED

#include <boost/asio.hpp>
#include <flame/log.hpp>


using boost::asio::ip::tcp;

class tcp_client {
public:
tcp_client(boost::asio::io_context& io_context, const std::string& ip_address, int port)
:io_context_(io_context),socket_(io_context_) {
    start_connect(ip_address, port);
}

private:
    void start_connect(const std::string& ip_address, int port) {
        try {
            boost::asio::ip::address ip_addr = boost::asio::ip::address::from_string(ip_address);
            tcp::endpoint endpoint(ip_addr, port);

            boost::asio::async_connect(_socket, {endpoint}, // endpoint를 리스트로 감싸서 전달
                [this](const boost::system::error_code& error, const tcp::endpoint& /*endpoint*/){
                    if (!error) {
                        logger::info("<client> connected to server");
                        start_read();
                    } 
                    else {
                        logger::error("<client> connected failed, {}", error.message());
                        reconnect();
                    }
                });
        } catch (const std::exception& e) {
            logger::error("<client> connection exception, {}", e.what());
            reconnect();
        }
    }

    void start_read() {
        boost::asio::async_read(_socket, boost::asio::buffer(_read_buffer),
            [this](const boost::system::error_code& error, size_t bytes_transferred) {
                if (!error) {
                    logger::info("<client> received, {}", string(_read_buffer, bytes_transferred));
                    start_read();
                } else {
                    logger::error("<client> read failed, {}", error.message());
                    reconnect();
                }
            });
    }

    void reconnect() {
        logger::info("<client> try reconecting...");
        _socket.close();
        reconnect_timer_.expires_after(std::chrono::seconds(1));
        reconnect_timer_.async_wait([this](const boost::system::error_code& error){
            if (!error) {
                start_connect(ip_address_, port_);
            } else {
                logger::error("<client> reconnect timer error, {}", error.message());
            }
        });
    }

private:
    boost::asio::io_context& io_context_;
    tcp::socket _socket;
    boost::asio::steady_timer reconnect_timer_{io_context_};
    std::string ip_address_;
    std::string port_;
    char _read_buffer[1024];
}; /* tcp client */

class tcp_server {
    public:
    tcp_server(boost::asio::io_context& io_context, short port)
    : io_context_(io_context),acceptor_(io_context_, tcp::endpoint(tcp::v4(), port)),socket_(io_context_) { // 소켓을 멤버 변수로 생성
        start_accept();
    }
    
    private:
        void start_accept() {
            acceptor_.async_accept(socket_, // 멤버 변수 소켓 사용
                [this](const boost::system::error_code& error) {
                    if (!error) {
                        logger::info("<server> accepted connection");
                        start_read(); // 바로 읽기 시작
                    } else {
                        logger::error("<server> accept failed, {}", error.message());
                    }
                });
        }
    
        void start_read() {
            boost::asio::async_read(socket_, boost::asio::buffer(read_buffer_),
                [this](const boost::system::error_code& error, size_t bytes_transferred) {
                    if (!error) {
                        logger::info("<server> received : {}",std::string(read_buffer_, bytes_transferred));
                        start_write(std::string(read_buffer_, bytes_transferred)); // Echo back
                    } else {
                        logger::error("<server> read failed, {}", error.message());
                        socket_.close(); // 연결 닫기
                        start_accept(); // 새 연결 대기
                    }
                });
        }
    
        void start_write(const std::string& message) {
            boost::asio::async_write(socket_, boost::asio::buffer(message),
                [this](const boost::system::error_code& error, size_t /*bytes_transferred*/) {
                    if (error) {
                        logger::error("<server> write failed, {}", error.message());
                        socket_.close(); // 연결 닫기
                        start_accept(); // 새 연결 대기
                    }
                });
        }
    
    private:
        boost::asio::io_context& io_context_;
        tcp::acceptor acceptor_;
        tcp::socket socket_; // 멤버 변수 소켓
        char read_buffer_[1024];
    };

#endif