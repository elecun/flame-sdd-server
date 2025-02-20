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
