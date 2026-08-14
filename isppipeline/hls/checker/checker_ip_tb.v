`timescale 1ns/1ps
// =============================================================================
// checker_ip_tb.v -- checker_scan real-RTL integration test. Updated 2026-08-06.
// Uses the csynth-generated AXI-Lite map and a burst-capable DDR read model.
// Runtime recalibration uses native HLS offsets 0x3C/0x44/0x4C; 0x0C is the
// ap_ctrl_hs interrupt-status register reserved by Vitis HLS.
// =============================================================================
module checker_ip_tb;
 localparam PROG_CYCLES=32;
 reg aclk=0,aresetn=0; always #2.5 aclk=~aclk;
 reg [6:0] s_axi_control_AWADDR=0,s_axi_control_ARADDR=0; reg s_axi_control_AWVALID=0,s_axi_control_WVALID=0,s_axi_control_BREADY=0,s_axi_control_ARVALID=0,s_axi_control_RREADY=0; reg [31:0] s_axi_control_WDATA=0; reg [3:0] s_axi_control_WSTRB=4'hf;
 wire s_axi_control_AWREADY,s_axi_control_WREADY,s_axi_control_BVALID,s_axi_control_ARREADY,s_axi_control_RVALID; wire [1:0] s_axi_control_BRESP,s_axi_control_RRESP; wire [31:0] s_axi_control_RDATA; wire checker_interrupt;
 reg [5:0] s_axi_status_AWADDR=0,s_axi_status_ARADDR=0;reg s_axi_status_AWVALID=0,s_axi_status_WVALID=0,s_axi_status_BREADY=0,s_axi_status_ARVALID=0,s_axi_status_RREADY=0;reg [31:0] s_axi_status_WDATA=0;reg [3:0] s_axi_status_WSTRB=4'hf;
 wire s_axi_status_AWREADY,s_axi_status_WREADY,s_axi_status_BVALID,s_axi_status_ARREADY,s_axi_status_RVALID;wire [1:0] s_axi_status_BRESP,s_axi_status_RRESP;wire [31:0] s_axi_status_RDATA;
 wire [1:0] vs_hw_triggers;reg vs_rm_shutdown_req=0,vs_rm_decouple=0,rm_ap_idle=1;wire vs_rm_shutdown_ack;
 wire m_axi_gmem0_AWVALID;reg m_axi_gmem0_AWREADY=0;wire [63:0] m_axi_gmem0_AWADDR;wire [0:0] m_axi_gmem0_AWID;wire [7:0] m_axi_gmem0_AWLEN;wire [2:0] m_axi_gmem0_AWSIZE;wire [1:0] m_axi_gmem0_AWBURST,m_axi_gmem0_AWLOCK;wire [3:0] m_axi_gmem0_AWCACHE,m_axi_gmem0_AWQOS,m_axi_gmem0_AWREGION;wire [2:0] m_axi_gmem0_AWPROT;wire [0:0] m_axi_gmem0_AWUSER;
 wire m_axi_gmem0_WVALID;reg m_axi_gmem0_WREADY=0;wire [31:0] m_axi_gmem0_WDATA;wire [3:0] m_axi_gmem0_WSTRB;wire m_axi_gmem0_WLAST;wire [0:0] m_axi_gmem0_WID,m_axi_gmem0_WUSER;
 wire m_axi_gmem0_ARVALID;wire m_axi_gmem0_ARREADY;wire [63:0] m_axi_gmem0_ARADDR;wire [0:0] m_axi_gmem0_ARID;wire [7:0] m_axi_gmem0_ARLEN;wire [2:0] m_axi_gmem0_ARSIZE;wire [1:0] m_axi_gmem0_ARBURST,m_axi_gmem0_ARLOCK;wire [3:0] m_axi_gmem0_ARCACHE,m_axi_gmem0_ARQOS,m_axi_gmem0_ARREGION;wire [2:0] m_axi_gmem0_ARPROT;wire [0:0] m_axi_gmem0_ARUSER;
 wire m_axi_gmem0_RVALID;wire m_axi_gmem0_RREADY;wire [31:0] m_axi_gmem0_RDATA;wire m_axi_gmem0_RLAST;wire [0:0] m_axi_gmem0_RID=0,m_axi_gmem0_RUSER=0;wire [1:0] m_axi_gmem0_RRESP=0;
 reg m_axi_gmem0_BVALID=0;wire m_axi_gmem0_BREADY;reg [1:0] m_axi_gmem0_BRESP=0;reg [0:0] m_axi_gmem0_BID=0,m_axi_gmem0_BUSER=0;

 checker_ip #(.DWELL_FRAMES(0)) dut(.*);

 reg [15:0] mem[0:255]; reg rd_active=0;reg [63:0] rd_addr;reg [7:0] rd_len,rd_beat;
 assign m_axi_gmem0_ARREADY=!rd_active;
 assign m_axi_gmem0_RVALID=rd_active;
 assign m_axi_gmem0_RDATA={mem[(rd_addr>>1)+(rd_beat*2)+1],mem[(rd_addr>>1)+(rd_beat*2)]};
 assign m_axi_gmem0_RLAST=rd_active&&(rd_beat==rd_len);
 always @(posedge aclk) begin
  if(!aresetn) begin rd_active<=0;rd_beat<=0;end
  else begin
   if(m_axi_gmem0_ARVALID&&m_axi_gmem0_ARREADY) begin rd_active<=1;rd_addr<=m_axi_gmem0_ARADDR;rd_len<=m_axi_gmem0_ARLEN;rd_beat<=0;end
   else if(m_axi_gmem0_RVALID&&m_axi_gmem0_RREADY) begin if(rd_beat==rd_len) rd_active<=0;else rd_beat<=rd_beat+1'b1;end
  end
 end

 integer swaps=0,trigger_count=0,errors=0,i;reg [1:0] last_target;
 task check;input cond;input [255:0] tag;begin if(!cond)begin $display("FAIL %0s",tag);errors=errors+1;end else $display("PASS %0s",tag);end endtask
 task ctrl_write;input [6:0] addr;input [31:0] data;begin
  @(negedge aclk);s_axi_control_AWADDR=addr;s_axi_control_AWVALID=1;
  while(!s_axi_control_AWREADY)@(negedge aclk);@(negedge aclk);s_axi_control_AWVALID=0;
  s_axi_control_WDATA=data;s_axi_control_WVALID=1;s_axi_control_BREADY=1;
  while(!s_axi_control_WREADY)@(negedge aclk);@(negedge aclk);s_axi_control_WVALID=0;
  while(!s_axi_control_BVALID)@(negedge aclk);@(negedge aclk);s_axi_control_BREADY=0;
 end endtask
 task ctrl_read;input [6:0] addr;output [31:0] data;begin
  @(negedge aclk);s_axi_control_ARADDR=addr;s_axi_control_ARVALID=1;s_axi_control_RREADY=1;
  while(!s_axi_control_ARREADY)@(negedge aclk);@(negedge aclk);s_axi_control_ARVALID=0;
  while(!s_axi_control_RVALID)@(negedge aclk);data=s_axi_control_RDATA;@(negedge aclk);s_axi_control_RREADY=0;
 end endtask
 task status_read;input [5:0] addr;output [31:0] data;begin
  @(negedge aclk);s_axi_status_ARADDR=addr;s_axi_status_ARVALID=1;s_axi_status_RREADY=1;
  while(!s_axi_status_ARREADY)@(negedge aclk);@(negedge aclk);s_axi_status_ARVALID=0;
  while(!s_axi_status_RVALID)@(negedge aclk);data=s_axi_status_RDATA;@(negedge aclk);s_axi_status_RREADY=0;
 end endtask
 task load_frame;input integer dark_pixels;begin for(i=0;i<100;i=i+1)mem[i]=(i<dark_pixels)?16'd100:16'd1000;end endtask
 task run_frame;reg[31:0]q,prior_count;begin status_read(6'h04,prior_count);ctrl_write(7'h00,1);q=prior_count;while(q==prior_count)status_read(6'h04,q);wait(dut.hyst_flags_ap_vld==0);end endtask

 // Capture the adapter's one-cycle trigger pulse synchronously.  The DFXC
 // model consumes this monotonically increasing event count, so it cannot
 // miss a pulse while returning from the previous swap transaction.
 // dfxc_trigger_adapter HOLDS vs_hw_triggers until pr_busy is observed, so it
 // spans multiple cycles per request -- count 0->nonzero edges, not levels, or
 // one swap is counted several times.
 reg [1:0] prev_hw_triggers=0;
 always @(posedge aclk) begin
  if(!aresetn) begin trigger_count=0;last_target=0;prev_hw_triggers<=0;end
  else begin
   if(|vs_hw_triggers && !(|prev_hw_triggers)) begin trigger_count=trigger_count+1;last_target=vs_hw_triggers;end
   prev_hw_triggers<=vs_hw_triggers;
  end
 end

 always begin
  wait(trigger_count>swaps);rm_ap_idle=0;
  @(negedge aclk);vs_rm_shutdown_req=1;repeat(swaps==0?6:4)@(negedge aclk);
  check(vs_rm_shutdown_ack===0,"shutdown ack held until RM idle");rm_ap_idle=1;wait(vs_rm_shutdown_ack===1);
  @(negedge aclk);vs_rm_shutdown_req=0;vs_rm_decouple=1;repeat(PROG_CYCLES)@(negedge aclk);vs_rm_decouple=0;swaps=swaps+1;
 end

 reg[31:0]q,base_frames;
 initial begin
  repeat(5)@(negedge aclk);aresetn=1;repeat(3)@(negedge aclk);
  ctrl_write(7'h10,0);ctrl_write(7'h14,0);ctrl_write(7'h1c,10);ctrl_write(7'h24,10);ctrl_write(7'h2c,2);ctrl_write(7'h34,256);
  ctrl_write(7'h3c,62);ctrl_write(7'h44,64);ctrl_write(7'h4c,60);
  load_frame(70);run_frame;wait(swaps==1);check(last_target==2'b10,"70 percent enters LOW_LIGHT at enter=64");
  load_frame(62);run_frame;repeat(4)@(negedge aclk);check(swaps==1,"in-band frame holds LOW_LIGHT");
  load_frame(50);run_frame;wait(swaps==2);check(last_target==2'b01,"50 percent exits to NORMAL");
  // Runtime recalibration: identical 70%-dark frame no longer enters at 75,
  // then enters after changing only the AXI-Lite threshold to 65.
  ctrl_write(7'h44,75);load_frame(70);run_frame;repeat(4)@(negedge aclk);check(swaps==2,"runtime enter=75 suppresses 70 percent frame");
  ctrl_write(7'h44,65);load_frame(70);run_frame;wait(swaps==3);check(last_target==2'b10,"runtime enter=65 accepts same frame");
  ctrl_read(7'h64,q);check(q==70,"HLS dark_count register");
  status_read(6'h00,q);check(q[0]==1,"status stable_mode");status_read(6'h04,q);check(q==5,"status frame_cnt");status_read(6'h08,q);check(q==3,"status swap_cnt");
  status_read(6'h0c,q);check(q>=4,"status drain_cycles");status_read(6'h10,q);check(q>=PROG_CYCLES,"status swap_cycles");
  $display("checker_ip probe: frames=5 swaps=3 drain=%0d swap=%0d",dut.drain_cycles,dut.swap_cycles);
  if(errors==0)$display("checker_ip_tb PASS: real HLS RTL, m_axi DDR model, ap_vld, runtime recalibration, status bank");
  else begin $display("checker_ip_tb FAIL (%0d errors)",errors);$fatal;end $finish;
 end
 initial begin #2000000;$display("checker_ip_tb TIMEOUT");$fatal;end
endmodule
