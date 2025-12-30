CXX := g++
CXXFLAGS := -std=c++17 -O2 -Wall -Wextra

TARGET := target_dirname_regex
SRC := target_dirname_regex.cc

all: $(TARGET)

$(TARGET): $(SRC)
	$(CXX) $(CXXFLAGS) -o $@ $^

clean:
	rm -f $(TARGET)
