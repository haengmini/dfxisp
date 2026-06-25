CXX ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -Werror -Wno-unknown-pragmas -Iinclude

BUILD_DIR := build
CSIM_BIN := $(BUILD_DIR)/dfxisp_csim

.PHONY: all csim clean

all: csim

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(CSIM_BIN): src/dfxisp_accel.cpp tests/test_dfxisp_csim.cpp include/dfxisp_accel.hpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) src/dfxisp_accel.cpp tests/test_dfxisp_csim.cpp -o $(CSIM_BIN)

csim: $(CSIM_BIN)
	./$(CSIM_BIN)

clean:
	rm -rf $(BUILD_DIR)
