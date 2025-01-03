# flame-sdd-server

SDD Server for DK

```
$ sudo apt install build-essential git libopencv-dev libzmq3-dev nmon ksh
```


Download & Install Pylon 7.5.0
```
# if you want to install pylon viewer, install belows
$ sudo apt-get install libgl1-mesa-dri libgl1-mesa-glx libxcb-xinerama0 libxcb-xinput0

$ sudo apt-get install ./pylon_*.deb ./codemeter*.deb
```


## Components
## dk.level2.terminal component
Modbus TCP(Server-side) into Internal Message(JSON)
- dependencies
```
$ sudo apt-get install libmodbus-dev
```

## autonics.temp.controller component
```
$ sudo apt-get install libmodbus-dev
```