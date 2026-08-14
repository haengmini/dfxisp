`timescale 1ns/1ps
// =============================================================================
// pr_latency_probe.v -- DFX Controller boundary latency instrumentation.
// Updated: 2026-08-06
// Rationale: counts observable PG374 handshakes without entering the control
// decision path. Results latch at decouple release and remain until next swap.
// =============================================================================
module pr_latency_probe (
    input  wire clk,
    input  wire rst_n,
    input  wire trigger_seen,
    input  wire vs_rm_shutdown_req,
    input  wire vs_rm_shutdown_ack,
    input  wire vs_rm_decouple,
    output reg [31:0] drain_cycles,
    output reg [31:0] swap_cycles,
    output reg meas_valid
);
    reg swap_active, drain_active, decouple_seen;
    reg [31:0] swap_count, drain_count;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            swap_active <= 1'b0; drain_active <= 1'b0; decouple_seen <= 1'b0;
            swap_count <= 0; drain_count <= 0;
            drain_cycles <= 0; swap_cycles <= 0; meas_valid <= 1'b0;
        end else begin
            meas_valid <= 1'b0;
            if (!swap_active && trigger_seen) begin
                swap_active <= 1'b1;
                swap_count <= 1;
                decouple_seen <= 1'b0;
            end else if (swap_active) begin
                swap_count <= swap_count + 1'b1;
                if (vs_rm_decouple) decouple_seen <= 1'b1;
                if (decouple_seen && !vs_rm_decouple) begin
                    swap_cycles <= swap_count;
                    swap_active <= 1'b0;
                    meas_valid <= 1'b1;
                end
            end

            if (!drain_active && vs_rm_shutdown_req && !vs_rm_shutdown_ack) begin
                drain_active <= 1'b1;
                drain_count <= 1;
            end else if (drain_active) begin
                if (vs_rm_shutdown_ack) begin
                    drain_cycles <= drain_count;
                    drain_active <= 1'b0;
                end else begin
                    drain_count <= drain_count + 1'b1;
                end
            end else if (vs_rm_shutdown_req && vs_rm_shutdown_ack) begin
                drain_cycles <= 0;
            end
        end
    end
endmodule
