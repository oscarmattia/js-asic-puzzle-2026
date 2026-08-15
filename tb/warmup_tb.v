`timescale 1ns/1ps

module warmup_tb;
    reg  clk;
    reg  rst_n;
    reg  A;
    reg  B;
    reg  en;
    wire S;

    adder_demo dut (
        .clk(clk),
        .rst_n(rst_n),
        .A(A),
        .B(B),
        .S(S),
        .en(en)
    );

    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    task automatic reset_dut;
        begin
            rst_n = 0;
            en    = 0;
            A     = 0;
            B     = 0;
            repeat (3) @(posedge clk);
            rst_n = 1;
        end
    endtask

  // MSB-first: serial_in becomes LSB; first bit shifted ends up as bit 7.
    task automatic shift_in;
        input [7:0] a_val;
        input [7:0] b_val;
        integer i;
        begin
            en = 1;
            for (i = 7; i >= 0; i = i - 1) begin
                A = a_val[i];
                B = b_val[i];
                @(posedge clk);
            end
            en = 0;
        end
    endtask

    task automatic check_s;
        input        expected;
        input string name;
        begin
            @(posedge clk);
            @(posedge clk);
            if (S !== expected) begin
                $display("FAIL: %s (expected S=%0d, got S=%0d)", name, expected, S);
                $fatal(1);
            end else
                $display("PASS: %s", name);
        end
    endtask

    task automatic run_test;
        input [7:0]  a_val;
        input [7:0]  b_val;
        input        expected_s;
        input string name;
        begin
            reset_dut();
            shift_in(a_val, b_val);
            check_s(expected_s, name);
        end
    endtask

    initial begin
        $dumpfile("build/warmup.vcd");
        $dumpvars(0, warmup_tb);

        rst_n = 0;
        en    = 0;
        A     = 0;
        B     = 0;

        @(posedge clk);
        @(posedge clk);
        @(posedge clk);
        rst_n = 1;

        run_test(8'd255, 8'd241, 1, "A=255 B=241 sum=496");
        run_test(8'd0,   8'd0,   0, "A=0 B=0 sum=0");
        run_test(8'd200, 8'd50,  0, "A=200 B=50 sum=250");
        run_test(8'd255, 8'd240, 0, "A=255 B=240 sum=495");
        run_test(8'd248, 8'd248, 1, "A=248 B=248 sum=496");

        $display("ALL TESTS PASSED");
        $finish;
    end
endmodule
