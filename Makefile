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
	CC := g++
	GCC := gcc
	LD_LIBRARY_PATH += -L./lib/arm64
	OUTDIR		= $(CURRENT_DIR)/bin/arm64/
	BUILDDIR	= $(CURRENT_DIR)/bin/arm64/
	INCLUDE_DIR = -I./ -I$(CURRENT_DIR)/ -I$(CURRENT_DIR)/include/ -I$(CURRENT_DIR)/include/dep -I/usr/include
	LD_LIBRARY_PATH += -L/usr/local/lib -L./lib/arm64/
else ifeq ($(ARCH), armhf)
	CC := /usr/bin/arm-linux-gnueabihf-g++-9
	GCC := /usr/bin/arm-linux-gnueabihf-gcc-9
	LD_LIBRARY_PATH += -L./lib/armhf
	OUTDIR		= $(CURRENT_DIR)/bin/armhf/
	BUILDDIR	= $(CURRENT_DIR)/bin/armhf/
	INCLUDE_DIR = -I./ -I$(CURRENT_DIR)/ -I$(CURRENT_DIR)/include/ -I$(CURRENT_DIR)/include/dep -I/usr/include
	LD_LIBRARY_PATH += -L/usr/local/lib -L./lib/armhf/
else ifeq ($(ARCH), aarch64) # for Mac Apple Silicon
	CC := g++
	GCC := gcc
#	LD_LIBRARY_PATH += -L./lib/aarch64-linux-gnu
	OUTDIR		= $(CURRENT_DIR)/bin/aarch64/
	BUILDDIR	= $(CURRENT_DIR)/bin/aarch64/
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
MIN_COUNT = 0 #$(shell git tag | wc -l)

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

# for test

test_image_pusher.comp:	$(BUILDDIR)test.image.pusher.o
							$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)/$@ $^ $(LDFLAGS) $(LDLIBS) -lopencv_core -lopencv_imgcodecs -lopencv_highgui -lopencv_imgproc
$(BUILDDIR)test.image.pusher.o:	$(CURRENT_DIR)/components/test.image.pusher/test.image.pusher.cc
									$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

# for dk project

basler_gige_cam_grabber.comp:	$(BUILDDIR)basler.gige.cam.grabber.o
							$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)/$@ $^ $(LDFLAGS) $(LDLIBS) -lopencv_core -lopencv_imgcodecs -lopencv_highgui -lopencv_imgproc -lpylonbase -lpylonutility 
$(BUILDDIR)basler.gige.cam.grabber.o:	$(CURRENT_DIR)/components/basler.gige.cam.grabber/basler.gige.cam.grabber.cc
									$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

dk_sdd_inference.comp:	$(BUILDDIR)dk.sdd.inference.o
						$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS)
$(BUILDDIR)dk.sdd.inference.o:	$(CURRENT_DIR)/components/dk.sdd.inference/dk.sdd.inference.cc
								$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

synology_nas_file_stacker.comp:	$(BUILDDIR)synology.nas.file.stacker.o
						$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS) -lopencv_core -lopencv_imgcodecs -lopencv_highgui -lopencv_imgproc
$(BUILDDIR)synology.nas.file.stacker.o:	$(CURRENT_DIR)/components/synology.nas.file.stacker/synology.nas.file.stacker.cc
							$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

general_file_stacker.comp:	$(BUILDDIR)general.file.stacker.o
						$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS) -lopencv_core -lopencv_imgcodecs -lopencv_highgui -lopencv_imgproc
$(BUILDDIR)general.file.stacker.o:	$(CURRENT_DIR)/components/general.file.stacker/general.file.stacker.cc
							$(CC) $(CXXFLAGS) $(INCLUDE_DIR) -c $^ -o $@

dummy_image_pusher.comp:	$(BUILDDIR)dummy.image.pusher.o
						$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS) -lopencv_core -lopencv_imgcodecs -lopencv_highgui -lopencv_imgproc
$(BUILDDIR)dummy.image.pusher.o:	$(CURRENT_DIR)/components/dummy.image.pusher/dummy.image.pusher.cc
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

system_echo_replier.comp:	$(BUILDDIR)system.echo.replier.o
							$(CC) $(LDFLAGS) $(LD_LIBRARY_PATH) -shared -o $(BUILDDIR)$@ $^ $(LDLIBS)
$(BUILDDIR)system.echo.replier.o:	$(CURRENT_DIR)/components/system.echo.replier/system.echo.replier.cc
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


all : flame

dk_h_inspector : flame basler_gige_cam_grabber.comp synology_nas_file_stacker.comp ni_daq_controller.comp dk_level2_interface.comp general_file_stacker.comp dummy_image_pusher.comp system_echo_replier.comp

dk_h_inspector_onsite : flame autonics_temp_controller.comp computar_vlmpz_controller.comp

deploy : FORCE
	cp $(BUILDDIR)/*.comp $(BUILDDIR)/flame $(BINDIR)
clean : FORCE 
		$(RM) $(BUILDDIR)/*.o $(BUILDDIR)/*.comp $(BUILDDIR)/flame
debug:
	@echo "Building for Architecture : $(ARCH)"
	@echo "Building for OS : $(OS)"

FORCE : 