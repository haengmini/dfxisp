CXX ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -Werror -Wno-unknown-pragmas -Iinclude
PYTHON ?= python3
VITIS_HLS ?= vitis_hls
DFXISP_HLS_FLOW ?= csim
DFXISP_HLS_TOP ?= dfxisp_accel
DFXISP_HLS_PART ?= xczu7ev-ffvc1156-2-e
DFXISP_HLS_CLOCK ?= 5.0
DFXISP_HLS_PROJECT ?= $(BUILD_DIR)/vitis_hls/$(DFXISP_HLS_TOP)

BUILD_DIR := build
CSIM_BIN := $(BUILD_DIR)/dfxisp_csim
HLS_TCL := scripts/vitis_hls.tcl
GOLDEN_CSV := tests/golden_vectors.csv
RM_GOLDEN_CSV := tests/rm_golden_vectors.csv
RM_CSIM_BIN := $(BUILD_DIR)/dfxisp_rm_csim
REPORT_MD := reports/latest.md
HLS_SRC := src/dfxisp_accel.cpp include/dfxisp_accel.hpp
HLS_TB := tests/test_dfxisp_csim.cpp $(GOLDEN_CSV)

.PHONY: all csim golden verify report hls-report hls rm-golden rm-csim rm-verify scheduler analysis sw-stage clean

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

report: golden $(CSIM_BIN)
	$(PYTHON) tools/gen_verification_report.py --out $(REPORT_MD)

hls-report:
	@printf '%s\n' 'DFXISP Vitis HLS dry-run report'
	@printf '  top     : %s\n' '$(DFXISP_HLS_TOP)'
	@printf '  project : %s\n' '$(DFXISP_HLS_PROJECT)'
	@printf '  part    : %s\n' '$(DFXISP_HLS_PART)'
	@printf '  clock   : %s ns\n' '$(DFXISP_HLS_CLOCK)'
	@printf '  flow    : %s\n' '$(DFXISP_HLS_FLOW)'
	@printf '  tcl     : %s\n' '$(HLS_TCL)'
	@printf '  sources : %s\n' '$(HLS_SRC)'
	@printf '  testbench: %s\n' '$(HLS_TB)'
	@printf '%s\n' '  expected outputs:'
	@printf '    local csim binary : %s\n' '$(CSIM_BIN)'
	@printf '    golden vectors    : %s\n' '$(GOLDEN_CSV)'
	@printf '    HLS project       : %s\n' '$(DFXISP_HLS_PROJECT)'
	@printf '    csim log          : %s/solution1/csim/report/$(DFXISP_HLS_TOP)_csim.log\n' '$(DFXISP_HLS_PROJECT)'
	@printf '    synthesis report  : %s/solution1/syn/report/$(DFXISP_HLS_TOP)_csynth.rpt (for csynth/cosim/export)\n' '$(DFXISP_HLS_PROJECT)'
	@printf '    exported IP       : %s/solution1/impl/export.zip (for export)\n' '$(DFXISP_HLS_PROJECT)'
	@printf '%s\n' '  note: dry-run only; vitis_hls is not invoked.'

hls:
	@if ! command -v $(VITIS_HLS) >/dev/null 2>&1; then \
		echo "ERROR: $(VITIS_HLS) not found. Install/source Vitis HLS, or set VITIS_HLS=/path/to/vitis_hls." >&2; \
		exit 127; \
	fi
	DFXISP_HLS_PROJECT=$(DFXISP_HLS_PROJECT) DFXISP_HLS_PART=$(DFXISP_HLS_PART) DFXISP_HLS_CLOCK=$(DFXISP_HLS_CLOCK) DFXISP_HLS_FLOW=$(DFXISP_HLS_FLOW) $(VITIS_HLS) -f $(HLS_TCL)

rm-golden:
	$(PYTHON) tools/gen_rm_golden.py --out $(RM_GOLDEN_CSV)

$(RM_CSIM_BIN): src/dfxisp_rm.cpp tests/test_rm_csim.cpp include/dfxisp_rm.hpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) src/dfxisp_rm.cpp tests/test_rm_csim.cpp -o $(RM_CSIM_BIN)

rm-csim: $(RM_CSIM_BIN)
	./$(RM_CSIM_BIN) $(RM_GOLDEN_CSV)

rm-verify: rm-golden rm-csim

scheduler: | $(BUILD_DIR)
	$(PYTHON) tools/scheduler_sim.py --out results/scheduler.csv

analysis: | $(BUILD_DIR)
	$(PYTHON) tools/isp_variant_analysis.py --out results/isp_analysis.csv

# Full software stage (no board): variants bit-exact + scheduler + ISP analysis.
sw-stage: verify rm-verify scheduler analysis

clean:
	rm -rf $(BUILD_DIR)
