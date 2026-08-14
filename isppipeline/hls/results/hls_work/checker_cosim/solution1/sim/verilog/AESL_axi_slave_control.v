// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.1 (64-bit)
// Tool Version Limit: 2024.05
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================

`timescale 1 ns / 1 ps

module AESL_axi_slave_control (
    clk,
    reset,
    TRAN_s_axi_control_AWADDR,
    TRAN_s_axi_control_AWVALID,
    TRAN_s_axi_control_AWREADY,
    TRAN_s_axi_control_WVALID,
    TRAN_s_axi_control_WREADY,
    TRAN_s_axi_control_WDATA,
    TRAN_s_axi_control_WSTRB,
    TRAN_s_axi_control_ARADDR,
    TRAN_s_axi_control_ARVALID,
    TRAN_s_axi_control_ARREADY,
    TRAN_s_axi_control_RVALID,
    TRAN_s_axi_control_RREADY,
    TRAN_s_axi_control_RDATA,
    TRAN_s_axi_control_RRESP,
    TRAN_s_axi_control_BVALID,
    TRAN_s_axi_control_BREADY,
    TRAN_s_axi_control_BRESP,
    TRAN_control_write_data_finish,
    TRAN_control_read_data_finish,
    TRAN_control_start_in,
    TRAN_control_idle_out,
    TRAN_control_ready_out,
    TRAN_control_ready_in,
    TRAN_control_done_out,
    TRAN_control_write_start_in   ,
    TRAN_control_write_start_finish,
    TRAN_control_interrupt,
    TRAN_control_transaction_done_in
    );

//------------------------Parameter----------------------
`define TV_IN_raw_bayer "../tv/cdatafile/c.checker_scan.autotvin_raw_bayer.dat"
`define TV_IN_width "../tv/cdatafile/c.checker_scan.autotvin_width.dat"
`define TV_IN_height "../tv/cdatafile/c.checker_scan.autotvin_height.dat"
`define TV_IN_mode "../tv/cdatafile/c.checker_scan.autotvin_mode.dat"
`define TV_IN_dark_pixel_threshold "../tv/cdatafile/c.checker_scan.autotvin_dark_pixel_threshold.dat"
`define TV_IN_verdict_pct "../tv/cdatafile/c.checker_scan.autotvin_verdict_pct.dat"
`define TV_IN_enter_pct "../tv/cdatafile/c.checker_scan.autotvin_enter_pct.dat"
`define TV_IN_exit_pct "../tv/cdatafile/c.checker_scan.autotvin_exit_pct.dat"
`define TV_OUT_selected_mode "../tv/rtldatafile/rtl.checker_scan.autotvout_selected_mode.dat"
`define TV_OUT_dark_count "../tv/rtldatafile/rtl.checker_scan.autotvout_dark_count.dat"
parameter ADDR_WIDTH = 7;
parameter DATA_WIDTH = 32;
parameter raw_bayer_DEPTH = 1;
reg [31 : 0] raw_bayer_OPERATE_DEPTH = 0;
parameter raw_bayer_c_bitwidth = 64;
parameter width_DEPTH = 1;
reg [31 : 0] width_OPERATE_DEPTH = 0;
parameter width_c_bitwidth = 32;
parameter height_DEPTH = 1;
reg [31 : 0] height_OPERATE_DEPTH = 0;
parameter height_c_bitwidth = 32;
parameter mode_DEPTH = 1;
reg [31 : 0] mode_OPERATE_DEPTH = 0;
parameter mode_c_bitwidth = 32;
parameter dark_pixel_threshold_DEPTH = 1;
reg [31 : 0] dark_pixel_threshold_OPERATE_DEPTH = 0;
parameter dark_pixel_threshold_c_bitwidth = 16;
parameter verdict_pct_DEPTH = 1;
reg [31 : 0] verdict_pct_OPERATE_DEPTH = 0;
parameter verdict_pct_c_bitwidth = 32;
parameter enter_pct_DEPTH = 1;
reg [31 : 0] enter_pct_OPERATE_DEPTH = 0;
parameter enter_pct_c_bitwidth = 32;
parameter exit_pct_DEPTH = 1;
reg [31 : 0] exit_pct_OPERATE_DEPTH = 0;
parameter exit_pct_c_bitwidth = 32;
parameter selected_mode_DEPTH = 1;
reg [31 : 0] selected_mode_OPERATE_DEPTH = 0;
parameter selected_mode_c_bitwidth = 32;
parameter dark_count_DEPTH = 1;
reg [31 : 0] dark_count_OPERATE_DEPTH = 0;
parameter dark_count_c_bitwidth = 32;
parameter START_ADDR = 0;
parameter checker_scan_continue_addr = 0;
parameter checker_scan_auto_start_addr = 0;
parameter raw_bayer_data_in_addr = 16;
parameter width_data_in_addr = 28;
parameter height_data_in_addr = 36;
parameter mode_data_in_addr = 44;
parameter dark_pixel_threshold_data_in_addr = 52;
parameter verdict_pct_data_in_addr = 60;
parameter enter_pct_data_in_addr = 68;
parameter exit_pct_data_in_addr = 76;
parameter selected_mode_data_out_addr = 84;
parameter selected_mode_valid_out_addr = 88;
parameter dark_count_data_out_addr = 100;
parameter dark_count_valid_out_addr = 104;
parameter STATUS_ADDR = 0;

output [ADDR_WIDTH - 1 : 0] TRAN_s_axi_control_AWADDR;
output  TRAN_s_axi_control_AWVALID;
input  TRAN_s_axi_control_AWREADY;
output  TRAN_s_axi_control_WVALID;
input  TRAN_s_axi_control_WREADY;
output [DATA_WIDTH - 1 : 0] TRAN_s_axi_control_WDATA;
output [DATA_WIDTH/8 - 1 : 0] TRAN_s_axi_control_WSTRB;
output [ADDR_WIDTH - 1 : 0] TRAN_s_axi_control_ARADDR;
output  TRAN_s_axi_control_ARVALID;
input  TRAN_s_axi_control_ARREADY;
input  TRAN_s_axi_control_RVALID;
output  TRAN_s_axi_control_RREADY;
input [DATA_WIDTH - 1 : 0] TRAN_s_axi_control_RDATA;
input [2 - 1 : 0] TRAN_s_axi_control_RRESP;
input  TRAN_s_axi_control_BVALID;
output  TRAN_s_axi_control_BREADY;
input [2 - 1 : 0] TRAN_s_axi_control_BRESP;
output TRAN_control_write_data_finish;
output TRAN_control_read_data_finish;
input     clk;
input     reset;
input     TRAN_control_start_in;
output    TRAN_control_done_out;
output    TRAN_control_ready_out;
input     TRAN_control_ready_in;
output    TRAN_control_idle_out;
input  TRAN_control_write_start_in   ;
output TRAN_control_write_start_finish;
input     TRAN_control_interrupt;
input     TRAN_control_transaction_done_in;

reg [ADDR_WIDTH - 1 : 0] AWADDR_reg = 0;
reg  AWVALID_reg = 0;
reg  WVALID_reg = 0;
reg [DATA_WIDTH - 1 : 0] WDATA_reg = 0;
reg [DATA_WIDTH/8 - 1 : 0] WSTRB_reg = 0;
reg [ADDR_WIDTH - 1 : 0] ARADDR_reg = 0;
reg  ARVALID_reg = 0;
reg  RREADY_reg = 0;
reg [DATA_WIDTH - 1 : 0] RDATA_reg = 0;
reg  BREADY_reg = 0;
reg [raw_bayer_c_bitwidth - 1 : 0] mem_raw_bayer [raw_bayer_DEPTH - 1 : 0] = '{default : 'h0};
reg [DATA_WIDTH-1 : 0] image_mem_raw_bayer [ (raw_bayer_c_bitwidth+DATA_WIDTH-1)/DATA_WIDTH * raw_bayer_DEPTH -1 : 0] = '{default : 'hz};
reg raw_bayer_write_data_finish;
reg [DATA_WIDTH - 1 : 0] mem_width [width_DEPTH - 1 : 0] = '{default : 'h0};
reg [DATA_WIDTH-1 : 0] image_mem_width [ (width_c_bitwidth+DATA_WIDTH-1)/DATA_WIDTH * width_DEPTH -1 : 0] = '{default : 'hz};
reg width_write_data_finish;
reg [DATA_WIDTH - 1 : 0] mem_height [height_DEPTH - 1 : 0] = '{default : 'h0};
reg [DATA_WIDTH-1 : 0] image_mem_height [ (height_c_bitwidth+DATA_WIDTH-1)/DATA_WIDTH * height_DEPTH -1 : 0] = '{default : 'hz};
reg height_write_data_finish;
reg [DATA_WIDTH - 1 : 0] mem_mode [mode_DEPTH - 1 : 0] = '{default : 'h0};
reg [DATA_WIDTH-1 : 0] image_mem_mode [ (mode_c_bitwidth+DATA_WIDTH-1)/DATA_WIDTH * mode_DEPTH -1 : 0] = '{default : 'hz};
reg mode_write_data_finish;
reg [DATA_WIDTH - 1 : 0] mem_dark_pixel_threshold [dark_pixel_threshold_DEPTH - 1 : 0] = '{default : 'h0};
reg [DATA_WIDTH-1 : 0] image_mem_dark_pixel_threshold [ (dark_pixel_threshold_c_bitwidth+DATA_WIDTH-1)/DATA_WIDTH * dark_pixel_threshold_DEPTH -1 : 0] = '{default : 'hz};
reg dark_pixel_threshold_write_data_finish;
reg [DATA_WIDTH - 1 : 0] mem_verdict_pct [verdict_pct_DEPTH - 1 : 0] = '{default : 'h0};
reg [DATA_WIDTH-1 : 0] image_mem_verdict_pct [ (verdict_pct_c_bitwidth+DATA_WIDTH-1)/DATA_WIDTH * verdict_pct_DEPTH -1 : 0] = '{default : 'hz};
reg verdict_pct_write_data_finish;
reg [DATA_WIDTH - 1 : 0] mem_enter_pct [enter_pct_DEPTH - 1 : 0] = '{default : 'h0};
reg [DATA_WIDTH-1 : 0] image_mem_enter_pct [ (enter_pct_c_bitwidth+DATA_WIDTH-1)/DATA_WIDTH * enter_pct_DEPTH -1 : 0] = '{default : 'hz};
reg enter_pct_write_data_finish;
reg [DATA_WIDTH - 1 : 0] mem_exit_pct [exit_pct_DEPTH - 1 : 0] = '{default : 'h0};
reg [DATA_WIDTH-1 : 0] image_mem_exit_pct [ (exit_pct_c_bitwidth+DATA_WIDTH-1)/DATA_WIDTH * exit_pct_DEPTH -1 : 0] = '{default : 'hz};
reg exit_pct_write_data_finish;
reg [DATA_WIDTH - 1 : 0] mem_selected_mode [selected_mode_DEPTH - 1 : 0] = '{default : 'h0};
reg [DATA_WIDTH-1 : 0] image_mem_selected_mode [ (selected_mode_c_bitwidth+DATA_WIDTH-1)/DATA_WIDTH * selected_mode_DEPTH -1 : 0] = '{default : 'hz};
reg selected_mode_read_data_finish;
reg [DATA_WIDTH - 1 : 0] mem_dark_count [dark_count_DEPTH - 1 : 0] = '{default : 'h0};
reg [DATA_WIDTH-1 : 0] image_mem_dark_count [ (dark_count_c_bitwidth+DATA_WIDTH-1)/DATA_WIDTH * dark_count_DEPTH -1 : 0] = '{default : 'hz};
reg dark_count_read_data_finish;
reg AESL_ready_out_index_reg = 0;
reg AESL_write_start_finish = 0;
reg AESL_ready_reg;
reg ready_initial;
reg AESL_done_index_reg = 0;
reg AESL_idle_index_reg = 0;
reg AESL_auto_restart_index_reg;
reg process_0_finish = 0;
reg process_1_finish = 0;
reg process_2_finish = 0;
reg process_3_finish = 0;
reg process_4_finish = 0;
reg process_5_finish = 0;
reg process_6_finish = 0;
reg process_7_finish = 0;
reg process_8_finish = 0;
reg process_9_finish = 0;
reg process_10_finish = 0;
reg process_11_finish = 0;
//write raw_bayer reg
reg [31 : 0] write_raw_bayer_count = 0;
reg [31 : 0] raw_bayer_diff_count = 0;
reg write_raw_bayer_run_flag = 0;
reg write_one_raw_bayer_data_done = 0;
//write width reg
reg [31 : 0] write_width_count = 0;
reg [31 : 0] width_diff_count = 0;
reg write_width_run_flag = 0;
reg write_one_width_data_done = 0;
//write height reg
reg [31 : 0] write_height_count = 0;
reg [31 : 0] height_diff_count = 0;
reg write_height_run_flag = 0;
reg write_one_height_data_done = 0;
//write mode reg
reg [31 : 0] write_mode_count = 0;
reg [31 : 0] mode_diff_count = 0;
reg write_mode_run_flag = 0;
reg write_one_mode_data_done = 0;
//write dark_pixel_threshold reg
reg [31 : 0] write_dark_pixel_threshold_count = 0;
reg [31 : 0] dark_pixel_threshold_diff_count = 0;
reg write_dark_pixel_threshold_run_flag = 0;
reg write_one_dark_pixel_threshold_data_done = 0;
//write verdict_pct reg
reg [31 : 0] write_verdict_pct_count = 0;
reg [31 : 0] verdict_pct_diff_count = 0;
reg write_verdict_pct_run_flag = 0;
reg write_one_verdict_pct_data_done = 0;
//write enter_pct reg
reg [31 : 0] write_enter_pct_count = 0;
reg [31 : 0] enter_pct_diff_count = 0;
reg write_enter_pct_run_flag = 0;
reg write_one_enter_pct_data_done = 0;
//write exit_pct reg
reg [31 : 0] write_exit_pct_count = 0;
reg [31 : 0] exit_pct_diff_count = 0;
reg write_exit_pct_run_flag = 0;
reg write_one_exit_pct_data_done = 0;
//read selected_mode reg
reg [31 : 0] read_selected_mode_count = 0;
reg read_selected_mode_run_flag = 0;
reg read_one_selected_mode_data_done = 0;
//read dark_count reg
reg [31 : 0] read_dark_count_count = 0;
reg read_dark_count_run_flag = 0;
reg read_one_dark_count_data_done = 0;
reg [31 : 0] write_start_count = 0;
reg write_start_run_flag = 0;

//===================process control=================
reg [31 : 0] ongoing_process_number = 0;
//process number depends on how much processes needed.
reg process_busy = 0;

//=================== signal connection ==============
assign TRAN_s_axi_control_AWADDR = AWADDR_reg;
assign TRAN_s_axi_control_AWVALID = AWVALID_reg;
assign TRAN_s_axi_control_WVALID = WVALID_reg;
assign TRAN_s_axi_control_WDATA = WDATA_reg;
assign TRAN_s_axi_control_WSTRB = WSTRB_reg;
assign TRAN_s_axi_control_ARADDR = ARADDR_reg;
assign TRAN_s_axi_control_ARVALID = ARVALID_reg;
assign TRAN_s_axi_control_RREADY = RREADY_reg;
assign TRAN_s_axi_control_BREADY = BREADY_reg;
assign TRAN_control_write_start_finish = AESL_write_start_finish;
assign TRAN_control_done_out = AESL_done_index_reg;
assign TRAN_control_ready_out = AESL_ready_out_index_reg;
assign TRAN_control_idle_out = AESL_idle_index_reg;
assign TRAN_control_read_data_finish = 1 & selected_mode_read_data_finish & dark_count_read_data_finish;
assign TRAN_control_write_data_finish = 1 & raw_bayer_write_data_finish & width_write_data_finish & height_write_data_finish & mode_write_data_finish & dark_pixel_threshold_write_data_finish & verdict_pct_write_data_finish & enter_pct_write_data_finish & exit_pct_write_data_finish;
always @(TRAN_control_ready_in or ready_initial) 
begin
    AESL_ready_reg <= TRAN_control_ready_in | ready_initial;
end

always @(reset or process_0_finish or process_1_finish or process_2_finish or process_3_finish or process_4_finish or process_5_finish or process_6_finish or process_7_finish or process_8_finish or process_9_finish or process_10_finish or process_11_finish ) begin
    if (reset == 0) begin
        ongoing_process_number <= 0;
    end
    else if (ongoing_process_number == 0 && process_0_finish == 1) begin
            ongoing_process_number <= ongoing_process_number + 1;
    end
    else if (ongoing_process_number == 1 && process_1_finish == 1) begin
            ongoing_process_number <= ongoing_process_number + 1;
    end
    else if (ongoing_process_number == 2 && process_2_finish == 1) begin
            ongoing_process_number <= ongoing_process_number + 1;
    end
    else if (ongoing_process_number == 3 && process_3_finish == 1) begin
            ongoing_process_number <= ongoing_process_number + 1;
    end
    else if (ongoing_process_number == 4 && process_4_finish == 1) begin
            ongoing_process_number <= ongoing_process_number + 1;
    end
    else if (ongoing_process_number == 5 && process_5_finish == 1) begin
            ongoing_process_number <= ongoing_process_number + 1;
    end
    else if (ongoing_process_number == 6 && process_6_finish == 1) begin
            ongoing_process_number <= ongoing_process_number + 1;
    end
    else if (ongoing_process_number == 7 && process_7_finish == 1) begin
            ongoing_process_number <= ongoing_process_number + 1;
    end
    else if (ongoing_process_number == 8 && process_8_finish == 1) begin
            ongoing_process_number <= ongoing_process_number + 1;
    end
    else if (ongoing_process_number == 9 && process_9_finish == 1) begin
            ongoing_process_number <= ongoing_process_number + 1;
    end
    else if (ongoing_process_number == 10 && process_10_finish == 1) begin
            ongoing_process_number <= ongoing_process_number + 1;
    end
    else if (ongoing_process_number == 11 && process_11_finish == 1) begin
            ongoing_process_number <= 0;
    end
end

task count_c_data_four_byte_num_by_bitwidth;
input  integer bitwidth;
output integer num;
integer factor;
integer i;
begin
    factor = 32;
    for (i = 1; i <= 1024; i = i + 1) begin
        if (bitwidth <= factor && bitwidth > factor - 32) begin
            num = i;
        end
        factor = factor + 32;
    end
end    
endtask

function integer ceil_align_to_pow_of_two;
input integer a;
begin
    ceil_align_to_pow_of_two = $pow(2,$clog2(a));
end
endfunction

task count_seperate_factor_by_bitwidth;
input  integer bitwidth;
output integer factor;
begin
    if (bitwidth <= 8) begin
        factor=4;
    end
    if (bitwidth <= 16 & bitwidth > 8 ) begin
        factor=2;
    end
    if (bitwidth <= 32 & bitwidth > 16 ) begin
        factor=1;
    end
    if (bitwidth > 32 ) begin
        factor=1;
    end
end    
endtask

task count_operate_depth_by_bitwidth_and_depth;
input  integer bitwidth;
input  integer depth;
output integer operate_depth;
integer factor;
integer remain;
begin
    count_seperate_factor_by_bitwidth (bitwidth , factor);
    operate_depth = depth / factor;
    remain = depth % factor;
    if (remain > 0) begin
        operate_depth = operate_depth + 1;
    end
end    
endtask

task write; /*{{{*/
    input  reg [ADDR_WIDTH - 1:0] waddr;   // write address
    input  reg [DATA_WIDTH - 1:0] wdata;   // write data
    output reg wresp;
    reg aw_flag;
    reg w_flag;
    reg [DATA_WIDTH/8 - 1:0] wstrb_reg;
    integer i;
begin 
    wresp = 0;
    aw_flag = 0;
    w_flag = 0;
//=======================one single write operate======================
    AWADDR_reg <= waddr;
    AWVALID_reg <= 1;
    WDATA_reg <= wdata;
    WVALID_reg <= 1;
    for (i = 0; i < DATA_WIDTH/8; i = i + 1) begin
        wstrb_reg [i] = 1;
    end    
    WSTRB_reg <= wstrb_reg;
    while (!(aw_flag && w_flag)) begin
        @(posedge clk);
        if (aw_flag != 1)
            aw_flag = TRAN_s_axi_control_AWREADY & AWVALID_reg;
        if (w_flag != 1)
            w_flag = TRAN_s_axi_control_WREADY & WVALID_reg;
        AWVALID_reg <= !aw_flag;
        WVALID_reg <= !w_flag;
    end

    BREADY_reg <= 1;
    while (TRAN_s_axi_control_BVALID != 1) begin
        //wait for response 
        @(posedge clk);
    end
    @(posedge clk);
    BREADY_reg <= 0;
    if (TRAN_s_axi_control_BRESP === 2'b00) begin
        wresp = 1;
        //input success. in fact BRESP is always 2'b00
    end   
//=======================one single write operate======================

end
endtask/*}}}*/

task read (/*{{{*/
    input  [ADDR_WIDTH - 1:0] raddr ,   // write address
    output [DATA_WIDTH - 1:0] RDATA_result ,
    output rresp
);
begin 
    rresp = 0;
//=======================one single read operate======================
    ARADDR_reg <= raddr;
    ARVALID_reg <= 1;
    while (TRAN_s_axi_control_ARREADY !== 1) begin
        @(posedge clk);
    end
    @(posedge clk);
    ARVALID_reg <= 0;
    RREADY_reg <= 1;
    while (TRAN_s_axi_control_RVALID !== 1) begin
        //wait for response 
        @(posedge clk);
    end
    @(posedge clk);
    RDATA_result  <= TRAN_s_axi_control_RDATA;
    RREADY_reg <= 0;
    if (TRAN_s_axi_control_RRESP === 2'b00 ) begin
        rresp <= 1;
        //output success. in fact RRESP is always 2'b00
    end  
    @(posedge clk);

//=======================one single read operate end======================

end
endtask/*}}}*/

initial begin : ready_initial_process
    ready_initial = 0;
    wait(reset === 1);
    @(posedge clk);
    ready_initial = 1;
    @(posedge clk);
    ready_initial = 0;
end

initial begin : update_status
    integer process_num ;
    integer read_status_resp;
    wait(reset === 1);
    @(posedge clk);
    process_num = 0;
    while (1) begin
        process_0_finish = 0;
        AESL_done_index_reg         <= 0;
        AESL_ready_out_index_reg        <= 0;
        if (ongoing_process_number === process_num && process_busy === 0) begin
            process_busy = 1;
            read (STATUS_ADDR, RDATA_reg, read_status_resp);
                AESL_done_index_reg         <= RDATA_reg[1 : 1];
                AESL_ready_out_index_reg    <= RDATA_reg[1 : 1];
                AESL_idle_index_reg         <= RDATA_reg[2 : 2];
            process_0_finish = 1;
            process_busy = 0;
        end 
        @(posedge clk);
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        write_raw_bayer_run_flag <= 0; 
        count_operate_depth_by_bitwidth_and_depth (raw_bayer_c_bitwidth, raw_bayer_DEPTH, raw_bayer_OPERATE_DEPTH);
    end
    else begin
        if (AESL_ready_reg === 1) begin
            write_raw_bayer_run_flag <= 1; 
        end
        else if ((write_one_raw_bayer_data_done == 1 && write_raw_bayer_count == raw_bayer_diff_count - 1) || raw_bayer_diff_count == 0) begin
            write_raw_bayer_run_flag <= 0; 
        end
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        write_raw_bayer_count = 0;
    end
    else begin
        if (AESL_ready_reg === 1) begin
            write_raw_bayer_count = 0;
        end
        if (write_one_raw_bayer_data_done === 1) begin
            write_raw_bayer_count = write_raw_bayer_count + 1;
        end
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        raw_bayer_write_data_finish <= 0;
    end
    else begin
        if (TRAN_control_start_in === 1) begin
            raw_bayer_write_data_finish <= 0;
        end
        if (write_raw_bayer_run_flag == 1 && write_raw_bayer_count == raw_bayer_diff_count) begin
            raw_bayer_write_data_finish <= 1;
        end
    end
end

initial begin : initial_diff_counter_raw_bayer
    integer four_byte_num;
    integer ceil_align_to_pow_of_two_four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;
    integer k;
    reg [31 : 0] raw_bayer_data_tmp_reg;
    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = raw_bayer_c_bitwidth;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num);
    ceil_align_to_pow_of_two_four_byte_num = ceil_align_to_pow_of_two(four_byte_num);
    while (1) begin
        wait (AESL_ready_reg === 1);
        raw_bayer_diff_count = 0;

        for (k = 0; k < raw_bayer_OPERATE_DEPTH; k = k + 1) begin
            for (i = 0; i < four_byte_num; i = i + 1) begin
                if (raw_bayer_c_bitwidth < 32) begin
                    raw_bayer_data_tmp_reg = mem_raw_bayer[k];
                end
                else begin
                    for (j = 0; j < 32; j = j + 1) begin
                        if (i*32 + j < raw_bayer_c_bitwidth) begin
                            raw_bayer_data_tmp_reg[j] = mem_raw_bayer[k][i*32 + j];
                        end
                        else begin
                            raw_bayer_data_tmp_reg[j] = 0;
                        end
                    end
                end
                if(image_mem_raw_bayer[k * four_byte_num  + i]!==raw_bayer_data_tmp_reg) begin
                raw_bayer_diff_count = raw_bayer_diff_count + 1;
                end
            end
        end

        @(posedge clk);
    end
end

initial begin : write_raw_bayer
    integer write_raw_bayer_resp;
    integer process_num ;
    integer get_ack;
    integer four_byte_num;
    integer ceil_align_to_pow_of_two_four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;
    integer check_raw_bayer_count;
    reg [31 : 0] raw_bayer_data_tmp_reg;
    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = raw_bayer_c_bitwidth;
    process_num = 1;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num);
    ceil_align_to_pow_of_two_four_byte_num = ceil_align_to_pow_of_two(four_byte_num);
    while (1) begin
        process_1_finish <= 0;

        for (check_raw_bayer_count = 0; check_raw_bayer_count < raw_bayer_OPERATE_DEPTH; check_raw_bayer_count = check_raw_bayer_count + 1) begin
            wait (ongoing_process_number === process_num && process_busy === 0);
            get_ack = 1;
            if (write_raw_bayer_run_flag === 1 && get_ack === 1) begin
                process_busy = 1;
                //write raw_bayer data 
                for (i = 0; i < four_byte_num; i = i + 1) begin
                    if (raw_bayer_c_bitwidth < 32) begin
                        raw_bayer_data_tmp_reg = mem_raw_bayer[check_raw_bayer_count];
                    end
                    else begin
                        for (j = 0; j < 32; j = j + 1) begin
                            if (i*32 + j < raw_bayer_c_bitwidth) begin
                                raw_bayer_data_tmp_reg[j] = mem_raw_bayer[check_raw_bayer_count][i*32 + j];
                            end
                            else begin
                                raw_bayer_data_tmp_reg[j] = 0;
                            end
                        end
                    end
                    if(image_mem_raw_bayer[check_raw_bayer_count * four_byte_num  + i]!==raw_bayer_data_tmp_reg) begin
                        image_mem_raw_bayer[check_raw_bayer_count * four_byte_num + i]=raw_bayer_data_tmp_reg;
                        write (raw_bayer_data_in_addr + check_raw_bayer_count * ceil_align_to_pow_of_two_four_byte_num * 4 + i * 4, raw_bayer_data_tmp_reg, write_raw_bayer_resp);
                        write_one_raw_bayer_data_done <= 1;
                        @(posedge clk);
                        write_one_raw_bayer_data_done <= 0;
                    end
                end
            end
            process_busy = 0;
        end

        process_1_finish <= 1;
        @(posedge clk);
    end    
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        write_width_run_flag <= 0; 
        count_operate_depth_by_bitwidth_and_depth (width_c_bitwidth, width_DEPTH, width_OPERATE_DEPTH);
    end
    else begin
        if (AESL_ready_reg === 1) begin
            write_width_run_flag <= 1; 
        end
        else if ((write_one_width_data_done == 1 && write_width_count == width_diff_count - 1) || width_diff_count == 0) begin
            write_width_run_flag <= 0; 
        end
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        write_width_count = 0;
    end
    else begin
        if (AESL_ready_reg === 1) begin
            write_width_count = 0;
        end
        if (write_one_width_data_done === 1) begin
            write_width_count = write_width_count + 1;
        end
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        width_write_data_finish <= 0;
    end
    else begin
        if (TRAN_control_start_in === 1) begin
            width_write_data_finish <= 0;
        end
        if (write_width_run_flag == 1 && write_width_count == width_diff_count) begin
            width_write_data_finish <= 1;
        end
    end
end

initial begin : initial_diff_counter_width
    integer four_byte_num;
    integer ceil_align_to_pow_of_two_four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;
    integer k;
    reg [31 : 0] width_data_tmp_reg;
    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = width_c_bitwidth;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num);
    ceil_align_to_pow_of_two_four_byte_num = ceil_align_to_pow_of_two(four_byte_num);
    while (1) begin
        wait (AESL_ready_reg === 1);
        width_diff_count = 0;

        for (k = 0; k < width_OPERATE_DEPTH; k = k + 1) begin
            for (i = 0; i < four_byte_num; i = i + 1) begin
                if (width_c_bitwidth < 32) begin
                    width_data_tmp_reg = mem_width[k];
                end
                else begin
                    for (j = 0; j < 32; j = j + 1) begin
                        if (i*32 + j < width_c_bitwidth) begin
                            width_data_tmp_reg[j] = mem_width[k][i*32 + j];
                        end
                        else begin
                            width_data_tmp_reg[j] = 0;
                        end
                    end
                end
                if(image_mem_width[k * four_byte_num  + i]!==width_data_tmp_reg) begin
                width_diff_count = width_diff_count + 1;
                end
            end
        end

        @(posedge clk);
    end
end

initial begin : write_width
    integer write_width_resp;
    integer process_num ;
    integer get_ack;
    integer four_byte_num;
    integer ceil_align_to_pow_of_two_four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;
    integer check_width_count;
    reg [31 : 0] width_data_tmp_reg;
    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = width_c_bitwidth;
    process_num = 2;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num);
    ceil_align_to_pow_of_two_four_byte_num = ceil_align_to_pow_of_two(four_byte_num);
    while (1) begin
        process_2_finish <= 0;

        for (check_width_count = 0; check_width_count < width_OPERATE_DEPTH; check_width_count = check_width_count + 1) begin
            wait (ongoing_process_number === process_num && process_busy === 0);
            get_ack = 1;
            if (write_width_run_flag === 1 && get_ack === 1) begin
                process_busy = 1;
                //write width data 
                for (i = 0; i < four_byte_num; i = i + 1) begin
                    if (width_c_bitwidth < 32) begin
                        width_data_tmp_reg = mem_width[check_width_count];
                    end
                    else begin
                        for (j = 0; j < 32; j = j + 1) begin
                            if (i*32 + j < width_c_bitwidth) begin
                                width_data_tmp_reg[j] = mem_width[check_width_count][i*32 + j];
                            end
                            else begin
                                width_data_tmp_reg[j] = 0;
                            end
                        end
                    end
                    if(image_mem_width[check_width_count * four_byte_num  + i]!==width_data_tmp_reg) begin
                        image_mem_width[check_width_count * four_byte_num + i]=width_data_tmp_reg;
                        write (width_data_in_addr + check_width_count * ceil_align_to_pow_of_two_four_byte_num * 4 + i * 4, width_data_tmp_reg, write_width_resp);
                        write_one_width_data_done <= 1;
                        @(posedge clk);
                        write_one_width_data_done <= 0;
                    end
                end
            end
            process_busy = 0;
        end

        process_2_finish <= 1;
        @(posedge clk);
    end    
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        write_height_run_flag <= 0; 
        count_operate_depth_by_bitwidth_and_depth (height_c_bitwidth, height_DEPTH, height_OPERATE_DEPTH);
    end
    else begin
        if (AESL_ready_reg === 1) begin
            write_height_run_flag <= 1; 
        end
        else if ((write_one_height_data_done == 1 && write_height_count == height_diff_count - 1) || height_diff_count == 0) begin
            write_height_run_flag <= 0; 
        end
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        write_height_count = 0;
    end
    else begin
        if (AESL_ready_reg === 1) begin
            write_height_count = 0;
        end
        if (write_one_height_data_done === 1) begin
            write_height_count = write_height_count + 1;
        end
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        height_write_data_finish <= 0;
    end
    else begin
        if (TRAN_control_start_in === 1) begin
            height_write_data_finish <= 0;
        end
        if (write_height_run_flag == 1 && write_height_count == height_diff_count) begin
            height_write_data_finish <= 1;
        end
    end
end

initial begin : initial_diff_counter_height
    integer four_byte_num;
    integer ceil_align_to_pow_of_two_four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;
    integer k;
    reg [31 : 0] height_data_tmp_reg;
    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = height_c_bitwidth;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num);
    ceil_align_to_pow_of_two_four_byte_num = ceil_align_to_pow_of_two(four_byte_num);
    while (1) begin
        wait (AESL_ready_reg === 1);
        height_diff_count = 0;

        for (k = 0; k < height_OPERATE_DEPTH; k = k + 1) begin
            for (i = 0; i < four_byte_num; i = i + 1) begin
                if (height_c_bitwidth < 32) begin
                    height_data_tmp_reg = mem_height[k];
                end
                else begin
                    for (j = 0; j < 32; j = j + 1) begin
                        if (i*32 + j < height_c_bitwidth) begin
                            height_data_tmp_reg[j] = mem_height[k][i*32 + j];
                        end
                        else begin
                            height_data_tmp_reg[j] = 0;
                        end
                    end
                end
                if(image_mem_height[k * four_byte_num  + i]!==height_data_tmp_reg) begin
                height_diff_count = height_diff_count + 1;
                end
            end
        end

        @(posedge clk);
    end
end

initial begin : write_height
    integer write_height_resp;
    integer process_num ;
    integer get_ack;
    integer four_byte_num;
    integer ceil_align_to_pow_of_two_four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;
    integer check_height_count;
    reg [31 : 0] height_data_tmp_reg;
    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = height_c_bitwidth;
    process_num = 3;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num);
    ceil_align_to_pow_of_two_four_byte_num = ceil_align_to_pow_of_two(four_byte_num);
    while (1) begin
        process_3_finish <= 0;

        for (check_height_count = 0; check_height_count < height_OPERATE_DEPTH; check_height_count = check_height_count + 1) begin
            wait (ongoing_process_number === process_num && process_busy === 0);
            get_ack = 1;
            if (write_height_run_flag === 1 && get_ack === 1) begin
                process_busy = 1;
                //write height data 
                for (i = 0; i < four_byte_num; i = i + 1) begin
                    if (height_c_bitwidth < 32) begin
                        height_data_tmp_reg = mem_height[check_height_count];
                    end
                    else begin
                        for (j = 0; j < 32; j = j + 1) begin
                            if (i*32 + j < height_c_bitwidth) begin
                                height_data_tmp_reg[j] = mem_height[check_height_count][i*32 + j];
                            end
                            else begin
                                height_data_tmp_reg[j] = 0;
                            end
                        end
                    end
                    if(image_mem_height[check_height_count * four_byte_num  + i]!==height_data_tmp_reg) begin
                        image_mem_height[check_height_count * four_byte_num + i]=height_data_tmp_reg;
                        write (height_data_in_addr + check_height_count * ceil_align_to_pow_of_two_four_byte_num * 4 + i * 4, height_data_tmp_reg, write_height_resp);
                        write_one_height_data_done <= 1;
                        @(posedge clk);
                        write_one_height_data_done <= 0;
                    end
                end
            end
            process_busy = 0;
        end

        process_3_finish <= 1;
        @(posedge clk);
    end    
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        write_mode_run_flag <= 0; 
        count_operate_depth_by_bitwidth_and_depth (mode_c_bitwidth, mode_DEPTH, mode_OPERATE_DEPTH);
    end
    else begin
        if (AESL_ready_reg === 1) begin
            write_mode_run_flag <= 1; 
        end
        else if ((write_one_mode_data_done == 1 && write_mode_count == mode_diff_count - 1) || mode_diff_count == 0) begin
            write_mode_run_flag <= 0; 
        end
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        write_mode_count = 0;
    end
    else begin
        if (AESL_ready_reg === 1) begin
            write_mode_count = 0;
        end
        if (write_one_mode_data_done === 1) begin
            write_mode_count = write_mode_count + 1;
        end
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        mode_write_data_finish <= 0;
    end
    else begin
        if (TRAN_control_start_in === 1) begin
            mode_write_data_finish <= 0;
        end
        if (write_mode_run_flag == 1 && write_mode_count == mode_diff_count) begin
            mode_write_data_finish <= 1;
        end
    end
end

initial begin : initial_diff_counter_mode
    integer four_byte_num;
    integer ceil_align_to_pow_of_two_four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;
    integer k;
    reg [31 : 0] mode_data_tmp_reg;
    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = mode_c_bitwidth;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num);
    ceil_align_to_pow_of_two_four_byte_num = ceil_align_to_pow_of_two(four_byte_num);
    while (1) begin
        wait (AESL_ready_reg === 1);
        mode_diff_count = 0;

        for (k = 0; k < mode_OPERATE_DEPTH; k = k + 1) begin
            for (i = 0; i < four_byte_num; i = i + 1) begin
                if (mode_c_bitwidth < 32) begin
                    mode_data_tmp_reg = mem_mode[k];
                end
                else begin
                    for (j = 0; j < 32; j = j + 1) begin
                        if (i*32 + j < mode_c_bitwidth) begin
                            mode_data_tmp_reg[j] = mem_mode[k][i*32 + j];
                        end
                        else begin
                            mode_data_tmp_reg[j] = 0;
                        end
                    end
                end
                if(image_mem_mode[k * four_byte_num  + i]!==mode_data_tmp_reg) begin
                mode_diff_count = mode_diff_count + 1;
                end
            end
        end

        @(posedge clk);
    end
end

initial begin : write_mode
    integer write_mode_resp;
    integer process_num ;
    integer get_ack;
    integer four_byte_num;
    integer ceil_align_to_pow_of_two_four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;
    integer check_mode_count;
    reg [31 : 0] mode_data_tmp_reg;
    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = mode_c_bitwidth;
    process_num = 4;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num);
    ceil_align_to_pow_of_two_four_byte_num = ceil_align_to_pow_of_two(four_byte_num);
    while (1) begin
        process_4_finish <= 0;

        for (check_mode_count = 0; check_mode_count < mode_OPERATE_DEPTH; check_mode_count = check_mode_count + 1) begin
            wait (ongoing_process_number === process_num && process_busy === 0);
            get_ack = 1;
            if (write_mode_run_flag === 1 && get_ack === 1) begin
                process_busy = 1;
                //write mode data 
                for (i = 0; i < four_byte_num; i = i + 1) begin
                    if (mode_c_bitwidth < 32) begin
                        mode_data_tmp_reg = mem_mode[check_mode_count];
                    end
                    else begin
                        for (j = 0; j < 32; j = j + 1) begin
                            if (i*32 + j < mode_c_bitwidth) begin
                                mode_data_tmp_reg[j] = mem_mode[check_mode_count][i*32 + j];
                            end
                            else begin
                                mode_data_tmp_reg[j] = 0;
                            end
                        end
                    end
                    if(image_mem_mode[check_mode_count * four_byte_num  + i]!==mode_data_tmp_reg) begin
                        image_mem_mode[check_mode_count * four_byte_num + i]=mode_data_tmp_reg;
                        write (mode_data_in_addr + check_mode_count * ceil_align_to_pow_of_two_four_byte_num * 4 + i * 4, mode_data_tmp_reg, write_mode_resp);
                        write_one_mode_data_done <= 1;
                        @(posedge clk);
                        write_one_mode_data_done <= 0;
                    end
                end
            end
            process_busy = 0;
        end

        process_4_finish <= 1;
        @(posedge clk);
    end    
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        write_dark_pixel_threshold_run_flag <= 0; 
        count_operate_depth_by_bitwidth_and_depth (dark_pixel_threshold_c_bitwidth, dark_pixel_threshold_DEPTH, dark_pixel_threshold_OPERATE_DEPTH);
    end
    else begin
        if (AESL_ready_reg === 1) begin
            write_dark_pixel_threshold_run_flag <= 1; 
        end
        else if ((write_one_dark_pixel_threshold_data_done == 1 && write_dark_pixel_threshold_count == dark_pixel_threshold_diff_count - 1) || dark_pixel_threshold_diff_count == 0) begin
            write_dark_pixel_threshold_run_flag <= 0; 
        end
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        write_dark_pixel_threshold_count = 0;
    end
    else begin
        if (AESL_ready_reg === 1) begin
            write_dark_pixel_threshold_count = 0;
        end
        if (write_one_dark_pixel_threshold_data_done === 1) begin
            write_dark_pixel_threshold_count = write_dark_pixel_threshold_count + 1;
        end
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        dark_pixel_threshold_write_data_finish <= 0;
    end
    else begin
        if (TRAN_control_start_in === 1) begin
            dark_pixel_threshold_write_data_finish <= 0;
        end
        if (write_dark_pixel_threshold_run_flag == 1 && write_dark_pixel_threshold_count == dark_pixel_threshold_diff_count) begin
            dark_pixel_threshold_write_data_finish <= 1;
        end
    end
end

initial begin : initial_diff_counter_dark_pixel_threshold
    integer four_byte_num;
    integer ceil_align_to_pow_of_two_four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;
    integer k;
    reg [31 : 0] dark_pixel_threshold_data_tmp_reg;
    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = dark_pixel_threshold_c_bitwidth;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num);
    ceil_align_to_pow_of_two_four_byte_num = ceil_align_to_pow_of_two(four_byte_num);
    while (1) begin
        wait (AESL_ready_reg === 1);
        dark_pixel_threshold_diff_count = 0;

        for (k = 0; k < dark_pixel_threshold_OPERATE_DEPTH; k = k + 1) begin
            for (i = 0; i < four_byte_num; i = i + 1) begin
                if (dark_pixel_threshold_c_bitwidth < 32) begin
                    dark_pixel_threshold_data_tmp_reg = mem_dark_pixel_threshold[k];
                end
                else begin
                    for (j = 0; j < 32; j = j + 1) begin
                        if (i*32 + j < dark_pixel_threshold_c_bitwidth) begin
                            dark_pixel_threshold_data_tmp_reg[j] = mem_dark_pixel_threshold[k][i*32 + j];
                        end
                        else begin
                            dark_pixel_threshold_data_tmp_reg[j] = 0;
                        end
                    end
                end
                if(image_mem_dark_pixel_threshold[k * four_byte_num  + i]!==dark_pixel_threshold_data_tmp_reg) begin
                dark_pixel_threshold_diff_count = dark_pixel_threshold_diff_count + 1;
                end
            end
        end

        @(posedge clk);
    end
end

initial begin : write_dark_pixel_threshold
    integer write_dark_pixel_threshold_resp;
    integer process_num ;
    integer get_ack;
    integer four_byte_num;
    integer ceil_align_to_pow_of_two_four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;
    integer check_dark_pixel_threshold_count;
    reg [31 : 0] dark_pixel_threshold_data_tmp_reg;
    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = dark_pixel_threshold_c_bitwidth;
    process_num = 5;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num);
    ceil_align_to_pow_of_two_four_byte_num = ceil_align_to_pow_of_two(four_byte_num);
    while (1) begin
        process_5_finish <= 0;

        for (check_dark_pixel_threshold_count = 0; check_dark_pixel_threshold_count < dark_pixel_threshold_OPERATE_DEPTH; check_dark_pixel_threshold_count = check_dark_pixel_threshold_count + 1) begin
            wait (ongoing_process_number === process_num && process_busy === 0);
            get_ack = 1;
            if (write_dark_pixel_threshold_run_flag === 1 && get_ack === 1) begin
                process_busy = 1;
                //write dark_pixel_threshold data 
                for (i = 0; i < four_byte_num; i = i + 1) begin
                    if (dark_pixel_threshold_c_bitwidth < 32) begin
                        dark_pixel_threshold_data_tmp_reg = mem_dark_pixel_threshold[check_dark_pixel_threshold_count];
                    end
                    else begin
                        for (j = 0; j < 32; j = j + 1) begin
                            if (i*32 + j < dark_pixel_threshold_c_bitwidth) begin
                                dark_pixel_threshold_data_tmp_reg[j] = mem_dark_pixel_threshold[check_dark_pixel_threshold_count][i*32 + j];
                            end
                            else begin
                                dark_pixel_threshold_data_tmp_reg[j] = 0;
                            end
                        end
                    end
                    if(image_mem_dark_pixel_threshold[check_dark_pixel_threshold_count * four_byte_num  + i]!==dark_pixel_threshold_data_tmp_reg) begin
                        image_mem_dark_pixel_threshold[check_dark_pixel_threshold_count * four_byte_num + i]=dark_pixel_threshold_data_tmp_reg;
                        write (dark_pixel_threshold_data_in_addr + check_dark_pixel_threshold_count * ceil_align_to_pow_of_two_four_byte_num * 4 + i * 4, dark_pixel_threshold_data_tmp_reg, write_dark_pixel_threshold_resp);
                        write_one_dark_pixel_threshold_data_done <= 1;
                        @(posedge clk);
                        write_one_dark_pixel_threshold_data_done <= 0;
                    end
                end
            end
            process_busy = 0;
        end

        process_5_finish <= 1;
        @(posedge clk);
    end    
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        write_verdict_pct_run_flag <= 0; 
        count_operate_depth_by_bitwidth_and_depth (verdict_pct_c_bitwidth, verdict_pct_DEPTH, verdict_pct_OPERATE_DEPTH);
    end
    else begin
        if (AESL_ready_reg === 1) begin
            write_verdict_pct_run_flag <= 1; 
        end
        else if ((write_one_verdict_pct_data_done == 1 && write_verdict_pct_count == verdict_pct_diff_count - 1) || verdict_pct_diff_count == 0) begin
            write_verdict_pct_run_flag <= 0; 
        end
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        write_verdict_pct_count = 0;
    end
    else begin
        if (AESL_ready_reg === 1) begin
            write_verdict_pct_count = 0;
        end
        if (write_one_verdict_pct_data_done === 1) begin
            write_verdict_pct_count = write_verdict_pct_count + 1;
        end
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        verdict_pct_write_data_finish <= 0;
    end
    else begin
        if (TRAN_control_start_in === 1) begin
            verdict_pct_write_data_finish <= 0;
        end
        if (write_verdict_pct_run_flag == 1 && write_verdict_pct_count == verdict_pct_diff_count) begin
            verdict_pct_write_data_finish <= 1;
        end
    end
end

initial begin : initial_diff_counter_verdict_pct
    integer four_byte_num;
    integer ceil_align_to_pow_of_two_four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;
    integer k;
    reg [31 : 0] verdict_pct_data_tmp_reg;
    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = verdict_pct_c_bitwidth;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num);
    ceil_align_to_pow_of_two_four_byte_num = ceil_align_to_pow_of_two(four_byte_num);
    while (1) begin
        wait (AESL_ready_reg === 1);
        verdict_pct_diff_count = 0;

        for (k = 0; k < verdict_pct_OPERATE_DEPTH; k = k + 1) begin
            for (i = 0; i < four_byte_num; i = i + 1) begin
                if (verdict_pct_c_bitwidth < 32) begin
                    verdict_pct_data_tmp_reg = mem_verdict_pct[k];
                end
                else begin
                    for (j = 0; j < 32; j = j + 1) begin
                        if (i*32 + j < verdict_pct_c_bitwidth) begin
                            verdict_pct_data_tmp_reg[j] = mem_verdict_pct[k][i*32 + j];
                        end
                        else begin
                            verdict_pct_data_tmp_reg[j] = 0;
                        end
                    end
                end
                if(image_mem_verdict_pct[k * four_byte_num  + i]!==verdict_pct_data_tmp_reg) begin
                verdict_pct_diff_count = verdict_pct_diff_count + 1;
                end
            end
        end

        @(posedge clk);
    end
end

initial begin : write_verdict_pct
    integer write_verdict_pct_resp;
    integer process_num ;
    integer get_ack;
    integer four_byte_num;
    integer ceil_align_to_pow_of_two_four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;
    integer check_verdict_pct_count;
    reg [31 : 0] verdict_pct_data_tmp_reg;
    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = verdict_pct_c_bitwidth;
    process_num = 6;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num);
    ceil_align_to_pow_of_two_four_byte_num = ceil_align_to_pow_of_two(four_byte_num);
    while (1) begin
        process_6_finish <= 0;

        for (check_verdict_pct_count = 0; check_verdict_pct_count < verdict_pct_OPERATE_DEPTH; check_verdict_pct_count = check_verdict_pct_count + 1) begin
            wait (ongoing_process_number === process_num && process_busy === 0);
            get_ack = 1;
            if (write_verdict_pct_run_flag === 1 && get_ack === 1) begin
                process_busy = 1;
                //write verdict_pct data 
                for (i = 0; i < four_byte_num; i = i + 1) begin
                    if (verdict_pct_c_bitwidth < 32) begin
                        verdict_pct_data_tmp_reg = mem_verdict_pct[check_verdict_pct_count];
                    end
                    else begin
                        for (j = 0; j < 32; j = j + 1) begin
                            if (i*32 + j < verdict_pct_c_bitwidth) begin
                                verdict_pct_data_tmp_reg[j] = mem_verdict_pct[check_verdict_pct_count][i*32 + j];
                            end
                            else begin
                                verdict_pct_data_tmp_reg[j] = 0;
                            end
                        end
                    end
                    if(image_mem_verdict_pct[check_verdict_pct_count * four_byte_num  + i]!==verdict_pct_data_tmp_reg) begin
                        image_mem_verdict_pct[check_verdict_pct_count * four_byte_num + i]=verdict_pct_data_tmp_reg;
                        write (verdict_pct_data_in_addr + check_verdict_pct_count * ceil_align_to_pow_of_two_four_byte_num * 4 + i * 4, verdict_pct_data_tmp_reg, write_verdict_pct_resp);
                        write_one_verdict_pct_data_done <= 1;
                        @(posedge clk);
                        write_one_verdict_pct_data_done <= 0;
                    end
                end
            end
            process_busy = 0;
        end

        process_6_finish <= 1;
        @(posedge clk);
    end    
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        write_enter_pct_run_flag <= 0; 
        count_operate_depth_by_bitwidth_and_depth (enter_pct_c_bitwidth, enter_pct_DEPTH, enter_pct_OPERATE_DEPTH);
    end
    else begin
        if (AESL_ready_reg === 1) begin
            write_enter_pct_run_flag <= 1; 
        end
        else if ((write_one_enter_pct_data_done == 1 && write_enter_pct_count == enter_pct_diff_count - 1) || enter_pct_diff_count == 0) begin
            write_enter_pct_run_flag <= 0; 
        end
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        write_enter_pct_count = 0;
    end
    else begin
        if (AESL_ready_reg === 1) begin
            write_enter_pct_count = 0;
        end
        if (write_one_enter_pct_data_done === 1) begin
            write_enter_pct_count = write_enter_pct_count + 1;
        end
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        enter_pct_write_data_finish <= 0;
    end
    else begin
        if (TRAN_control_start_in === 1) begin
            enter_pct_write_data_finish <= 0;
        end
        if (write_enter_pct_run_flag == 1 && write_enter_pct_count == enter_pct_diff_count) begin
            enter_pct_write_data_finish <= 1;
        end
    end
end

initial begin : initial_diff_counter_enter_pct
    integer four_byte_num;
    integer ceil_align_to_pow_of_two_four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;
    integer k;
    reg [31 : 0] enter_pct_data_tmp_reg;
    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = enter_pct_c_bitwidth;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num);
    ceil_align_to_pow_of_two_four_byte_num = ceil_align_to_pow_of_two(four_byte_num);
    while (1) begin
        wait (AESL_ready_reg === 1);
        enter_pct_diff_count = 0;

        for (k = 0; k < enter_pct_OPERATE_DEPTH; k = k + 1) begin
            for (i = 0; i < four_byte_num; i = i + 1) begin
                if (enter_pct_c_bitwidth < 32) begin
                    enter_pct_data_tmp_reg = mem_enter_pct[k];
                end
                else begin
                    for (j = 0; j < 32; j = j + 1) begin
                        if (i*32 + j < enter_pct_c_bitwidth) begin
                            enter_pct_data_tmp_reg[j] = mem_enter_pct[k][i*32 + j];
                        end
                        else begin
                            enter_pct_data_tmp_reg[j] = 0;
                        end
                    end
                end
                if(image_mem_enter_pct[k * four_byte_num  + i]!==enter_pct_data_tmp_reg) begin
                enter_pct_diff_count = enter_pct_diff_count + 1;
                end
            end
        end

        @(posedge clk);
    end
end

initial begin : write_enter_pct
    integer write_enter_pct_resp;
    integer process_num ;
    integer get_ack;
    integer four_byte_num;
    integer ceil_align_to_pow_of_two_four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;
    integer check_enter_pct_count;
    reg [31 : 0] enter_pct_data_tmp_reg;
    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = enter_pct_c_bitwidth;
    process_num = 7;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num);
    ceil_align_to_pow_of_two_four_byte_num = ceil_align_to_pow_of_two(four_byte_num);
    while (1) begin
        process_7_finish <= 0;

        for (check_enter_pct_count = 0; check_enter_pct_count < enter_pct_OPERATE_DEPTH; check_enter_pct_count = check_enter_pct_count + 1) begin
            wait (ongoing_process_number === process_num && process_busy === 0);
            get_ack = 1;
            if (write_enter_pct_run_flag === 1 && get_ack === 1) begin
                process_busy = 1;
                //write enter_pct data 
                for (i = 0; i < four_byte_num; i = i + 1) begin
                    if (enter_pct_c_bitwidth < 32) begin
                        enter_pct_data_tmp_reg = mem_enter_pct[check_enter_pct_count];
                    end
                    else begin
                        for (j = 0; j < 32; j = j + 1) begin
                            if (i*32 + j < enter_pct_c_bitwidth) begin
                                enter_pct_data_tmp_reg[j] = mem_enter_pct[check_enter_pct_count][i*32 + j];
                            end
                            else begin
                                enter_pct_data_tmp_reg[j] = 0;
                            end
                        end
                    end
                    if(image_mem_enter_pct[check_enter_pct_count * four_byte_num  + i]!==enter_pct_data_tmp_reg) begin
                        image_mem_enter_pct[check_enter_pct_count * four_byte_num + i]=enter_pct_data_tmp_reg;
                        write (enter_pct_data_in_addr + check_enter_pct_count * ceil_align_to_pow_of_two_four_byte_num * 4 + i * 4, enter_pct_data_tmp_reg, write_enter_pct_resp);
                        write_one_enter_pct_data_done <= 1;
                        @(posedge clk);
                        write_one_enter_pct_data_done <= 0;
                    end
                end
            end
            process_busy = 0;
        end

        process_7_finish <= 1;
        @(posedge clk);
    end    
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        write_exit_pct_run_flag <= 0; 
        count_operate_depth_by_bitwidth_and_depth (exit_pct_c_bitwidth, exit_pct_DEPTH, exit_pct_OPERATE_DEPTH);
    end
    else begin
        if (AESL_ready_reg === 1) begin
            write_exit_pct_run_flag <= 1; 
        end
        else if ((write_one_exit_pct_data_done == 1 && write_exit_pct_count == exit_pct_diff_count - 1) || exit_pct_diff_count == 0) begin
            write_exit_pct_run_flag <= 0; 
        end
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        write_exit_pct_count = 0;
    end
    else begin
        if (AESL_ready_reg === 1) begin
            write_exit_pct_count = 0;
        end
        if (write_one_exit_pct_data_done === 1) begin
            write_exit_pct_count = write_exit_pct_count + 1;
        end
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        exit_pct_write_data_finish <= 0;
    end
    else begin
        if (TRAN_control_start_in === 1) begin
            exit_pct_write_data_finish <= 0;
        end
        if (write_exit_pct_run_flag == 1 && write_exit_pct_count == exit_pct_diff_count) begin
            exit_pct_write_data_finish <= 1;
        end
    end
end

initial begin : initial_diff_counter_exit_pct
    integer four_byte_num;
    integer ceil_align_to_pow_of_two_four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;
    integer k;
    reg [31 : 0] exit_pct_data_tmp_reg;
    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = exit_pct_c_bitwidth;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num);
    ceil_align_to_pow_of_two_four_byte_num = ceil_align_to_pow_of_two(four_byte_num);
    while (1) begin
        wait (AESL_ready_reg === 1);
        exit_pct_diff_count = 0;

        for (k = 0; k < exit_pct_OPERATE_DEPTH; k = k + 1) begin
            for (i = 0; i < four_byte_num; i = i + 1) begin
                if (exit_pct_c_bitwidth < 32) begin
                    exit_pct_data_tmp_reg = mem_exit_pct[k];
                end
                else begin
                    for (j = 0; j < 32; j = j + 1) begin
                        if (i*32 + j < exit_pct_c_bitwidth) begin
                            exit_pct_data_tmp_reg[j] = mem_exit_pct[k][i*32 + j];
                        end
                        else begin
                            exit_pct_data_tmp_reg[j] = 0;
                        end
                    end
                end
                if(image_mem_exit_pct[k * four_byte_num  + i]!==exit_pct_data_tmp_reg) begin
                exit_pct_diff_count = exit_pct_diff_count + 1;
                end
            end
        end

        @(posedge clk);
    end
end

initial begin : write_exit_pct
    integer write_exit_pct_resp;
    integer process_num ;
    integer get_ack;
    integer four_byte_num;
    integer ceil_align_to_pow_of_two_four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;
    integer check_exit_pct_count;
    reg [31 : 0] exit_pct_data_tmp_reg;
    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = exit_pct_c_bitwidth;
    process_num = 8;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num);
    ceil_align_to_pow_of_two_four_byte_num = ceil_align_to_pow_of_two(four_byte_num);
    while (1) begin
        process_8_finish <= 0;

        for (check_exit_pct_count = 0; check_exit_pct_count < exit_pct_OPERATE_DEPTH; check_exit_pct_count = check_exit_pct_count + 1) begin
            wait (ongoing_process_number === process_num && process_busy === 0);
            get_ack = 1;
            if (write_exit_pct_run_flag === 1 && get_ack === 1) begin
                process_busy = 1;
                //write exit_pct data 
                for (i = 0; i < four_byte_num; i = i + 1) begin
                    if (exit_pct_c_bitwidth < 32) begin
                        exit_pct_data_tmp_reg = mem_exit_pct[check_exit_pct_count];
                    end
                    else begin
                        for (j = 0; j < 32; j = j + 1) begin
                            if (i*32 + j < exit_pct_c_bitwidth) begin
                                exit_pct_data_tmp_reg[j] = mem_exit_pct[check_exit_pct_count][i*32 + j];
                            end
                            else begin
                                exit_pct_data_tmp_reg[j] = 0;
                            end
                        end
                    end
                    if(image_mem_exit_pct[check_exit_pct_count * four_byte_num  + i]!==exit_pct_data_tmp_reg) begin
                        image_mem_exit_pct[check_exit_pct_count * four_byte_num + i]=exit_pct_data_tmp_reg;
                        write (exit_pct_data_in_addr + check_exit_pct_count * ceil_align_to_pow_of_two_four_byte_num * 4 + i * 4, exit_pct_data_tmp_reg, write_exit_pct_resp);
                        write_one_exit_pct_data_done <= 1;
                        @(posedge clk);
                        write_one_exit_pct_data_done <= 0;
                    end
                end
            end
            process_busy = 0;
        end

        process_8_finish <= 1;
        @(posedge clk);
    end    
end


always @(reset or posedge clk) begin
    if (reset == 0) begin
        write_start_run_flag <= 0; 
        write_start_count <= 0;
    end
    else begin
        if (write_start_count >= 4) begin
            write_start_run_flag <= 0; 
        end
        else if (TRAN_control_write_start_in === 1) begin
            write_start_run_flag <= 1; 
        end
        if (AESL_write_start_finish === 1) begin
            write_start_count <= write_start_count + 1;
            write_start_run_flag <= 0; 
        end
    end
end

initial begin : write_start
    reg [DATA_WIDTH - 1 : 0] write_start_tmp;
    integer process_num;
    integer write_start_resp;
    wait(reset === 1);
    @(posedge clk);
    process_num = 9;
    while (1) begin
        process_9_finish = 0;
        if (ongoing_process_number === process_num && process_busy === 0 ) begin
            if (write_start_run_flag === 1) begin
                process_busy = 1;
                write_start_tmp=0;
                write_start_tmp[0 : 0] = 1;
                write (START_ADDR, write_start_tmp, write_start_resp);
                process_busy = 0;
                AESL_write_start_finish <= 1;
                @(posedge clk);
                AESL_write_start_finish <= 0;
            end
            process_9_finish <= 1;
        end 
        @(posedge clk);
    end
end

always @(reset or posedge clk) begin
    if (reset == 0) begin
        selected_mode_read_data_finish <= 0;
        read_selected_mode_run_flag <= 0; 
        read_selected_mode_count = 0;
        count_operate_depth_by_bitwidth_and_depth (selected_mode_c_bitwidth, selected_mode_DEPTH, selected_mode_OPERATE_DEPTH);
    end
    else begin
        if (AESL_done_index_reg === 1) begin
            read_selected_mode_run_flag = 1; 
        end
        if (TRAN_control_transaction_done_in === 1) begin
            selected_mode_read_data_finish <= 0;
            read_selected_mode_count = 0; 
        end
        if (read_one_selected_mode_data_done === 1) begin
            read_selected_mode_count = read_selected_mode_count + 1;
            if (read_selected_mode_count == selected_mode_OPERATE_DEPTH) begin
                read_selected_mode_run_flag <= 0; 
                selected_mode_read_data_finish <= 1;
            end
        end
    end
end

initial begin : read_selected_mode
    integer read_selected_mode_resp;
    integer process_num;
    integer get_vld;
    integer four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;

    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = selected_mode_c_bitwidth;
    process_num = 10;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num) ;
    while (1) begin
        process_10_finish <= 0;
        if (ongoing_process_number === process_num && process_busy === 0 ) begin
            if (read_selected_mode_run_flag === 1) begin
                process_busy = 1;
                get_vld = 0;
                //read selected_mode vld
                read (selected_mode_valid_out_addr, RDATA_reg, read_selected_mode_resp);
                if (RDATA_reg[0 : 0] == 1) begin
                    get_vld = 1;
                end
                if (get_vld == 1) begin
                    //read selected_mode data 
                    for (i = 0 ; i < four_byte_num ; i = i+1) begin
                        read (selected_mode_data_out_addr + read_selected_mode_count * four_byte_num * 4 + i * 4, RDATA_reg, read_selected_mode_resp);
                        if (selected_mode_c_bitwidth < 32) begin
                            mem_selected_mode[read_selected_mode_count] <= RDATA_reg;
                        end
                        else begin
                            for (j=0 ; j < 32 ; j = j + 1) begin
                                if (i*32 + j < selected_mode_c_bitwidth) begin
                                    mem_selected_mode[read_selected_mode_count][i*32 + j] <= RDATA_reg[j];
                                end
                            end
                        end
                    end
                    
                    read_one_selected_mode_data_done <= 1;
                    @(posedge clk);
                    read_one_selected_mode_data_done <= 0;
                end    
                process_busy = 0;
            end    
            process_10_finish <= 1;
        end
        @(posedge clk);
    end    
end
always @(reset or posedge clk) begin
    if (reset == 0) begin
        dark_count_read_data_finish <= 0;
        read_dark_count_run_flag <= 0; 
        read_dark_count_count = 0;
        count_operate_depth_by_bitwidth_and_depth (dark_count_c_bitwidth, dark_count_DEPTH, dark_count_OPERATE_DEPTH);
    end
    else begin
        if (AESL_done_index_reg === 1) begin
            read_dark_count_run_flag = 1; 
        end
        if (TRAN_control_transaction_done_in === 1) begin
            dark_count_read_data_finish <= 0;
            read_dark_count_count = 0; 
        end
        if (read_one_dark_count_data_done === 1) begin
            read_dark_count_count = read_dark_count_count + 1;
            if (read_dark_count_count == dark_count_OPERATE_DEPTH) begin
                read_dark_count_run_flag <= 0; 
                dark_count_read_data_finish <= 1;
            end
        end
    end
end

initial begin : read_dark_count
    integer read_dark_count_resp;
    integer process_num;
    integer get_vld;
    integer four_byte_num;
    integer c_bitwidth;
    integer i;
    integer j;

    wait(reset === 1);
    @(posedge clk);
    c_bitwidth = dark_count_c_bitwidth;
    process_num = 11;
    count_c_data_four_byte_num_by_bitwidth (c_bitwidth , four_byte_num) ;
    while (1) begin
        process_11_finish <= 0;
        if (ongoing_process_number === process_num && process_busy === 0 ) begin
            if (read_dark_count_run_flag === 1) begin
                process_busy = 1;
                get_vld = 0;
                //read dark_count vld
                read (dark_count_valid_out_addr, RDATA_reg, read_dark_count_resp);
                if (RDATA_reg[0 : 0] == 1) begin
                    get_vld = 1;
                end
                if (get_vld == 1) begin
                    //read dark_count data 
                    for (i = 0 ; i < four_byte_num ; i = i+1) begin
                        read (dark_count_data_out_addr + read_dark_count_count * four_byte_num * 4 + i * 4, RDATA_reg, read_dark_count_resp);
                        if (dark_count_c_bitwidth < 32) begin
                            mem_dark_count[read_dark_count_count] <= RDATA_reg;
                        end
                        else begin
                            for (j=0 ; j < 32 ; j = j + 1) begin
                                if (i*32 + j < dark_count_c_bitwidth) begin
                                    mem_dark_count[read_dark_count_count][i*32 + j] <= RDATA_reg[j];
                                end
                            end
                        end
                    end
                    
                    read_one_dark_count_data_done <= 1;
                    @(posedge clk);
                    read_one_dark_count_data_done <= 0;
                end    
                process_busy = 0;
            end    
            process_11_finish <= 1;
        end
        @(posedge clk);
    end    
end
//------------------------Task and function-------------- 
task read_token; 
    input integer fp; 
    output reg [151 : 0] token;
    integer ret;
    begin
        token = "";
        ret = 0;
        ret = $fscanf(fp,"%s",token);
    end 
endtask 
 
//------------------------Read file------------------------ 
 
// Read data from file 
initial begin : read_raw_bayer_file_process 
  integer fp; 
  integer ret; 
  integer factor; 
  reg [151 : 0] token; 
  reg [151 : 0] token_tmp; 
  //reg [raw_bayer_c_bitwidth - 1 : 0] token_tmp; 
  reg [DATA_WIDTH - 1 : 0] tmp_cache_mem; 
  reg [ 8*5 : 1] str;
    reg [63:0] trans_depth;
  integer transaction_idx; 
  integer i; 
  transaction_idx = 0; 
  tmp_cache_mem [DATA_WIDTH - 1 : 0] = 0;
  count_seperate_factor_by_bitwidth (raw_bayer_c_bitwidth , factor);
  fp = $fopen(`TV_IN_raw_bayer ,"r"); 
  if(fp == 0) begin                               // Failed to open file 
      $display("Failed to open file \"%s\"!", `TV_IN_raw_bayer); 
      $finish; 
  end 
  read_token(fp, token); 
  if (token != "[[[runtime]]]") begin             // Illegal format 
      $display("ERROR: Simulation using HLS TB failed.");
      $finish; 
  end 
  read_token(fp, token); 
  while (token != "[[[/runtime]]]") begin 
      if (token != "[[transaction]]") begin 
          $display("ERROR: Simulation using HLS TB failed.");
          $finish; 
      end 
      read_token(fp, token);                        // skip transaction number 
      @(posedge clk);
      # 0.2;
      while(AESL_ready_reg !== 1) begin
          @(posedge clk); 
          # 0.2;
      end
      for(i = 0; i < raw_bayer_DEPTH; i = i + 1) begin 
          read_token(fp, token); 
          ret = $sscanf(token, "0x%x", token_tmp); 
          if (factor == 4) begin
              if (i%factor == 0) begin
                  tmp_cache_mem [7 : 0] = token_tmp;
              end
              if (i%factor == 1) begin
                  tmp_cache_mem [15 : 8] = token_tmp;
              end
              if (i%factor == 2) begin
                  tmp_cache_mem [23 : 16] = token_tmp;
              end
              if (i%factor == 3) begin
                  tmp_cache_mem [31 : 24] = token_tmp;
                  mem_raw_bayer [i/factor] = tmp_cache_mem;
                  tmp_cache_mem [DATA_WIDTH - 1 : 0] = 0;
              end
          end
          if (factor == 2) begin
              if (i%factor == 0) begin
                  tmp_cache_mem [15 : 0] = token_tmp;
              end
              if (i%factor == 1) begin
                  tmp_cache_mem [31 : 16] = token_tmp;
                  mem_raw_bayer [i/factor] = tmp_cache_mem;
                  tmp_cache_mem [DATA_WIDTH - 1: 0] = 0;
              end
          end
          if (factor == 1) begin
              mem_raw_bayer [i] = token_tmp;
          end
      end 
      if (factor == 4) begin
          if (i%factor != 0) begin
              mem_raw_bayer [i/factor] = tmp_cache_mem;
          end
      end
      if (factor == 2) begin
          if (i%factor != 0) begin
              mem_raw_bayer [i/factor] = tmp_cache_mem;
          end
      end 
      read_token(fp, token); 
      if(token != "[[/transaction]]") begin 
          $display("ERROR: Simulation using HLS TB failed.");
          $finish; 
      end 
      read_token(fp, token); 
      transaction_idx = transaction_idx + 1; 
  end 
  $fclose(fp); 
end 
 
task write_binary_raw_bayer;
    input integer fp;
    input reg[64-1:0] in;
    input integer in_bw;
    reg [63:0] tmp_long;
    reg[64-1:0] local_in;
    integer char_num;
    integer long_num;
    integer i;
    integer j;
    begin
        long_num = (in_bw + 63) / 64;
        char_num = ((in_bw - 1) % 64 + 7) / 8;
        for(i=long_num;i>0;i=i-1) begin
             local_in = in;
             tmp_long = local_in >> ((i-1)*64);
             for(j=0;j<64;j=j+1)
                 if (tmp_long[j] === 1'bx)
                     tmp_long[j] = 1'b0;
             if (i == long_num) begin
                 case(char_num)
                     1: $fwrite(fp,"%c",tmp_long[7:0]);
                     2: $fwrite(fp,"%c%c",tmp_long[15:8],tmp_long[7:0]);
                     3: $fwrite(fp,"%c%c%c",tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     4: $fwrite(fp,"%c%c%c%c",tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     5: $fwrite(fp,"%c%c%c%c%c",tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     6: $fwrite(fp,"%c%c%c%c%c%c",tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     7: $fwrite(fp,"%c%c%c%c%c%c%c",tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     8: $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     default: ;
                 endcase
             end
             else begin
                 $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
             end
        end
    end
endtask;
//------------------------Read file------------------------ 
 
// Read data from file 
initial begin : read_width_file_process 
  integer fp; 
  integer ret; 
  integer factor; 
  reg [127 : 0] token; 
  reg [127 : 0] token_tmp; 
  //reg [width_c_bitwidth - 1 : 0] token_tmp; 
  reg [DATA_WIDTH - 1 : 0] tmp_cache_mem; 
  reg [ 8*5 : 1] str;
    reg [63:0] trans_depth;
  integer transaction_idx; 
  integer i; 
  transaction_idx = 0; 
  tmp_cache_mem [DATA_WIDTH - 1 : 0] = 0;
  count_seperate_factor_by_bitwidth (width_c_bitwidth , factor);
  fp = $fopen(`TV_IN_width ,"r"); 
  if(fp == 0) begin                               // Failed to open file 
      $display("Failed to open file \"%s\"!", `TV_IN_width); 
      $finish; 
  end 
  read_token(fp, token); 
  if (token != "[[[runtime]]]") begin             // Illegal format 
      $display("ERROR: Simulation using HLS TB failed.");
      $finish; 
  end 
  read_token(fp, token); 
  while (token != "[[[/runtime]]]") begin 
      if (token != "[[transaction]]") begin 
          $display("ERROR: Simulation using HLS TB failed.");
          $finish; 
      end 
      read_token(fp, token);                        // skip transaction number 
      @(posedge clk);
      # 0.2;
      while(AESL_ready_reg !== 1) begin
          @(posedge clk); 
          # 0.2;
      end
      for(i = 0; i < width_DEPTH; i = i + 1) begin 
          read_token(fp, token); 
          ret = $sscanf(token, "0x%x", token_tmp); 
          if (factor == 4) begin
              if (i%factor == 0) begin
                  tmp_cache_mem [7 : 0] = token_tmp;
              end
              if (i%factor == 1) begin
                  tmp_cache_mem [15 : 8] = token_tmp;
              end
              if (i%factor == 2) begin
                  tmp_cache_mem [23 : 16] = token_tmp;
              end
              if (i%factor == 3) begin
                  tmp_cache_mem [31 : 24] = token_tmp;
                  mem_width [i/factor] = tmp_cache_mem;
                  tmp_cache_mem [DATA_WIDTH - 1 : 0] = 0;
              end
          end
          if (factor == 2) begin
              if (i%factor == 0) begin
                  tmp_cache_mem [15 : 0] = token_tmp;
              end
              if (i%factor == 1) begin
                  tmp_cache_mem [31 : 16] = token_tmp;
                  mem_width [i/factor] = tmp_cache_mem;
                  tmp_cache_mem [DATA_WIDTH - 1: 0] = 0;
              end
          end
          if (factor == 1) begin
              mem_width [i] = token_tmp;
          end
      end 
      if (factor == 4) begin
          if (i%factor != 0) begin
              mem_width [i/factor] = tmp_cache_mem;
          end
      end
      if (factor == 2) begin
          if (i%factor != 0) begin
              mem_width [i/factor] = tmp_cache_mem;
          end
      end 
      read_token(fp, token); 
      if(token != "[[/transaction]]") begin 
          $display("ERROR: Simulation using HLS TB failed.");
          $finish; 
      end 
      read_token(fp, token); 
      transaction_idx = transaction_idx + 1; 
  end 
  $fclose(fp); 
end 
 
task write_binary_width;
    input integer fp;
    input reg[64-1:0] in;
    input integer in_bw;
    reg [63:0] tmp_long;
    reg[64-1:0] local_in;
    integer char_num;
    integer long_num;
    integer i;
    integer j;
    begin
        long_num = (in_bw + 63) / 64;
        char_num = ((in_bw - 1) % 64 + 7) / 8;
        for(i=long_num;i>0;i=i-1) begin
             local_in = in;
             tmp_long = local_in >> ((i-1)*64);
             for(j=0;j<64;j=j+1)
                 if (tmp_long[j] === 1'bx)
                     tmp_long[j] = 1'b0;
             if (i == long_num) begin
                 case(char_num)
                     1: $fwrite(fp,"%c",tmp_long[7:0]);
                     2: $fwrite(fp,"%c%c",tmp_long[15:8],tmp_long[7:0]);
                     3: $fwrite(fp,"%c%c%c",tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     4: $fwrite(fp,"%c%c%c%c",tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     5: $fwrite(fp,"%c%c%c%c%c",tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     6: $fwrite(fp,"%c%c%c%c%c%c",tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     7: $fwrite(fp,"%c%c%c%c%c%c%c",tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     8: $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     default: ;
                 endcase
             end
             else begin
                 $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
             end
        end
    end
endtask;
//------------------------Read file------------------------ 
 
// Read data from file 
initial begin : read_height_file_process 
  integer fp; 
  integer ret; 
  integer factor; 
  reg [127 : 0] token; 
  reg [127 : 0] token_tmp; 
  //reg [height_c_bitwidth - 1 : 0] token_tmp; 
  reg [DATA_WIDTH - 1 : 0] tmp_cache_mem; 
  reg [ 8*5 : 1] str;
    reg [63:0] trans_depth;
  integer transaction_idx; 
  integer i; 
  transaction_idx = 0; 
  tmp_cache_mem [DATA_WIDTH - 1 : 0] = 0;
  count_seperate_factor_by_bitwidth (height_c_bitwidth , factor);
  fp = $fopen(`TV_IN_height ,"r"); 
  if(fp == 0) begin                               // Failed to open file 
      $display("Failed to open file \"%s\"!", `TV_IN_height); 
      $finish; 
  end 
  read_token(fp, token); 
  if (token != "[[[runtime]]]") begin             // Illegal format 
      $display("ERROR: Simulation using HLS TB failed.");
      $finish; 
  end 
  read_token(fp, token); 
  while (token != "[[[/runtime]]]") begin 
      if (token != "[[transaction]]") begin 
          $display("ERROR: Simulation using HLS TB failed.");
          $finish; 
      end 
      read_token(fp, token);                        // skip transaction number 
      @(posedge clk);
      # 0.2;
      while(AESL_ready_reg !== 1) begin
          @(posedge clk); 
          # 0.2;
      end
      for(i = 0; i < height_DEPTH; i = i + 1) begin 
          read_token(fp, token); 
          ret = $sscanf(token, "0x%x", token_tmp); 
          if (factor == 4) begin
              if (i%factor == 0) begin
                  tmp_cache_mem [7 : 0] = token_tmp;
              end
              if (i%factor == 1) begin
                  tmp_cache_mem [15 : 8] = token_tmp;
              end
              if (i%factor == 2) begin
                  tmp_cache_mem [23 : 16] = token_tmp;
              end
              if (i%factor == 3) begin
                  tmp_cache_mem [31 : 24] = token_tmp;
                  mem_height [i/factor] = tmp_cache_mem;
                  tmp_cache_mem [DATA_WIDTH - 1 : 0] = 0;
              end
          end
          if (factor == 2) begin
              if (i%factor == 0) begin
                  tmp_cache_mem [15 : 0] = token_tmp;
              end
              if (i%factor == 1) begin
                  tmp_cache_mem [31 : 16] = token_tmp;
                  mem_height [i/factor] = tmp_cache_mem;
                  tmp_cache_mem [DATA_WIDTH - 1: 0] = 0;
              end
          end
          if (factor == 1) begin
              mem_height [i] = token_tmp;
          end
      end 
      if (factor == 4) begin
          if (i%factor != 0) begin
              mem_height [i/factor] = tmp_cache_mem;
          end
      end
      if (factor == 2) begin
          if (i%factor != 0) begin
              mem_height [i/factor] = tmp_cache_mem;
          end
      end 
      read_token(fp, token); 
      if(token != "[[/transaction]]") begin 
          $display("ERROR: Simulation using HLS TB failed.");
          $finish; 
      end 
      read_token(fp, token); 
      transaction_idx = transaction_idx + 1; 
  end 
  $fclose(fp); 
end 
 
task write_binary_height;
    input integer fp;
    input reg[64-1:0] in;
    input integer in_bw;
    reg [63:0] tmp_long;
    reg[64-1:0] local_in;
    integer char_num;
    integer long_num;
    integer i;
    integer j;
    begin
        long_num = (in_bw + 63) / 64;
        char_num = ((in_bw - 1) % 64 + 7) / 8;
        for(i=long_num;i>0;i=i-1) begin
             local_in = in;
             tmp_long = local_in >> ((i-1)*64);
             for(j=0;j<64;j=j+1)
                 if (tmp_long[j] === 1'bx)
                     tmp_long[j] = 1'b0;
             if (i == long_num) begin
                 case(char_num)
                     1: $fwrite(fp,"%c",tmp_long[7:0]);
                     2: $fwrite(fp,"%c%c",tmp_long[15:8],tmp_long[7:0]);
                     3: $fwrite(fp,"%c%c%c",tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     4: $fwrite(fp,"%c%c%c%c",tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     5: $fwrite(fp,"%c%c%c%c%c",tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     6: $fwrite(fp,"%c%c%c%c%c%c",tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     7: $fwrite(fp,"%c%c%c%c%c%c%c",tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     8: $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     default: ;
                 endcase
             end
             else begin
                 $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
             end
        end
    end
endtask;
//------------------------Read file------------------------ 
 
// Read data from file 
initial begin : read_mode_file_process 
  integer fp; 
  integer ret; 
  integer factor; 
  reg [127 : 0] token; 
  reg [127 : 0] token_tmp; 
  //reg [mode_c_bitwidth - 1 : 0] token_tmp; 
  reg [DATA_WIDTH - 1 : 0] tmp_cache_mem; 
  reg [ 8*5 : 1] str;
    reg [63:0] trans_depth;
  integer transaction_idx; 
  integer i; 
  transaction_idx = 0; 
  tmp_cache_mem [DATA_WIDTH - 1 : 0] = 0;
  count_seperate_factor_by_bitwidth (mode_c_bitwidth , factor);
  fp = $fopen(`TV_IN_mode ,"r"); 
  if(fp == 0) begin                               // Failed to open file 
      $display("Failed to open file \"%s\"!", `TV_IN_mode); 
      $finish; 
  end 
  read_token(fp, token); 
  if (token != "[[[runtime]]]") begin             // Illegal format 
      $display("ERROR: Simulation using HLS TB failed.");
      $finish; 
  end 
  read_token(fp, token); 
  while (token != "[[[/runtime]]]") begin 
      if (token != "[[transaction]]") begin 
          $display("ERROR: Simulation using HLS TB failed.");
          $finish; 
      end 
      read_token(fp, token);                        // skip transaction number 
      @(posedge clk);
      # 0.2;
      while(AESL_ready_reg !== 1) begin
          @(posedge clk); 
          # 0.2;
      end
      for(i = 0; i < mode_DEPTH; i = i + 1) begin 
          read_token(fp, token); 
          ret = $sscanf(token, "0x%x", token_tmp); 
          if (factor == 4) begin
              if (i%factor == 0) begin
                  tmp_cache_mem [7 : 0] = token_tmp;
              end
              if (i%factor == 1) begin
                  tmp_cache_mem [15 : 8] = token_tmp;
              end
              if (i%factor == 2) begin
                  tmp_cache_mem [23 : 16] = token_tmp;
              end
              if (i%factor == 3) begin
                  tmp_cache_mem [31 : 24] = token_tmp;
                  mem_mode [i/factor] = tmp_cache_mem;
                  tmp_cache_mem [DATA_WIDTH - 1 : 0] = 0;
              end
          end
          if (factor == 2) begin
              if (i%factor == 0) begin
                  tmp_cache_mem [15 : 0] = token_tmp;
              end
              if (i%factor == 1) begin
                  tmp_cache_mem [31 : 16] = token_tmp;
                  mem_mode [i/factor] = tmp_cache_mem;
                  tmp_cache_mem [DATA_WIDTH - 1: 0] = 0;
              end
          end
          if (factor == 1) begin
              mem_mode [i] = token_tmp;
          end
      end 
      if (factor == 4) begin
          if (i%factor != 0) begin
              mem_mode [i/factor] = tmp_cache_mem;
          end
      end
      if (factor == 2) begin
          if (i%factor != 0) begin
              mem_mode [i/factor] = tmp_cache_mem;
          end
      end 
      read_token(fp, token); 
      if(token != "[[/transaction]]") begin 
          $display("ERROR: Simulation using HLS TB failed.");
          $finish; 
      end 
      read_token(fp, token); 
      transaction_idx = transaction_idx + 1; 
  end 
  $fclose(fp); 
end 
 
task write_binary_mode;
    input integer fp;
    input reg[64-1:0] in;
    input integer in_bw;
    reg [63:0] tmp_long;
    reg[64-1:0] local_in;
    integer char_num;
    integer long_num;
    integer i;
    integer j;
    begin
        long_num = (in_bw + 63) / 64;
        char_num = ((in_bw - 1) % 64 + 7) / 8;
        for(i=long_num;i>0;i=i-1) begin
             local_in = in;
             tmp_long = local_in >> ((i-1)*64);
             for(j=0;j<64;j=j+1)
                 if (tmp_long[j] === 1'bx)
                     tmp_long[j] = 1'b0;
             if (i == long_num) begin
                 case(char_num)
                     1: $fwrite(fp,"%c",tmp_long[7:0]);
                     2: $fwrite(fp,"%c%c",tmp_long[15:8],tmp_long[7:0]);
                     3: $fwrite(fp,"%c%c%c",tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     4: $fwrite(fp,"%c%c%c%c",tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     5: $fwrite(fp,"%c%c%c%c%c",tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     6: $fwrite(fp,"%c%c%c%c%c%c",tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     7: $fwrite(fp,"%c%c%c%c%c%c%c",tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     8: $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     default: ;
                 endcase
             end
             else begin
                 $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
             end
        end
    end
endtask;
//------------------------Read file------------------------ 
 
// Read data from file 
initial begin : read_dark_pixel_threshold_file_process 
  integer fp; 
  integer ret; 
  integer factor; 
  reg [127 : 0] token; 
  reg [127 : 0] token_tmp; 
  //reg [dark_pixel_threshold_c_bitwidth - 1 : 0] token_tmp; 
  reg [DATA_WIDTH - 1 : 0] tmp_cache_mem; 
  reg [ 8*5 : 1] str;
    reg [63:0] trans_depth;
  integer transaction_idx; 
  integer i; 
  transaction_idx = 0; 
  tmp_cache_mem [DATA_WIDTH - 1 : 0] = 0;
  count_seperate_factor_by_bitwidth (dark_pixel_threshold_c_bitwidth , factor);
  fp = $fopen(`TV_IN_dark_pixel_threshold ,"r"); 
  if(fp == 0) begin                               // Failed to open file 
      $display("Failed to open file \"%s\"!", `TV_IN_dark_pixel_threshold); 
      $finish; 
  end 
  read_token(fp, token); 
  if (token != "[[[runtime]]]") begin             // Illegal format 
      $display("ERROR: Simulation using HLS TB failed.");
      $finish; 
  end 
  read_token(fp, token); 
  while (token != "[[[/runtime]]]") begin 
      if (token != "[[transaction]]") begin 
          $display("ERROR: Simulation using HLS TB failed.");
          $finish; 
      end 
      read_token(fp, token);                        // skip transaction number 
      @(posedge clk);
      # 0.2;
      while(AESL_ready_reg !== 1) begin
          @(posedge clk); 
          # 0.2;
      end
      for(i = 0; i < dark_pixel_threshold_DEPTH; i = i + 1) begin 
          read_token(fp, token); 
          ret = $sscanf(token, "0x%x", token_tmp); 
          if (factor == 4) begin
              if (i%factor == 0) begin
                  tmp_cache_mem [7 : 0] = token_tmp;
              end
              if (i%factor == 1) begin
                  tmp_cache_mem [15 : 8] = token_tmp;
              end
              if (i%factor == 2) begin
                  tmp_cache_mem [23 : 16] = token_tmp;
              end
              if (i%factor == 3) begin
                  tmp_cache_mem [31 : 24] = token_tmp;
                  mem_dark_pixel_threshold [i/factor] = tmp_cache_mem;
                  tmp_cache_mem [DATA_WIDTH - 1 : 0] = 0;
              end
          end
          if (factor == 2) begin
              if (i%factor == 0) begin
                  tmp_cache_mem [15 : 0] = token_tmp;
              end
              if (i%factor == 1) begin
                  tmp_cache_mem [31 : 16] = token_tmp;
                  mem_dark_pixel_threshold [i/factor] = tmp_cache_mem;
                  tmp_cache_mem [DATA_WIDTH - 1: 0] = 0;
              end
          end
          if (factor == 1) begin
              mem_dark_pixel_threshold [i] = token_tmp;
          end
      end 
      if (factor == 4) begin
          if (i%factor != 0) begin
              mem_dark_pixel_threshold [i/factor] = tmp_cache_mem;
          end
      end
      if (factor == 2) begin
          if (i%factor != 0) begin
              mem_dark_pixel_threshold [i/factor] = tmp_cache_mem;
          end
      end 
      read_token(fp, token); 
      if(token != "[[/transaction]]") begin 
          $display("ERROR: Simulation using HLS TB failed.");
          $finish; 
      end 
      read_token(fp, token); 
      transaction_idx = transaction_idx + 1; 
  end 
  $fclose(fp); 
end 
 
task write_binary_dark_pixel_threshold;
    input integer fp;
    input reg[64-1:0] in;
    input integer in_bw;
    reg [63:0] tmp_long;
    reg[64-1:0] local_in;
    integer char_num;
    integer long_num;
    integer i;
    integer j;
    begin
        long_num = (in_bw + 63) / 64;
        char_num = ((in_bw - 1) % 64 + 7) / 8;
        for(i=long_num;i>0;i=i-1) begin
             local_in = in;
             tmp_long = local_in >> ((i-1)*64);
             for(j=0;j<64;j=j+1)
                 if (tmp_long[j] === 1'bx)
                     tmp_long[j] = 1'b0;
             if (i == long_num) begin
                 case(char_num)
                     1: $fwrite(fp,"%c",tmp_long[7:0]);
                     2: $fwrite(fp,"%c%c",tmp_long[15:8],tmp_long[7:0]);
                     3: $fwrite(fp,"%c%c%c",tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     4: $fwrite(fp,"%c%c%c%c",tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     5: $fwrite(fp,"%c%c%c%c%c",tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     6: $fwrite(fp,"%c%c%c%c%c%c",tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     7: $fwrite(fp,"%c%c%c%c%c%c%c",tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     8: $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     default: ;
                 endcase
             end
             else begin
                 $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
             end
        end
    end
endtask;
//------------------------Read file------------------------ 
 
// Read data from file 
initial begin : read_verdict_pct_file_process 
  integer fp; 
  integer ret; 
  integer factor; 
  reg [127 : 0] token; 
  reg [127 : 0] token_tmp; 
  //reg [verdict_pct_c_bitwidth - 1 : 0] token_tmp; 
  reg [DATA_WIDTH - 1 : 0] tmp_cache_mem; 
  reg [ 8*5 : 1] str;
    reg [63:0] trans_depth;
  integer transaction_idx; 
  integer i; 
  transaction_idx = 0; 
  tmp_cache_mem [DATA_WIDTH - 1 : 0] = 0;
  count_seperate_factor_by_bitwidth (verdict_pct_c_bitwidth , factor);
  fp = $fopen(`TV_IN_verdict_pct ,"r"); 
  if(fp == 0) begin                               // Failed to open file 
      $display("Failed to open file \"%s\"!", `TV_IN_verdict_pct); 
      $finish; 
  end 
  read_token(fp, token); 
  if (token != "[[[runtime]]]") begin             // Illegal format 
      $display("ERROR: Simulation using HLS TB failed.");
      $finish; 
  end 
  read_token(fp, token); 
  while (token != "[[[/runtime]]]") begin 
      if (token != "[[transaction]]") begin 
          $display("ERROR: Simulation using HLS TB failed.");
          $finish; 
      end 
      read_token(fp, token);                        // skip transaction number 
      @(posedge clk);
      # 0.2;
      while(AESL_ready_reg !== 1) begin
          @(posedge clk); 
          # 0.2;
      end
      for(i = 0; i < verdict_pct_DEPTH; i = i + 1) begin 
          read_token(fp, token); 
          ret = $sscanf(token, "0x%x", token_tmp); 
          if (factor == 4) begin
              if (i%factor == 0) begin
                  tmp_cache_mem [7 : 0] = token_tmp;
              end
              if (i%factor == 1) begin
                  tmp_cache_mem [15 : 8] = token_tmp;
              end
              if (i%factor == 2) begin
                  tmp_cache_mem [23 : 16] = token_tmp;
              end
              if (i%factor == 3) begin
                  tmp_cache_mem [31 : 24] = token_tmp;
                  mem_verdict_pct [i/factor] = tmp_cache_mem;
                  tmp_cache_mem [DATA_WIDTH - 1 : 0] = 0;
              end
          end
          if (factor == 2) begin
              if (i%factor == 0) begin
                  tmp_cache_mem [15 : 0] = token_tmp;
              end
              if (i%factor == 1) begin
                  tmp_cache_mem [31 : 16] = token_tmp;
                  mem_verdict_pct [i/factor] = tmp_cache_mem;
                  tmp_cache_mem [DATA_WIDTH - 1: 0] = 0;
              end
          end
          if (factor == 1) begin
              mem_verdict_pct [i] = token_tmp;
          end
      end 
      if (factor == 4) begin
          if (i%factor != 0) begin
              mem_verdict_pct [i/factor] = tmp_cache_mem;
          end
      end
      if (factor == 2) begin
          if (i%factor != 0) begin
              mem_verdict_pct [i/factor] = tmp_cache_mem;
          end
      end 
      read_token(fp, token); 
      if(token != "[[/transaction]]") begin 
          $display("ERROR: Simulation using HLS TB failed.");
          $finish; 
      end 
      read_token(fp, token); 
      transaction_idx = transaction_idx + 1; 
  end 
  $fclose(fp); 
end 
 
task write_binary_verdict_pct;
    input integer fp;
    input reg[64-1:0] in;
    input integer in_bw;
    reg [63:0] tmp_long;
    reg[64-1:0] local_in;
    integer char_num;
    integer long_num;
    integer i;
    integer j;
    begin
        long_num = (in_bw + 63) / 64;
        char_num = ((in_bw - 1) % 64 + 7) / 8;
        for(i=long_num;i>0;i=i-1) begin
             local_in = in;
             tmp_long = local_in >> ((i-1)*64);
             for(j=0;j<64;j=j+1)
                 if (tmp_long[j] === 1'bx)
                     tmp_long[j] = 1'b0;
             if (i == long_num) begin
                 case(char_num)
                     1: $fwrite(fp,"%c",tmp_long[7:0]);
                     2: $fwrite(fp,"%c%c",tmp_long[15:8],tmp_long[7:0]);
                     3: $fwrite(fp,"%c%c%c",tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     4: $fwrite(fp,"%c%c%c%c",tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     5: $fwrite(fp,"%c%c%c%c%c",tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     6: $fwrite(fp,"%c%c%c%c%c%c",tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     7: $fwrite(fp,"%c%c%c%c%c%c%c",tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     8: $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     default: ;
                 endcase
             end
             else begin
                 $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
             end
        end
    end
endtask;
//------------------------Read file------------------------ 
 
// Read data from file 
initial begin : read_enter_pct_file_process 
  integer fp; 
  integer ret; 
  integer factor; 
  reg [127 : 0] token; 
  reg [127 : 0] token_tmp; 
  //reg [enter_pct_c_bitwidth - 1 : 0] token_tmp; 
  reg [DATA_WIDTH - 1 : 0] tmp_cache_mem; 
  reg [ 8*5 : 1] str;
    reg [63:0] trans_depth;
  integer transaction_idx; 
  integer i; 
  transaction_idx = 0; 
  tmp_cache_mem [DATA_WIDTH - 1 : 0] = 0;
  count_seperate_factor_by_bitwidth (enter_pct_c_bitwidth , factor);
  fp = $fopen(`TV_IN_enter_pct ,"r"); 
  if(fp == 0) begin                               // Failed to open file 
      $display("Failed to open file \"%s\"!", `TV_IN_enter_pct); 
      $finish; 
  end 
  read_token(fp, token); 
  if (token != "[[[runtime]]]") begin             // Illegal format 
      $display("ERROR: Simulation using HLS TB failed.");
      $finish; 
  end 
  read_token(fp, token); 
  while (token != "[[[/runtime]]]") begin 
      if (token != "[[transaction]]") begin 
          $display("ERROR: Simulation using HLS TB failed.");
          $finish; 
      end 
      read_token(fp, token);                        // skip transaction number 
      @(posedge clk);
      # 0.2;
      while(AESL_ready_reg !== 1) begin
          @(posedge clk); 
          # 0.2;
      end
      for(i = 0; i < enter_pct_DEPTH; i = i + 1) begin 
          read_token(fp, token); 
          ret = $sscanf(token, "0x%x", token_tmp); 
          if (factor == 4) begin
              if (i%factor == 0) begin
                  tmp_cache_mem [7 : 0] = token_tmp;
              end
              if (i%factor == 1) begin
                  tmp_cache_mem [15 : 8] = token_tmp;
              end
              if (i%factor == 2) begin
                  tmp_cache_mem [23 : 16] = token_tmp;
              end
              if (i%factor == 3) begin
                  tmp_cache_mem [31 : 24] = token_tmp;
                  mem_enter_pct [i/factor] = tmp_cache_mem;
                  tmp_cache_mem [DATA_WIDTH - 1 : 0] = 0;
              end
          end
          if (factor == 2) begin
              if (i%factor == 0) begin
                  tmp_cache_mem [15 : 0] = token_tmp;
              end
              if (i%factor == 1) begin
                  tmp_cache_mem [31 : 16] = token_tmp;
                  mem_enter_pct [i/factor] = tmp_cache_mem;
                  tmp_cache_mem [DATA_WIDTH - 1: 0] = 0;
              end
          end
          if (factor == 1) begin
              mem_enter_pct [i] = token_tmp;
          end
      end 
      if (factor == 4) begin
          if (i%factor != 0) begin
              mem_enter_pct [i/factor] = tmp_cache_mem;
          end
      end
      if (factor == 2) begin
          if (i%factor != 0) begin
              mem_enter_pct [i/factor] = tmp_cache_mem;
          end
      end 
      read_token(fp, token); 
      if(token != "[[/transaction]]") begin 
          $display("ERROR: Simulation using HLS TB failed.");
          $finish; 
      end 
      read_token(fp, token); 
      transaction_idx = transaction_idx + 1; 
  end 
  $fclose(fp); 
end 
 
task write_binary_enter_pct;
    input integer fp;
    input reg[64-1:0] in;
    input integer in_bw;
    reg [63:0] tmp_long;
    reg[64-1:0] local_in;
    integer char_num;
    integer long_num;
    integer i;
    integer j;
    begin
        long_num = (in_bw + 63) / 64;
        char_num = ((in_bw - 1) % 64 + 7) / 8;
        for(i=long_num;i>0;i=i-1) begin
             local_in = in;
             tmp_long = local_in >> ((i-1)*64);
             for(j=0;j<64;j=j+1)
                 if (tmp_long[j] === 1'bx)
                     tmp_long[j] = 1'b0;
             if (i == long_num) begin
                 case(char_num)
                     1: $fwrite(fp,"%c",tmp_long[7:0]);
                     2: $fwrite(fp,"%c%c",tmp_long[15:8],tmp_long[7:0]);
                     3: $fwrite(fp,"%c%c%c",tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     4: $fwrite(fp,"%c%c%c%c",tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     5: $fwrite(fp,"%c%c%c%c%c",tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     6: $fwrite(fp,"%c%c%c%c%c%c",tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     7: $fwrite(fp,"%c%c%c%c%c%c%c",tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     8: $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     default: ;
                 endcase
             end
             else begin
                 $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
             end
        end
    end
endtask;
//------------------------Read file------------------------ 
 
// Read data from file 
initial begin : read_exit_pct_file_process 
  integer fp; 
  integer ret; 
  integer factor; 
  reg [127 : 0] token; 
  reg [127 : 0] token_tmp; 
  //reg [exit_pct_c_bitwidth - 1 : 0] token_tmp; 
  reg [DATA_WIDTH - 1 : 0] tmp_cache_mem; 
  reg [ 8*5 : 1] str;
    reg [63:0] trans_depth;
  integer transaction_idx; 
  integer i; 
  transaction_idx = 0; 
  tmp_cache_mem [DATA_WIDTH - 1 : 0] = 0;
  count_seperate_factor_by_bitwidth (exit_pct_c_bitwidth , factor);
  fp = $fopen(`TV_IN_exit_pct ,"r"); 
  if(fp == 0) begin                               // Failed to open file 
      $display("Failed to open file \"%s\"!", `TV_IN_exit_pct); 
      $finish; 
  end 
  read_token(fp, token); 
  if (token != "[[[runtime]]]") begin             // Illegal format 
      $display("ERROR: Simulation using HLS TB failed.");
      $finish; 
  end 
  read_token(fp, token); 
  while (token != "[[[/runtime]]]") begin 
      if (token != "[[transaction]]") begin 
          $display("ERROR: Simulation using HLS TB failed.");
          $finish; 
      end 
      read_token(fp, token);                        // skip transaction number 
      @(posedge clk);
      # 0.2;
      while(AESL_ready_reg !== 1) begin
          @(posedge clk); 
          # 0.2;
      end
      for(i = 0; i < exit_pct_DEPTH; i = i + 1) begin 
          read_token(fp, token); 
          ret = $sscanf(token, "0x%x", token_tmp); 
          if (factor == 4) begin
              if (i%factor == 0) begin
                  tmp_cache_mem [7 : 0] = token_tmp;
              end
              if (i%factor == 1) begin
                  tmp_cache_mem [15 : 8] = token_tmp;
              end
              if (i%factor == 2) begin
                  tmp_cache_mem [23 : 16] = token_tmp;
              end
              if (i%factor == 3) begin
                  tmp_cache_mem [31 : 24] = token_tmp;
                  mem_exit_pct [i/factor] = tmp_cache_mem;
                  tmp_cache_mem [DATA_WIDTH - 1 : 0] = 0;
              end
          end
          if (factor == 2) begin
              if (i%factor == 0) begin
                  tmp_cache_mem [15 : 0] = token_tmp;
              end
              if (i%factor == 1) begin
                  tmp_cache_mem [31 : 16] = token_tmp;
                  mem_exit_pct [i/factor] = tmp_cache_mem;
                  tmp_cache_mem [DATA_WIDTH - 1: 0] = 0;
              end
          end
          if (factor == 1) begin
              mem_exit_pct [i] = token_tmp;
          end
      end 
      if (factor == 4) begin
          if (i%factor != 0) begin
              mem_exit_pct [i/factor] = tmp_cache_mem;
          end
      end
      if (factor == 2) begin
          if (i%factor != 0) begin
              mem_exit_pct [i/factor] = tmp_cache_mem;
          end
      end 
      read_token(fp, token); 
      if(token != "[[/transaction]]") begin 
          $display("ERROR: Simulation using HLS TB failed.");
          $finish; 
      end 
      read_token(fp, token); 
      transaction_idx = transaction_idx + 1; 
  end 
  $fclose(fp); 
end 
 
task write_binary_exit_pct;
    input integer fp;
    input reg[64-1:0] in;
    input integer in_bw;
    reg [63:0] tmp_long;
    reg[64-1:0] local_in;
    integer char_num;
    integer long_num;
    integer i;
    integer j;
    begin
        long_num = (in_bw + 63) / 64;
        char_num = ((in_bw - 1) % 64 + 7) / 8;
        for(i=long_num;i>0;i=i-1) begin
             local_in = in;
             tmp_long = local_in >> ((i-1)*64);
             for(j=0;j<64;j=j+1)
                 if (tmp_long[j] === 1'bx)
                     tmp_long[j] = 1'b0;
             if (i == long_num) begin
                 case(char_num)
                     1: $fwrite(fp,"%c",tmp_long[7:0]);
                     2: $fwrite(fp,"%c%c",tmp_long[15:8],tmp_long[7:0]);
                     3: $fwrite(fp,"%c%c%c",tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     4: $fwrite(fp,"%c%c%c%c",tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     5: $fwrite(fp,"%c%c%c%c%c",tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     6: $fwrite(fp,"%c%c%c%c%c%c",tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     7: $fwrite(fp,"%c%c%c%c%c%c%c",tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     8: $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     default: ;
                 endcase
             end
             else begin
                 $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
             end
        end
    end
endtask;
task write_binary_selected_mode;
    input integer fp;
    input reg[64-1:0] in;
    input integer in_bw;
    reg [63:0] tmp_long;
    reg[64-1:0] local_in;
    integer char_num;
    integer long_num;
    integer i;
    integer j;
    begin
        long_num = (in_bw + 63) / 64;
        char_num = ((in_bw - 1) % 64 + 7) / 8;
        for(i=long_num;i>0;i=i-1) begin
             local_in = in;
             tmp_long = local_in >> ((i-1)*64);
             for(j=0;j<64;j=j+1)
                 if (tmp_long[j] === 1'bx)
                     tmp_long[j] = 1'b0;
             if (i == long_num) begin
                 case(char_num)
                     1: $fwrite(fp,"%c",tmp_long[7:0]);
                     2: $fwrite(fp,"%c%c",tmp_long[15:8],tmp_long[7:0]);
                     3: $fwrite(fp,"%c%c%c",tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     4: $fwrite(fp,"%c%c%c%c",tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     5: $fwrite(fp,"%c%c%c%c%c",tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     6: $fwrite(fp,"%c%c%c%c%c%c",tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     7: $fwrite(fp,"%c%c%c%c%c%c%c",tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     8: $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     default: ;
                 endcase
             end
             else begin
                 $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
             end
        end
    end
endtask;
//------------------------Write file----------------------- 
 
// Write data to file 
 
initial begin : write_selected_mode_file_proc 
  integer fp; 
  integer factor; 
  integer transaction_idx; 
  reg [selected_mode_c_bitwidth - 1 : 0] tmp_cache_mem; 
  reg [ 100*8 : 1] str;
  reg [63:0] bin_data;
  integer i; 
  transaction_idx = 0; 
  count_seperate_factor_by_bitwidth (selected_mode_c_bitwidth , factor);
  while(1) begin 
      @(posedge clk);
      while (selected_mode_read_data_finish !== 1 || TRAN_control_transaction_done_in === 1) begin
          @(posedge clk);
      end
      # 0.1;
      fp = $fopen(`TV_OUT_selected_mode, "a"); 
      if(fp == 0) begin       // Failed to open file 
          $display("Failed to open file \"%s\"!", `TV_OUT_selected_mode); 
          $finish; 
      end 
      $fdisplay(fp, "[[transaction]] %d", transaction_idx);
      for (i = 0; i < (selected_mode_DEPTH - selected_mode_DEPTH % factor); i = i + 1) begin
          if (factor == 4) begin
              if (i%factor == 0) begin
                  tmp_cache_mem = mem_selected_mode[i/factor][7:0];
              end
              if (i%factor == 1) begin
                  tmp_cache_mem = mem_selected_mode[i/factor][15:8];
              end
              if (i%factor == 2) begin
                  tmp_cache_mem = mem_selected_mode[i/factor][23:16];
              end
              if (i%factor == 3) begin
                  tmp_cache_mem = mem_selected_mode[i/factor][31:24];
              end
              $fdisplay(fp,"0x%x",tmp_cache_mem);
          end
          if (factor == 2) begin
              if (i%factor == 0) begin
                  tmp_cache_mem = mem_selected_mode[i/factor][15:0];
              end
              if (i%factor == 1) begin
                  tmp_cache_mem = mem_selected_mode[i/factor][31:16];
              end
              $fdisplay(fp,"0x%x",tmp_cache_mem);
          end
          if (factor == 1) begin
              $fdisplay(fp,"0x%x",mem_selected_mode[i]);
          end
      end 
      if (factor == 4) begin
          if ((selected_mode_DEPTH - 1) % factor == 2) begin
              $fdisplay(fp,"0x%x",mem_selected_mode[selected_mode_DEPTH / factor][7:0]);
              $fdisplay(fp,"0x%x",mem_selected_mode[selected_mode_DEPTH / factor][15:8]);
              $fdisplay(fp,"0x%x",mem_selected_mode[selected_mode_DEPTH / factor][23:16]);
          end
          if ((selected_mode_DEPTH - 1) % factor == 1) begin
              $fdisplay(fp,"0x%x",mem_selected_mode[selected_mode_DEPTH / factor][7:0]);
              $fdisplay(fp,"0x%x",mem_selected_mode[selected_mode_DEPTH / factor][15:8]);
          end
          if ((selected_mode_DEPTH - 1) % factor == 0) begin
              $fdisplay(fp,"0x%x",mem_selected_mode[selected_mode_DEPTH / factor][7:0]);
          end
      end
      if (factor == 2) begin
          if ((selected_mode_DEPTH - 1) % factor == 0) begin
              $fdisplay(fp,"0x%x",mem_selected_mode[selected_mode_DEPTH / factor][15:0]);
          end
      end
      $fdisplay(fp, "[[/transaction]]");
      transaction_idx = transaction_idx + 1;
      $fclose(fp); 
      while (TRAN_control_start_in !== 1) begin
          @(posedge clk);
      end
  end 
end 
 
task write_binary_dark_count;
    input integer fp;
    input reg[64-1:0] in;
    input integer in_bw;
    reg [63:0] tmp_long;
    reg[64-1:0] local_in;
    integer char_num;
    integer long_num;
    integer i;
    integer j;
    begin
        long_num = (in_bw + 63) / 64;
        char_num = ((in_bw - 1) % 64 + 7) / 8;
        for(i=long_num;i>0;i=i-1) begin
             local_in = in;
             tmp_long = local_in >> ((i-1)*64);
             for(j=0;j<64;j=j+1)
                 if (tmp_long[j] === 1'bx)
                     tmp_long[j] = 1'b0;
             if (i == long_num) begin
                 case(char_num)
                     1: $fwrite(fp,"%c",tmp_long[7:0]);
                     2: $fwrite(fp,"%c%c",tmp_long[15:8],tmp_long[7:0]);
                     3: $fwrite(fp,"%c%c%c",tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     4: $fwrite(fp,"%c%c%c%c",tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     5: $fwrite(fp,"%c%c%c%c%c",tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     6: $fwrite(fp,"%c%c%c%c%c%c",tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     7: $fwrite(fp,"%c%c%c%c%c%c%c",tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     8: $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
                     default: ;
                 endcase
             end
             else begin
                 $fwrite(fp,"%c%c%c%c%c%c%c%c",tmp_long[63:56],tmp_long[55:48],tmp_long[47:40],tmp_long[39:32],tmp_long[31:24],tmp_long[23:16],tmp_long[15:8],tmp_long[7:0]);
             end
        end
    end
endtask;
//------------------------Write file----------------------- 
 
// Write data to file 
 
initial begin : write_dark_count_file_proc 
  integer fp; 
  integer factor; 
  integer transaction_idx; 
  reg [dark_count_c_bitwidth - 1 : 0] tmp_cache_mem; 
  reg [ 100*8 : 1] str;
  reg [63:0] bin_data;
  integer i; 
  transaction_idx = 0; 
  count_seperate_factor_by_bitwidth (dark_count_c_bitwidth , factor);
  while(1) begin 
      @(posedge clk);
      while (dark_count_read_data_finish !== 1 || TRAN_control_transaction_done_in === 1) begin
          @(posedge clk);
      end
      # 0.1;
      fp = $fopen(`TV_OUT_dark_count, "a"); 
      if(fp == 0) begin       // Failed to open file 
          $display("Failed to open file \"%s\"!", `TV_OUT_dark_count); 
          $finish; 
      end 
      $fdisplay(fp, "[[transaction]] %d", transaction_idx);
      for (i = 0; i < (dark_count_DEPTH - dark_count_DEPTH % factor); i = i + 1) begin
          if (factor == 4) begin
              if (i%factor == 0) begin
                  tmp_cache_mem = mem_dark_count[i/factor][7:0];
              end
              if (i%factor == 1) begin
                  tmp_cache_mem = mem_dark_count[i/factor][15:8];
              end
              if (i%factor == 2) begin
                  tmp_cache_mem = mem_dark_count[i/factor][23:16];
              end
              if (i%factor == 3) begin
                  tmp_cache_mem = mem_dark_count[i/factor][31:24];
              end
              $fdisplay(fp,"0x%x",tmp_cache_mem);
          end
          if (factor == 2) begin
              if (i%factor == 0) begin
                  tmp_cache_mem = mem_dark_count[i/factor][15:0];
              end
              if (i%factor == 1) begin
                  tmp_cache_mem = mem_dark_count[i/factor][31:16];
              end
              $fdisplay(fp,"0x%x",tmp_cache_mem);
          end
          if (factor == 1) begin
              $fdisplay(fp,"0x%x",mem_dark_count[i]);
          end
      end 
      if (factor == 4) begin
          if ((dark_count_DEPTH - 1) % factor == 2) begin
              $fdisplay(fp,"0x%x",mem_dark_count[dark_count_DEPTH / factor][7:0]);
              $fdisplay(fp,"0x%x",mem_dark_count[dark_count_DEPTH / factor][15:8]);
              $fdisplay(fp,"0x%x",mem_dark_count[dark_count_DEPTH / factor][23:16]);
          end
          if ((dark_count_DEPTH - 1) % factor == 1) begin
              $fdisplay(fp,"0x%x",mem_dark_count[dark_count_DEPTH / factor][7:0]);
              $fdisplay(fp,"0x%x",mem_dark_count[dark_count_DEPTH / factor][15:8]);
          end
          if ((dark_count_DEPTH - 1) % factor == 0) begin
              $fdisplay(fp,"0x%x",mem_dark_count[dark_count_DEPTH / factor][7:0]);
          end
      end
      if (factor == 2) begin
          if ((dark_count_DEPTH - 1) % factor == 0) begin
              $fdisplay(fp,"0x%x",mem_dark_count[dark_count_DEPTH / factor][15:0]);
          end
      end
      $fdisplay(fp, "[[/transaction]]");
      transaction_idx = transaction_idx + 1;
      $fclose(fp); 
      while (TRAN_control_start_in !== 1) begin
          @(posedge clk);
      end
  end 
end 
 
endmodule
