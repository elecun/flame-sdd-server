/**
 * @file concurrent_queue.hpp
 * @author Byunghun Hwang<bh.hwang@iae.re.kr>
 * @brief 
 * @version 0.1
 * @date 2025-02-19
 * 
 * @copyright Copyright (c) 2025
 * 
 */

#ifndef FLAME_CONCURRENT_QUEUE_HPP_INCLUDED
#define FLAME_CONCURRENT_QUEUE_HPP_INCLUDED

#include <queue>
#include <thread>
#include <mutex>
#include <condition_variable>

template <typename T, unsigned int _buffer_size_ = 100>
class concurrent_queue {
    public:
        /* pop element */
        T pop() {
            std::unique_lock<std::mutex> mlock(mutex_);
            while(queue_.empty()) {
                cond_.wait(mlock);
            }
            auto val = queue_.front();
            queue_.pop();
            mlock.unlock();
            cond_.notify_one();
            return val;
        }

        bool empty(){
            std::unique_lock<std::mutex> mlock(mutex_);
            bool _empty = false;
            _empty = !(queue_.size()>0);
            mlock.unlock();
            // cond_.notify_one();
            return _empty;
        }

        /* pop element */
        void pop(T& item) {
            std::unique_lock<std::mutex> mlock(mutex_);
            while(queue_.empty()) {
                cond_.wait(mlock);
            }
            item = queue_.front();
            queue_.pop();
            mlock.unlock();
            cond_.notify_one();
        }

        bool pop_async(T& item){
            std::unique_lock<std::mutex> mlock(mutex_);
            bool ret = false;
            if(queue_.empty()){
                ret = false;
            }
            else {
                item = queue_.front();
                queue_.pop();
                ret = true;
            }
            mlock.unlock();
            cond_.notify_one();
            
            return ret;
        }

        /* push element */
        void push(const T& item) {
            std::unique_lock<std::mutex> mlock(mutex_);
            while(queue_.size() >= _buffer_size_) {
                cond_.wait(mlock);
            }
            queue_.push(item);
            mlock.unlock();
            cond_.notify_one();
        }
        concurrent_queue()=default;
        concurrent_queue(const concurrent_queue&) = delete;            // disable copying
        concurrent_queue& operator=(const concurrent_queue&) = delete; // disable assignment

    private:
        std::queue<T> queue_;
        std::mutex mutex_;
        std::condition_variable cond_;
        // const static unsigned int BUFFER_SIZE = 10;
};

#endif

// producer-consumer.cc
// #include "concurrent-queue.h"
// #include <iostream>
// #include <thread>

// void produce(ConcurrentQueue<int>& q) {
//   for (int i = 0; i< 10000; ++i) {
//     std::cout << "Pushing " << i << "\n";
//     q.push(i);
//   }
// }

// void consume(ConcurrentQueue<int>& q, unsigned int id) {
//   for (int i = 0; i< 2500; ++i) {
//     auto item = q.pop();
//     std::cout << "Consumer " << id << " popped " << item << "\n";
//   }
// }

// int main() {
//   ConcurrentQueue<int> q;

//   using namespace std::placeholders;

//   // producer thread
//   std::thread prod1(std::bind(produce, std::ref(q)));

//   // consumer threads
//   std::thread consumer1(std::bind(&consume, std::ref(q), 1));
//   std::thread consumer2(std::bind(&consume, std::ref(q), 2));
//   std::thread consumer3(std::bind(&consume, std::ref(q), 3));
//   std::thread consumer4(std::bind(&consume, std::ref(q), 4));

//   prod1.join();
//   consumer1.join();
//   consumer2.join();
//   consumer3.join();
//   consumer4.join();
//   return 0;
// }