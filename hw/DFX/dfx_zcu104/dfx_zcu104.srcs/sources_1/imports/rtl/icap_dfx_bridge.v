// Static-shell bridge between DFX Controller and the Zynq UltraScale+ ICAPE3.
// Signal names follow the Controller; notably icap_o drives ICAPE3.I.
module icap_dfx_bridge (
    input  wire        icap_clk,
    input  wire [31:0] icap_o,
    input  wire        icap_csib,
    input  wire        icap_rdwrb,
    output wire [31:0] icap_i,
    output wire        icap_avail,
    output wire        icap_prdone,
    output wire        icap_prerror
);
    ICAPE3 icape3_inst (
        .CLK(icap_clk),
        .I(icap_o),
        .CSIB(icap_csib),
        .RDWRB(icap_rdwrb),
        .O(icap_i),
        .AVAIL(icap_avail),
        .PRDONE(icap_prdone),
        .PRERROR(icap_prerror)
    );
endmodule
