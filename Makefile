# Author : Byunghun Hwang <bh.hwang@iae.re.kr>


# Build for architecture selection (editable!!)
ARCH := $(shell uname -m)
OS := $(shell uname)

CURRENT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
CURRENT_DIR_NAME := $(notdir $(patsubst %/,%,$(dir $(CURRENT_DIR))))

# path
FLAME_PATH = $(CURRENT_DIR)/flame
INCLUDES = $(FLAME_PATH)/include
SOURCE_FILES = .

#Compilers
ifeq ($(ARCH),arm64)
	CC := /usr/bin/aarch64-linux-gnu-g++
	GCC := /usr/bin/aarch64-linux-gnu-g++
	LD_LIBRARY_PATH += -L./lib/arm64
	OUTDIR		= $(CURRENT_DIR)/bin/arm64
	BUILDDIR	= $(CURRENT_DIR)/bin/arm64
	INCLUDE_DIR = -I./ -I$(CURRENT_DIR)/ -I$(CURRENT_DIR)/include/ -I$(CURRENT_DIR)/include/dep -I/usr/include
	LD_LIBRARY_PATH += -L/usr/local/lib -L./lib/arm64
else ifeq ($(ARCH), armhf)
	CC := /usr/bin/arm-linux-gnueabihf-g++-9
	GCC := /usr/bin/arm-linux-gnueabihf-gcc-9
	LD_LIBRARY_PATH += -L./lib/armhf
	OUTDIR		= $(CURRENT_DIR)/bin/armhf
	BUILDDIR	= $(CURRENT_DIR)/bin/armhf
	INCLUDE_DIR = -I./ -I$(CURRENT_DIR)/ -I$(CURRENT_DIR)/include/ -I$(CURRENT_DIR)/include/dep -I/usr/include
	LD_LIBRARY_PATH += -L/usr/local/lib -L./lib/armhf
else ifeq ($(ARCH), aarch64) # for Mac Apple Silicon
	CC := g++
	GCC := gcc
#	LD_LIBRARY_PATH += -L./lib/aarch64-linux-gnu
	OUTDIR		= $(CURRENT_DIR)/bin/aarch64
	BUILDDIR	= $(CURRENT_DIR)/bin/aarch64
	INCLUDE_DIR = -I./ -I$(CURRENT_DIR) -I$(FLAME_PATH)/include -I$(FLAME_PATH)/include/dep -I/usr/include -I/usr/local/include -I/opt/pylon/include -I/usr/include/opencv4
	LIBDIR = -L/usr/local/lib -L$(CURRENT_DIR)/lib/aarch64-linux-gnu/
export LD_LIBRARY_PATH := $(LIBDIR):$(LD_LIBRARY_PATH)
else
	CC := g++
	GCC := gcc
#	LD_LIBRARY_PATH += -L./lib/x86_64
	OUTDIR		= $(CURRENT_DIR)/bin/x86_64/
	BUILDDIR	= $(CURRENT_DIR)/bin/x86_64/
	INCLUDE_DIR = -I./ -I$(CURRENT_DIR) -I$(FLAME_PATH)/include -I$(FLAME_PATH)/include/dep -I/usr/include -I/usr/local/include -I/opt/pylon/include -I/usr/include/opencv4
	LIBDIR = -L/usr/local/lib -L$(FLAME_PATH)/lib/x86_64/ -L/opt/pylon/lib/
export LD_LIBRARY_PATH := $(LIBDIR):$(LD_LIBRARY_PATH)
endif

# OS
ifeq ($(OS),Linux) #for Linux
	LDFLAGS = -Wl,--export-dynamic -Wl,-rpath=. $(LIBDIR) -L$(LIBDIR)
	LDLIBS = -pthread -lrt -ldl -lm -lzmq
endif



$(shell mkdir -p $(OUTDIR))
$(shell mkdir -p $(BUILDDIR))
REV_COUNT = $(shell git rev-list --all --count)
MIN_COUNT = $(shell git tag | wc -l)

#if release(-O3), debug(-O0)
# if release mode compile, remove -DNDEBUG
CXXFLAGS = -O3 -fPIC -Wall -std=c++20 -D__cplusplus=202002L

#custom definitions
CXXFLAGS += -D__MAJOR__=0 -D__MINOR__=$(MIN_COUNT) -D__REV__=$(REV_COUNT)
RM	= rm -rf


DK_H_INSPECTOR = $(BUILDDIR)/dk_h_inspector

# flame service engine
flame:	$(BUILDDIR)flame.o \
		$(BUILDDIR)config.o \
		$(BUILDDIR)manager.o \
		$(BUILDDIR)driver.o \
		$(BUILDDIR)instance.o
		$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -o $(BUILDDIR)$@ $^ $(LDLIBS)

