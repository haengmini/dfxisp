CXX ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -Werror -Wno-unknown-pragmas -Iinclude
PYTHON ?= python3
VITIS_HLS ?= vitis_hls
DFXISP_HLS_FLOW ?= csim

BUILD_DIR := build
CSIM_BIN := $(BUILD_DIR)/dfxisp_csim
HLS_TCL := scripts/vitis_hls.tcl
GOLDEN_CSV := tests/golden_vectors.csv

.PHONY: all csim golden verify hls clean

all: csim

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(CSIM_BIN): src/dfxisp_accel.cpp tests/test_dfxisp_csim.cpp include/dfxisp_accel.hpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) src/dfxisp_accel.cpp tests/test_dfxisp_csim.cpp -o $(CSIM_BIN)

csim: $(CSIM_BIN)
	./$(CSIM_BIN)

golden:
	$(PYTHON) tools/gen_golden_vectors.py --out $(GOLDEN_CSV)

verify: golden csim

hls:
	@if ! command -v $(VITIS_HLS) >/dev/null 2>&1; then \
		echo "ERROR: $(VITIS_HLS) not found. Install/source Vitis HLS, or set VITIS_HLS=/path/to/vitis_hls." >&2; \
		exit 127; \
	fi
	DFXISP_HLS_FLOW=$(DFXISP_HLS_FLOW) $(VITIS_HLS) -f $(HLS_TCL)

clean:
	rm -rf $(BUILD_DIR)
