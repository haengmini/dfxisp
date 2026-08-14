set SynModuleInfo {
  {SRCNAME checker_scan_Pipeline_VITIS_LOOP_38_1 MODELNAME checker_scan_Pipeline_VITIS_LOOP_38_1 RTLNAME checker_scan_checker_scan_Pipeline_VITIS_LOOP_38_1
    SUBMODULES {
      {MODELNAME checker_scan_flow_control_loop_pipe_sequential_init RTLNAME checker_scan_flow_control_loop_pipe_sequential_init BINDTYPE interface TYPE internal_upc_flow_control INSTNAME checker_scan_flow_control_loop_pipe_sequential_init_U}
    }
  }
  {SRCNAME checker_scan MODELNAME checker_scan RTLNAME checker_scan IS_TOP 1
    SUBMODULES {
      {MODELNAME checker_scan_mul_32s_32s_32_1_1 RTLNAME checker_scan_mul_32s_32s_32_1_1 BINDTYPE op TYPE mul IMPL auto LATENCY 0 ALLOW_PRAGMA 1}
      {MODELNAME checker_scan_gmem0_m_axi RTLNAME checker_scan_gmem0_m_axi BINDTYPE interface TYPE adapter IMPL m_axi}
      {MODELNAME checker_scan_control_s_axi RTLNAME checker_scan_control_s_axi BINDTYPE interface TYPE interface_s_axilite}
    }
  }
}