$(BUILDDIR)flame.o:	$(FLAME_PATH)/tools/flame/flame.cc
					$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@
$(BUILDDIR)instance.o: $(FLAME_PATH)/tools/flame/instance.cc
						$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@
$(BUILDDIR)manager.o: $(FLAME_PATH)/tools/flame/manager.cc
						$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@
$(BUILDDIR)driver.o: $(INCLUDES)/flame/component/driver.cc
						$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@
$(BUILDDIR)config.o: $(INCLUDES)/flame/config.cc
						$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@


# components
data_push.comp:	$(BUILDDIR)data.push.o
				$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS)
$(BUILDDIR)data.push.o:	$(CURRENT_DIR)/components/data.push/data.push.cc
						$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

data_pull.comp:	$(BUILDDIR)data.pull.o
				$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS)
$(BUILDDIR)data.pull.o:	$(CURRENT_DIR)/components/data.pull/data.pull.cc
						$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

device_uvccam_multi.comp:	$(BUILDDIR)device.uvccam.multi.o
							$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS)
$(BUILDDIR)device.uvccam.multi.o:	$(CURRENT_DIR)/components/device.uvccam.multi/device.uvccam.multi.cc
									$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

# for dk project
basler_gige_cam_linker.comp:	$(BUILDDIR)/basler.gige.cam.linker.o
							$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)/$@ $^ $(LDFLAGS) $(LDLIBS) -lopencv_core -lopencv_imgcodecs -lopencv_highgui -lopencv_imgproc -lpylonbase -lpylonutility 
$(BUILDDIR)/basler.gige.cam.linker.o:	$(CURRENT_DIR)/components/basler.gige.cam.linker/basler.gige.cam.linker.cc
									$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

basler_gige_cam_grabber.comp:	$(BUILDDIR)basler.gige.cam.grabber.o
							$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)/$@ $^ $(LDFLAGS) $(LDLIBS) -lopencv_core -lopencv_imgcodecs -lopencv_highgui -lopencv_imgproc -lpylonbase -lpylonutility 
$(BUILDDIR)basler.gige.cam.grabber.o:	$(CURRENT_DIR)/components/basler.gige.cam.grabber/basler.gige.cam.grabber.cc
									$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

image_flow_handler.comp:	$(BUILDDIR)image.flow.handler.o
							$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDFLAGS) $(LDLIBS) -lopencv_core -lopencv_imgcodecs -lopencv_highgui -lopencv_imgproc -lpylonbase -lpylonutility 
$(BUILDDIR)image.flow.handler.o:	$(CURRENT_DIR)/components/image.flow.handler/image.flow.handler.cc
									$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

dk_gui_supporter.comp:	$(BUILDDIR)dk.gui.supporter.o
						$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS)
$(BUILDDIR)dk.gui.supporter.o:	$(CURRENT_DIR)/components/dk.gui.supporter/dk.gui.supporter.cc
								$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

dk_sdd_inference.comp:	$(BUILDDIR)dk.sdd.inference.o
						$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS)
$(BUILDDIR)dk.sdd.inference.o:	$(CURRENT_DIR)/components/dk.sdd.inference/dk.sdd.inference.cc
								$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

dk_presdd_inference.comp:	$(BUILDDIR)dk.presdd.inference.o
							$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS)
$(BUILDDIR)dk.presdd.inference.o:	$(CURRENT_DIR)/components/dk.presdd.inference/dk.presdd.inference.cc
									$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

dk_sys_op_trigger.comp:	$(BUILDDIR)dk.sys.op.trigger.o
						$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS)
$(BUILDDIR)dk.sys.op.trigger.o:	$(CURRENT_DIR)/components/dk.sys.op.trigger/dk.sys.op.trigger.cc
								$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

synology_nas_file_stacker.comp:	$(BUILDDIR)synology_nas.file.stacker.o
						$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS) -lopencv_core -lopencv_imgcodecs -lopencv_highgui -lopencv_imgproc
$(BUILDDIR)synology.nas.file.stacker.o:	$(CURRENT_DIR)/components/synology.nas.file.stacker/synology.nas.file.stacker.cc
							$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

ni_daq_pulse_generator.comp:	$(BUILDDIR)ni.daq.pulse.generator.o
							$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS) -lnidaqmx
$(BUILDDIR)ni.daq.pulse.generator.o:	$(CURRENT_DIR)/components/ni.daq.pulse.generator/ni.daq.pulse.generator.cc
									$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

ni_daq_controller.comp:	$(BUILDDIR)ni.daq.controller.o
							$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS) -lnidaqmx
$(BUILDDIR)ni.daq.controller.o:	$(CURRENT_DIR)/components/ni.daq.controller/ni.daq.controller.cc
									$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

dk_level2_interface.comp:	$(BUILDDIR)dk.level2.interface.o
							$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS) -lmodbus
