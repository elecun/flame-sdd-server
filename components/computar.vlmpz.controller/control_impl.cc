#include "computar.vlmpz.controller.hpp"
#include <time.h>

#define SATURATE(x, min, max) ((x) < (min) ? (min) : ((x) > (max) ? (max) : (x)))
#define MILLI_SEC 1000000L
unsigned char i2cAddr = I2CSLAVEADDR * 2;

controlImpl::controlImpl(string parent_name, int device_id, int camera_id)
:_parent_name(parent_name), _lens_device_id(device_id), _lens_camera_id(camera_id){

}

bool controlImpl::open(){

	/* USB Open */
	if(this->UsbOpen(_lens_device_id))
		return false;

	/* USB Set Config */
    if(this->UsbSetConfig())
		return false;

    uint16_t capabilities;
    this->CapabilitiesRead(&capabilities);
	this->Status2ReadSet();

	if(capabilities & FOCUS_MASK) {
		this->FocusParameterReadSet();
		if((status2 & FOCUS_MASK) == INIT_COMPLETED)
			this->FocusCurrentAddrReadSet();
	}
	if(capabilities & IRIS_MASK) {
		this->IrisParameterReadSet();
		if((status2 & IRIS_MASK) == INIT_COMPLETED)
			this->IrisCurrentAddrReadSet();
	}

	/* start worker thread */
	_control_worker = make_unique<thread>(&controlImpl::run_process, this);
    
    return true;
}

int controlImpl::read_focus_position(){
	return this->FocusCurrentAddrReadSet();
}

