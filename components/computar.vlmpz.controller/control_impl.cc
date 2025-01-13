# include "computar.vlmpz.controller.hpp"

#define SATURATE(x, min, max) ((x) < (min) ? (min) : ((x) > (max) ? (max) : (x)))

bool controlImpl::open(int device_idx){
    if(UsbOpen(device_idx))
        return false;
    if(UsbSetConfig())
        return false;

    uint16_t capabilities;
    CapabilitiesRead(&capabilities);
	Status2ReadSet();

	if(capabilities & FOCUS_MASK) {
		FocusParameterReadSet();
		if((status2 & FOCUS_MASK) == INIT_COMPLETED)
			FocusCurrentAddrReadSet();
	}
	if(capabilities & IRIS_MASK) {
		IrisParameterReadSet();
		if((status2 & IRIS_MASK) == INIT_COMPLETED)
			IrisCurrentAddrReadSet();
	}

	/* start worker thread */
	_control_worker = make_unique<thread>(&controlImpl::run_process, this);
    
    return true;
}

int controlImpl::read_focus_position(){
	return FocusCurrentAddrReadSet();
}

void controlImpl::close(){

	_is_running = false;
	this_thread::sleep_for(chrono::milliseconds(500));
	if(_control_worker && _control_worker->joinable()){
		_control_worker->join();
	}

	// /* close USB */
    // UsbClose();

	logger::info("close controlImpl");
}

void controlImpl::focus_initialize(){
	json api = {
		{"function","focus_initialize"}
	};
	caller(api);
}

void controlImpl::iris_initialize(){
	json api = {
		{"function","iris_initialize"}
	};
	caller(api);
}

void controlImpl::focus_move(int value){
	json api = {
		{"function","move_focus"},
		{"value", value}
	};
	caller(api);
}

void controlImpl::iris_move(int value){
	json api = {
		{"function","iris_move"},
		{"value", value}
	};
	caller(api);
}

bool controlImpl::caller(const json& api){
	lock_guard<mutex> lock(_mutex);
	if(_f_queue.empty()){
		_f_queue.push([this, api]() { execute(api); });
		return true;
	}
	else {
		logger::warn("Device is now working.., please wait until the job is finished.");
		return false;
	}
}

void controlImpl::execute(const json& api){
	
	if(api.contains("function")) {
		string function_name = api["function"].get<string>();

		if(function_code.contains(function_name)){
			int fcode = function_code[function_name];
			switch(fcode){
				case 1: { //focus initialize
					FocusInit();
					logger::info("Lens #{} Focus is initialized",_lens_id);
				}
				break;

				case 2: { //iris initialize
					IrisInit();
					logger::info("Lens #{} Iris is initialized",_lens_id);
				}
				break;

				case 3: { // focus_move
					int value = api["value"].get<int>();
					value = SATURATE(value, 0, 9091);
					FocusMove((uint16_t)value);
					logger::info("Lens #{} move focus : {}", _lens_id, value);
				}
				break;

				case 4: { //iris move
					int value = api["value"].get<int>();
					value = SATURATE(value, 0, 12636);
					IrisMove((uint16_t)value);
				}

				default:
					logger::warn("Unknown function");
			}
		}
	} else {
		logger::warn("API does not contain 'function' key.");
	}
}

void controlImpl::run_process(){

	while(_is_running){
		function<void()> task;
		{
			lock_guard<mutex> lock(_mutex);
			if(!_f_queue.empty()){
				task = move(_f_queue.front());
				_f_queue.pop();
			}
		}

		if(task){
			task();
		}
		else{
			this_thread::sleep_for(chrono::milliseconds(100));
		}
	}
}