`timescale 1ns/1ps
// =============================================================================
// checker_ip.v -- static checker integration shell. Updated: 2026-08-06.
//
// PS drives checker_scan's generated S_AXI_CONTROL directly; there is no
// internal AXI-Lite master and no duplicate measurement register file.
// checker_scan's M_AXI_GMEM0 is passed through to SmartConnect/DDR.
//
// Separate read-only S_AXI_STATUS map (32-bit words):
//   0x00 stable_mode                  bit 0
//   0x04 frame_cnt                    bits 31:0
//   0x08 swap_cnt                     bits 31:0
//   0x0C drain_cycles                 bits 31:0
//   0x10 swap_cycles                  bits 31:0
// Writes complete with SLVERR and never change state.
// =============================================================================
module checker_ip #(
 parameter integer DWELL_FRAMES=1
)(
 input wire aclk,input wire aresetn,
 // HLS AXI4-Lite control slave (csynth address width is exactly 7 bits).
 input wire [6:0] s_axi_control_AWADDR,input wire s_axi_control_AWVALID,output wire s_axi_control_AWREADY,
 input wire [31:0] s_axi_control_WDATA,input wire [3:0] s_axi_control_WSTRB,input wire s_axi_control_WVALID,output wire s_axi_control_WREADY,
 output wire [1:0] s_axi_control_BRESP,output wire s_axi_control_BVALID,input wire s_axi_control_BREADY,
 input wire [6:0] s_axi_control_ARADDR,input wire s_axi_control_ARVALID,output wire s_axi_control_ARREADY,
 output wire [31:0] s_axi_control_RDATA,output wire [1:0] s_axi_control_RRESP,output wire s_axi_control_RVALID,input wire s_axi_control_RREADY,
 output wire checker_interrupt,
 // HLS m_axi_gmem0, exact Vitis HLS 2024.1 generated widths.
 output wire m_axi_gmem0_AWVALID,input wire m_axi_gmem0_AWREADY,output wire [63:0] m_axi_gmem0_AWADDR,output wire [0:0] m_axi_gmem0_AWID,output wire [7:0] m_axi_gmem0_AWLEN,output wire [2:0] m_axi_gmem0_AWSIZE,output wire [1:0] m_axi_gmem0_AWBURST,output wire [1:0] m_axi_gmem0_AWLOCK,output wire [3:0] m_axi_gmem0_AWCACHE,output wire [2:0] m_axi_gmem0_AWPROT,output wire [3:0] m_axi_gmem0_AWQOS,output wire [3:0] m_axi_gmem0_AWREGION,output wire [0:0] m_axi_gmem0_AWUSER,
 output wire m_axi_gmem0_WVALID,input wire m_axi_gmem0_WREADY,output wire [31:0] m_axi_gmem0_WDATA,output wire [3:0] m_axi_gmem0_WSTRB,output wire m_axi_gmem0_WLAST,output wire [0:0] m_axi_gmem0_WID,output wire [0:0] m_axi_gmem0_WUSER,
 output wire m_axi_gmem0_ARVALID,input wire m_axi_gmem0_ARREADY,output wire [63:0] m_axi_gmem0_ARADDR,output wire [0:0] m_axi_gmem0_ARID,output wire [7:0] m_axi_gmem0_ARLEN,output wire [2:0] m_axi_gmem0_ARSIZE,output wire [1:0] m_axi_gmem0_ARBURST,output wire [1:0] m_axi_gmem0_ARLOCK,output wire [3:0] m_axi_gmem0_ARCACHE,output wire [2:0] m_axi_gmem0_ARPROT,output wire [3:0] m_axi_gmem0_ARQOS,output wire [3:0] m_axi_gmem0_ARREGION,output wire [0:0] m_axi_gmem0_ARUSER,
 input wire m_axi_gmem0_RVALID,output wire m_axi_gmem0_RREADY,input wire [31:0] m_axi_gmem0_RDATA,input wire m_axi_gmem0_RLAST,input wire [0:0] m_axi_gmem0_RID,input wire [0:0] m_axi_gmem0_RUSER,input wire [1:0] m_axi_gmem0_RRESP,
 input wire m_axi_gmem0_BVALID,output wire m_axi_gmem0_BREADY,input wire [1:0] m_axi_gmem0_BRESP,input wire [0:0] m_axi_gmem0_BID,input wire [0:0] m_axi_gmem0_BUSER,
 // Read-only status AXI4-Lite slave.
 input wire [5:0] s_axi_status_AWADDR,input wire s_axi_status_AWVALID,output wire s_axi_status_AWREADY,
 input wire [31:0] s_axi_status_WDATA,input wire [3:0] s_axi_status_WSTRB,input wire s_axi_status_WVALID,output wire s_axi_status_WREADY,
 output wire [1:0] s_axi_status_BRESP,output reg s_axi_status_BVALID,input wire s_axi_status_BREADY,
 input wire [5:0] s_axi_status_ARADDR,input wire s_axi_status_ARVALID,output wire s_axi_status_ARREADY,
 output reg [31:0] s_axi_status_RDATA,output wire [1:0] s_axi_status_RRESP,output reg s_axi_status_RVALID,input wire s_axi_status_RREADY,
 // PG374 VSM boundary and active-RM status.
 output wire [1:0] vs_hw_triggers,input wire vs_rm_shutdown_req,output wire vs_rm_shutdown_ack,input wire vs_rm_decouple,input wire rm_ap_idle
);
 wire [31:0] hyst_flags;
 wire hyst_flags_ap_vld;
 wire stable_mode,pr_trigger,pr_busy;
 wire [31:0] drain_cycles,swap_cycles;
 wire meas_valid;
 reg [31:0] frame_cnt,swap_cnt;

 checker_scan u_scan(
  .ap_clk(aclk),.ap_rst_n(aresetn),
  .m_axi_gmem0_AWVALID(m_axi_gmem0_AWVALID),.m_axi_gmem0_AWREADY(m_axi_gmem0_AWREADY),.m_axi_gmem0_AWADDR(m_axi_gmem0_AWADDR),.m_axi_gmem0_AWID(m_axi_gmem0_AWID),.m_axi_gmem0_AWLEN(m_axi_gmem0_AWLEN),.m_axi_gmem0_AWSIZE(m_axi_gmem0_AWSIZE),.m_axi_gmem0_AWBURST(m_axi_gmem0_AWBURST),.m_axi_gmem0_AWLOCK(m_axi_gmem0_AWLOCK),.m_axi_gmem0_AWCACHE(m_axi_gmem0_AWCACHE),.m_axi_gmem0_AWPROT(m_axi_gmem0_AWPROT),.m_axi_gmem0_AWQOS(m_axi_gmem0_AWQOS),.m_axi_gmem0_AWREGION(m_axi_gmem0_AWREGION),.m_axi_gmem0_AWUSER(m_axi_gmem0_AWUSER),
  .m_axi_gmem0_WVALID(m_axi_gmem0_WVALID),.m_axi_gmem0_WREADY(m_axi_gmem0_WREADY),.m_axi_gmem0_WDATA(m_axi_gmem0_WDATA),.m_axi_gmem0_WSTRB(m_axi_gmem0_WSTRB),.m_axi_gmem0_WLAST(m_axi_gmem0_WLAST),.m_axi_gmem0_WID(m_axi_gmem0_WID),.m_axi_gmem0_WUSER(m_axi_gmem0_WUSER),
  .m_axi_gmem0_ARVALID(m_axi_gmem0_ARVALID),.m_axi_gmem0_ARREADY(m_axi_gmem0_ARREADY),.m_axi_gmem0_ARADDR(m_axi_gmem0_ARADDR),.m_axi_gmem0_ARID(m_axi_gmem0_ARID),.m_axi_gmem0_ARLEN(m_axi_gmem0_ARLEN),.m_axi_gmem0_ARSIZE(m_axi_gmem0_ARSIZE),.m_axi_gmem0_ARBURST(m_axi_gmem0_ARBURST),.m_axi_gmem0_ARLOCK(m_axi_gmem0_ARLOCK),.m_axi_gmem0_ARCACHE(m_axi_gmem0_ARCACHE),.m_axi_gmem0_ARPROT(m_axi_gmem0_ARPROT),.m_axi_gmem0_ARQOS(m_axi_gmem0_ARQOS),.m_axi_gmem0_ARREGION(m_axi_gmem0_ARREGION),.m_axi_gmem0_ARUSER(m_axi_gmem0_ARUSER),
  .m_axi_gmem0_RVALID(m_axi_gmem0_RVALID),.m_axi_gmem0_RREADY(m_axi_gmem0_RREADY),.m_axi_gmem0_RDATA(m_axi_gmem0_RDATA),.m_axi_gmem0_RLAST(m_axi_gmem0_RLAST),.m_axi_gmem0_RID(m_axi_gmem0_RID),.m_axi_gmem0_RUSER(m_axi_gmem0_RUSER),.m_axi_gmem0_RRESP(m_axi_gmem0_RRESP),.m_axi_gmem0_BVALID(m_axi_gmem0_BVALID),.m_axi_gmem0_BREADY(m_axi_gmem0_BREADY),.m_axi_gmem0_BRESP(m_axi_gmem0_BRESP),.m_axi_gmem0_BID(m_axi_gmem0_BID),.m_axi_gmem0_BUSER(m_axi_gmem0_BUSER),
  .hyst_flags(hyst_flags),.hyst_flags_ap_vld(hyst_flags_ap_vld),
  .s_axi_control_AWVALID(s_axi_control_AWVALID),.s_axi_control_AWREADY(s_axi_control_AWREADY),.s_axi_control_AWADDR(s_axi_control_AWADDR),.s_axi_control_WVALID(s_axi_control_WVALID),.s_axi_control_WREADY(s_axi_control_WREADY),.s_axi_control_WDATA(s_axi_control_WDATA),.s_axi_control_WSTRB(s_axi_control_WSTRB),.s_axi_control_ARVALID(s_axi_control_ARVALID),.s_axi_control_ARREADY(s_axi_control_ARREADY),.s_axi_control_ARADDR(s_axi_control_ARADDR),.s_axi_control_RVALID(s_axi_control_RVALID),.s_axi_control_RREADY(s_axi_control_RREADY),.s_axi_control_RDATA(s_axi_control_RDATA),.s_axi_control_RRESP(s_axi_control_RRESP),.s_axi_control_BVALID(s_axi_control_BVALID),.s_axi_control_BREADY(s_axi_control_BREADY),.s_axi_control_BRESP(s_axi_control_BRESP),.interrupt(checker_interrupt));

 checker_hysteresis #(.DWELL_FRAMES(DWELL_FRAMES)) u_hyst(
  .clk(aclk),.rst_n(aresetn),.flags_vld(hyst_flags_ap_vld),.above_enter(hyst_flags[0]),.below_exit(hyst_flags[1]),
  .pr_busy(pr_busy),.pr_trigger(pr_trigger),.mode(stable_mode));
 dfxc_trigger_adapter u_adapter(.clk(aclk),.rst_n(aresetn),.mode(stable_mode),.pr_trigger(pr_trigger),.pr_busy(pr_busy),.vs_hw_triggers(vs_hw_triggers),.vs_rm_shutdown_req(vs_rm_shutdown_req),.vs_rm_shutdown_ack(vs_rm_shutdown_ack),.vs_rm_decouple(vs_rm_decouple),.rm_ap_idle(rm_ap_idle));
 pr_latency_probe u_probe(.clk(aclk),.rst_n(aresetn),.trigger_seen(|vs_hw_triggers),.vs_rm_shutdown_req(vs_rm_shutdown_req),.vs_rm_shutdown_ack(vs_rm_shutdown_ack),.vs_rm_decouple(vs_rm_decouple),.drain_cycles(drain_cycles),.swap_cycles(swap_cycles),.meas_valid(meas_valid));

 always @(posedge aclk or negedge aresetn) begin
  if(!aresetn) begin frame_cnt<=0;swap_cnt<=0;end
  else begin
   if(hyst_flags_ap_vld) frame_cnt<=frame_cnt+1'b1;
   if(meas_valid) swap_cnt<=swap_cnt+1'b1;
  end
 end

 // Read-only status slave: one outstanding read, writes are consumed and
 // answered SLVERR so a stray write cannot wedge an AXI interconnect.
 reg status_aw_seen,status_w_seen;
 assign s_axi_status_AWREADY=!status_aw_seen&&!s_axi_status_BVALID;
 assign s_axi_status_WREADY=!status_w_seen&&!s_axi_status_BVALID;
 assign s_axi_status_BRESP=2'b10;
 assign s_axi_status_ARREADY=!s_axi_status_RVALID;
 assign s_axi_status_RRESP=2'b00;
 always @(posedge aclk or negedge aresetn) begin
  if(!aresetn) begin status_aw_seen<=0;status_w_seen<=0;s_axi_status_BVALID<=0;s_axi_status_RVALID<=0;s_axi_status_RDATA<=0;end
  else begin
   if(s_axi_status_AWVALID&&s_axi_status_AWREADY) status_aw_seen<=1;
   if(s_axi_status_WVALID&&s_axi_status_WREADY) status_w_seen<=1;
   if(status_aw_seen&&status_w_seen&&!s_axi_status_BVALID) begin status_aw_seen<=0;status_w_seen<=0;s_axi_status_BVALID<=1;end
   else if(s_axi_status_BVALID&&s_axi_status_BREADY) s_axi_status_BVALID<=0;
   if(s_axi_status_ARVALID&&s_axi_status_ARREADY) begin
    case(s_axi_status_ARADDR[5:0])
     6'h00:s_axi_status_RDATA<={31'd0,stable_mode};
     6'h04:s_axi_status_RDATA<=frame_cnt;
     6'h08:s_axi_status_RDATA<=swap_cnt;
     6'h0c:s_axi_status_RDATA<=drain_cycles;
     6'h10:s_axi_status_RDATA<=swap_cycles;
     default:s_axi_status_RDATA<=0;
    endcase
    s_axi_status_RVALID<=1;
   end else if(s_axi_status_RVALID&&s_axi_status_RREADY) s_axi_status_RVALID<=0;
  end
 end
endmodule