$(BUILDDIR)dk.level2.interface.o:	$(CURRENT_DIR)/components/dk.level2.interface/dk.level2.interface.cc
									$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

dk_light_linker.comp:	$(BUILDDIR)dk.light.linker.o
							$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS)
$(BUILDDIR)dk.light.linker.o:	$(CURRENT_DIR)/components/dk.light.linker/dk.light.linker.cc
									$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

# autonics temperature controller component
autonics_temp_controller.comp:	$(BUILDDIR)autonics.temp.controller.o
							$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS) -lmodbus
$(BUILDDIR)autonics.temp.controller.o:	$(CURRENT_DIR)/components/autonics.temp.controller/autonics.temp.controller.cc
									$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

# system status(usage) monitoring component
system_status_monitor.comp:	$(BUILDDIR)system.status.monitor.o
							$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS)
$(BUILDDIR)system.status.monitor.o:	$(CURRENT_DIR)/components/system.status.monitor/system.status.monitor.cc
									$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

# focus lens module controller component
computar_vlmpz_controller.comp:	$(BUILDDIR)computar_vlmpz_controller.o \
									$(BUILDDIR)control_impl.o
									$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS) -lslabhidtosmbus -lslabhiddevice -lusb-1.0 -ludev
$(BUILDDIR)computar_vlmpz_controller.o:	$(CURRENT_DIR)/components/computar.vlmpz.controller/computar.vlmpz.controller.cc
									$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@
$(BUILDDIR)control_impl.o:	$(CURRENT_DIR)/components/computar.vlmpz.controller/control_impl.cc
									$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@
# $(BUILDDIR)UsbCtrl.o:$(CURRENT_DIR)/components/computar.vlmpz.controller/include/UsbCtrl.c 
# 					$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -I./ -c $^ -o $@
# $(BUILDDIR)LensCtrl.o:$(CURRENT_DIR)/components/computar.vlmpz.controller/include/LensCtrl.c 
# 					$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -I./ -c $^ -o $@
# $(BUILDDIR)LensAccess.o:$(CURRENT_DIR)/components/computar.vlmpz.controller/include/LensAccess.c 
# 					$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -I./ -c $^ -o $@
# $(BUILDDIR)LensConnect.o:$(CURRENT_DIR)/components/computar.vlmpz.controller/include/LensConnect.c 
# 					$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -I./ -c $^ -o $@


# dk_remote_lens_linker.comp:	$(BUILDDIR)dk.remote.lens.linker.o \
# 							$(BUILDDIR)UsbCtrl.o \
# 							$(BUILDDIR)LensCtrl.o \
# 							$(BUILDDIR)LensAccess.o \
# 							$(BUILDDIR)LensConnect.o
# 							$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS) -lslabhidtosmbus -lslabhiddevice -lusb-1.0 -ludev
# $(BUILDDIR)dk.remote.lens.linker.o:	$(CURRENT_DIR)/components/dk.remote.lens.linker/dk.remote.lens.linker.cc
# 									$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@
# $(BUILDDIR)UsbCtrl.o:$(CURRENT_DIR)/components/dk.remote.lens.linker/controller/UsbCtrl.c 
# 					$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -I./ -c $^ -o $@
# $(BUILDDIR)LensCtrl.o:$(CURRENT_DIR)/components/dk.remote.lens.linker/controller/LensCtrl.c 
# 					$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -I./ -c $^ -o $@
# $(BUILDDIR)LensAccess.o:$(CURRENT_DIR)/components/dk.remote.lens.linker/controller/LensAccess.c 
# 					$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -I./ -c $^ -o $@
# $(BUILDDIR)LensConnect.o:$(CURRENT_DIR)/components/dk.remote.lens.linker/controller/LensConnect.c 
# 					$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -I./ -c $^ -o $@

dk_image_push_unittest.comp:	$(BUILDDIR)dk.image.push.unittest.o
							$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDFLAGS) $(LDLIBS)
$(BUILDDIR)dk.image.push.unittest.o:	$(CURRENT_DIR)/components/dk.image.push.unittest/dk.image.push.unittest.cc
									$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@


all : flame

dk_h_inspector : flame basler_gige_cam_grabber.comp synology_nas_file_stacker.comp ni_daq_pulse_generator.comp ni_daq_controller.comp dk_level2_interface.comp

dk_h_inspector_onsite : flame system_status_monitor.comp autonics_temp_controller.comp computar_vlmpz_controller.comp

deploy : FORCE
	cp $(BUILDDIR)/*.comp $(BUILDDIR)/flame $(BINDIR)
clean : FORCE 
		$(RM) $(BUILDDIR)/*.o $(BUILDDIR)/*.comp $(BUILDDIR)/flame
debug:
	@echo "Building for Architecture : $(ARCH)"
	@echo "Building for OS : $(OS)"

FORCE : 