void controlImpl::close(){

	_is_running.store(false);
	this_thread::sleep_for(chrono::milliseconds(500));
	if(_control_worker && _control_worker->joinable()){
		_control_worker->join();
	}

	// /* close USB */
	this->UsbClose();

	logger::info("close Lens Controller");
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
	// json api = {
	// 	{"function","move_focus"},
	// 	{"value", value}
	// };
	// caller(api);
	//value = SATURATE(value, 0, 9091);
	//this->FocusMove((uint16_t)value);
	logger::info("Lens #{} move focus : {}", _lens_device_id, value);
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
					this->FocusInit();
					logger::info("Lens #{} Focus is initialized",_lens_device_id);
				}
				break;

				case 2: { //iris initialize
					this->IrisInit();
					logger::info("Lens #{} Iris is initialized",_lens_device_id);
				}
				break;

				case 3: { // focus_move
					int value = api["value"].get<int>();
					value = SATURATE(value, 0, 9091);
					this->FocusMove((uint16_t)value);
					logger::info("Lens #{} move focus : {}", _lens_device_id, value);
				}
				break;

				case 4: { //iris move
					int value = api["value"].get<int>();
					value = SATURATE(value, 0, 12636);
					this->IrisMove((uint16_t)value);
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

	while(_is_running.load()){
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


int controlImpl::UsbGetNumDevices(unsigned int* numDevices){
	int retval = HidSmbus_GetNumDevices(numDevices, VID, PID);
	return retval;
}
int controlImpl::UsbGetSnDevice(unsigned short index, char* SnString){
	int retval = HidSmbus_GetString(index, VID, PID, SnString, HID_SMBUS_GET_SERIAL_STR);
	return retval;
}
int controlImpl::UsbOpen(unsigned long deviceNumber){
	int retval = HidSmbus_Open(&this->connectedDevice, deviceNumber, VID, PID);
	return retval;
}
void controlImpl::UsbClose(){
	HidSmbus_Close(this->connectedDevice);
}
int controlImpl::UsbSetConfig(){
	int retval = HidSmbus_SetSmbusConfig(this->connectedDevice,
		BITRATE, i2cAddr, AUTOREADRESPOND,
		WRITETIMEOUT, READTIMEOUT,
		SCLLOWTIMEOUT, TRANSFARRETRIES);
	if (retval == HID_SMBUS_SUCCESS)
		return retval;

	retval = HidSmbus_SetGpioConfig(this->connectedDevice, DIRECTION, MODE, SPECIAL, CLKDIV);
	if (retval == HID_SMBUS_SUCCESS)
		return retval;

	retval = HidSmbus_SetTimeouts(this->connectedDevice, RESPONSETIMEOUT);
	if (retval == HID_SMBUS_SUCCESS)
		return retval;

	return retval;
}
int controlImpl::UsbRead(unsigned short segmentOffset, unsigned short receiveSize){
	unsigned char sendData[SEGMENTOFFSET_LENGTH];
	sendData[0] = segmentOffset >> 8;
	sendData[1] = (unsigned char)segmentOffset;
	BYTE sendSize = sizeof(sendData);
	int retval = HidSmbus_WriteRequest(this->connectedDevice, i2cAddr, sendData, sendSize);
	if (retval != HID_SMBUS_SUCCESS)
		return retval;

	retval = HidSmbus_ReadRequest(this->connectedDevice, i2cAddr, receiveSize);
	if (retval != HID_SMBUS_SUCCESS)
		return retval;

	retval = HidSmbus_ForceReadResponse(this->connectedDevice, receiveSize);
	if (retval != HID_SMBUS_SUCCESS)
		return retval;

	unsigned char receiveData[128];
	HID_SMBUS_S0 status;
	BYTE totalBytesRead = 0;
	BYTE bufferSize = 62;
	BYTE bytesRead = 0;
	do {
		retval = HidSmbus_GetReadResponse(this->connectedDevice, &status, 
			receiveData + totalBytesRead, bufferSize, &bytesRead);
		if (retval != HID_SMBUS_SUCCESS)
			return retval;

		totalBytesRead += bytesRead;
	} while (totalBytesRead < receiveSize);

	for (int i = 0; i < totalBytesRead; i++) {
		receivedData[i] = receiveData[i];
	}
	return retval;
}
unsigned short controlImpl::UsbRead2Bytes(){
	return ((receivedData[0] << 8) | receivedData[1]);
}
unsigned int controlImpl::CountRead(){
	return ((receivedData[0] << 24) | (receivedData[1] << 16) | (receivedData[2] << 8) | (receivedData[3]));
}
int controlImpl::UsbWrite(unsigned short segmentOffset, unsigned short writeData){
	unsigned char sendData[4];
	sendData[0] = segmentOffset >> 8;
	sendData[1] = (unsigned char)segmentOffset;
	sendData[2] = writeData >> 8;
	sendData[3] = (unsigned char)writeData;
	BYTE sendSize = sizeof(sendData);
	int retval = HidSmbus_WriteRequest(this->connectedDevice, i2cAddr, sendData, sendSize);
	return retval;
}

int controlImpl::CapabilitiesRead(unsigned short* capabilities) {
	int retval = this->UsbRead(CAPABILITIES, DATA_LENGTH);
	*capabilities = this->UsbRead2Bytes();
	return retval;
}

int controlImpl::Status2ReadSet() {
	int retval = this->UsbRead(STATUS2, DATA_LENGTH);
	if (retval != HID_SMBUS_SUCCESS)
		return retval;
	status2 = this->UsbRead2Bytes();
	return retval;
}

int controlImpl::FocusParameterReadSet() {
	int retval = this->UsbRead(FOCUS_MECH_STEP_MIN, DATA_LENGTH);
	if (retval != HID_SMBUS_SUCCESS)
		return retval;
	this->focusMinAddr = this->UsbRead2Bytes();

	retval = this->UsbRead(FOCUS_MECH_STEP_MAX, DATA_LENGTH);
	if (retval != HID_SMBUS_SUCCESS)
		return retval;
	this->focusMaxAddr = this->UsbRead2Bytes();

	retval = this->UsbRead(FOCUS_SPEED_VAL, DATA_LENGTH);
	if (retval != HID_SMBUS_SUCCESS)
		return retval;
	this->focusSpeedPPS = this->UsbRead2Bytes();

	return retval;
}

int controlImpl::FocusCurrentAddrReadSet() {
	int retval = this->UsbRead(FOCUS_POSITION_VAL, DATA_LENGTH);
	focusCurrentAddr = this->UsbRead2Bytes();
	return retval;
}

int controlImpl::IrisParameterReadSet() {
	int retval = this->UsbRead(IRIS_MECH_STEP_MIN, DATA_LENGTH);
	if (retval != HID_SMBUS_SUCCESS)
		return retval;
	irisMinAddr = this->UsbRead2Bytes();

	retval = this->UsbRead(IRIS_MECH_STEP_MAX, DATA_LENGTH);
	if (retval != HID_SMBUS_SUCCESS)
		return retval;
	irisMaxAddr = this->UsbRead2Bytes();

	retval = this->UsbRead(IRIS_SPEED_VAL, DATA_LENGTH);
	if (retval != HID_SMBUS_SUCCESS)
		return retval;
	irisSpeedPPS = this->UsbRead2Bytes();

	return retval;
}

int controlImpl::IrisCurrentAddrReadSet() {
	int retval = this->UsbRead(IRIS_POSITION_VAL, DATA_LENGTH);
	irisCurrentAddr = this->UsbRead2Bytes();
	return retval;
}

int controlImpl::FocusInit() {
	int waitTime = WaitCalc((focusMaxAddr - focusMinAddr), focusSpeedPPS);
	int retval = this->UsbWrite(FOCUS_INITIALIZE, INIT_RUN_BIT);
	if (retval == HID_SMBUS_SUCCESS) {
		retval = this->StatusWait(STATUS1, FOCUS_MASK, waitTime);
		if (retval == HID_SMBUS_SUCCESS) {
			retval = this->UsbRead(FOCUS_POSITION_VAL, DATA_LENGTH);
			if (retval == HID_SMBUS_SUCCESS) {
				focusCurrentAddr = this->UsbRead2Bytes();
				this->Status2ReadSet();
				return retval;
			}
		}
	}
	return retval;
}

void controlImpl::MsSleep(int n) {
	struct timespec ts;
	ts.tv_sec  = 0;
	ts.tv_nsec = MILLI_SEC;
	nanosleep(&ts, NULL);
}

int controlImpl::StatusWait(unsigned short segmentOffset, unsigned short statusMask, int waitTime) {
	int tmp = 0;
	unsigned short readStatus;
	int retval;
	do {
		retval = this->UsbRead(segmentOffset, DATA_LENGTH);
		if (retval != HID_SMBUS_SUCCESS)
			return retval;

		readStatus = this->UsbRead2Bytes();
		tmp += 1;
		if (tmp >= LOW_HIGH_WAIT)
			return LOWHI_ERROR;

	} while ((readStatus & statusMask) != statusMask);

	tmp = 0;
	do {
		retval = this->UsbRead(segmentOffset, DATA_LENGTH);
		if (retval != HID_SMBUS_SUCCESS)
			return retval;

		readStatus = this->UsbRead2Bytes();
		tmp += 1;
		if (tmp >= waitTime)
			return HILOW_ERROR;
		
		this->MsSleep(1);
	} while ((readStatus & statusMask) != 0);

	return retval;
}

int controlImpl::IrisInit() {
	int waitTime = this->WaitCalc((irisMaxAddr - irisMinAddr), irisSpeedPPS);
	int retval = this->UsbWrite(IRIS_INITIALIZE, INIT_RUN_BIT);
	if (retval == HID_SMBUS_SUCCESS) {
		retval = this->StatusWait(STATUS1, IRIS_MASK, waitTime);
		if (retval == HID_SMBUS_SUCCESS) {
			retval = this->UsbRead(IRIS_POSITION_VAL, DATA_LENGTH);
			if (retval == HID_SMBUS_SUCCESS) {
				irisCurrentAddr = this->UsbRead2Bytes();
				this->Status2ReadSet();
				return retval;
			}
		}
	}
	return retval;
}

int controlImpl::WaitCalc(unsigned short moveValue, int speedPPS) {
	int waitTime = WAIT_MAG * moveValue / speedPPS;
	if (MINIMUM_WAIT > waitTime)
		waitTime = MINIMUM_WAIT;
	return waitTime;
}

int controlImpl::FocusMove(unsigned short addrData) {
	unsigned short moveVal = abs(addrData - focusCurrentAddr);
	int waitTime = this->WaitCalc(moveVal, focusSpeedPPS);
	int retval = DeviceMove(FOCUS_POSITION_VAL, &addrData, FOCUS_MASK, waitTime);
	if (retval == HID_SMBUS_SUCCESS)
		focusCurrentAddr = addrData;
	return retval;
}

int controlImpl::DeviceMove(unsigned short segmentOffset, unsigned short *addrData, unsigned short mask , int waitTime) {
	int retval = this->UsbWrite(segmentOffset, *addrData);
	if (retval == HID_SMBUS_SUCCESS) {
		retval = this->StatusWait(STATUS1, mask, waitTime);
		if (retval == HID_SMBUS_SUCCESS) {
			retval = this->UsbRead(segmentOffset, DATA_LENGTH);
			if (retval != HID_SMBUS_SUCCESS)
				return retval;
			*addrData = this->UsbRead2Bytes();
			return retval;
		}
		return retval;
	}
	return retval;
}

int controlImpl::IrisMove(unsigned short addrData) {
	unsigned short moveVal = abs(addrData - irisCurrentAddr);
	int waitTime = this->WaitCalc(moveVal, irisSpeedPPS);
	int retval = this->DeviceMove(IRIS_POSITION_VAL, &addrData, IRIS_MASK, waitTime);
	if (retval == HID_SMBUS_SUCCESS)
		irisCurrentAddr = addrData;
	return retval;
}