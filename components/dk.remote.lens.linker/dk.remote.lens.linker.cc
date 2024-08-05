
#include "dk.remote.lens.linker.hpp"
#include <flame/log.hpp>
#include <flame/config_def.hpp>

using namespace flame;

static dk_remote_lens_linker* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new dk_remote_lens_linker(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool dk_remote_lens_linker::on_init(){

    int n_devices = get_profile()->parameters().value("n_devices", 10);
    _lens_scan();
    
    //connect
    return true;
}

void dk_remote_lens_linker::on_loop(){
    


}

void dk_remote_lens_linker::on_close(){
	// UsbClose();
}

void dk_remote_lens_linker::on_message(){
    
}

void dk_remote_lens_linker::_lens_device_connect(int n_devices){
    
	int retval = UsbOpen(n_devices);
	if(retval != SUCCESS){
        logger::error("[{}] {}", get_name(), ErrorTxt(retval));
		return;
	}

	retval = UsbSetConfig();
	if(retval != SUCCESS){
        logger::error("[{}] {}", get_name(), ErrorTxt(retval));
		return;
	}
	logger::info("Lens device is connected.");

    // uint16_t capabilities;
	// CapabilitiesRead(&capabilities);
	// Status2ReadSet();

	// if(capabilities & ZOOM_MASK) {
	// 	ZoomParameterReadSet();
	// 	if((status2 & ZOOM_MASK) == INIT_COMPLETED)
	// 	    ZoomCurrentAddrReadSet();
	// 	withZoom = TRUE;
	// }
	// if(capabilities & FOCUS_MASK) {
	// 	FocusParameterReadSet();
	// 	if ((status2 & FOCUS_MASK) == INIT_COMPLETED)
	// 		FocusCurrentAddrReadSet();
	// 	withFocus = TRUE;
	// }
	// if(capabilities & IRIS_MASK) {
	// 	IrisParameterReadSet();
	// 	if ((status2 & IRIS_MASK) == INIT_COMPLETED)
	// 		IrisCurrentAddrReadSet();
	// 	withIris = TRUE;
	// }
	// if(capabilities & OPT_FILTER_MASK) {
	// 	OptFilterParameterReadSet();
	// 	if ((status2 & OPT_FILTER_MASK) == INIT_COMPLETED)
	// 		OptFilterCurrentAddrReadSet();
	// 	withOptFil = TRUE;
	// }
	// USBOpen_flag = TRUE;
}

void dk_remote_lens_linker::_lens_device_disconnect(){

}

void dk_remote_lens_linker::_lens_scan()
{
    // unsigned int _n_devices = 0;
	// char _sn_string[260];	// SnString is 260bytes according to the instructions of the USB IC
	// char _model[25];
	// UsbGetNumDevices(&_n_devices);
	// if(_n_devices >= 1) {
	// 	for(unsigned short i=0; i<_n_devices; i++) {
	// 		int retval = UsbGetSnDevice(i, _sn_string);
	// 		if(retval == SUCCESS){
	// 			UsbOpen(i);
	// 			ModelName(_model);
    //             logger::info("Lens #{} : {}({})", i, _model, _sn_string);
	// 			UsbClose();
	// 			logger::info("device closed");
	// 		}
    //         else {
    //             logger::warn("Len devices cannot be scanned");
    //         }
	// 	}
	// }
	// else
    //     logger::warn("No Lens devices are connected");
}