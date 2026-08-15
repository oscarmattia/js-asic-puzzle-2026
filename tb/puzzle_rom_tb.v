`timescale 1ns/1ps

// Dump the 4-bit ROM nibble and n_620/n_721 each enable cycle. I=0.
module puzzle_rom_tb;
    reg clk, rst_n, enable, I;
    wire success;
    wire [7:0] O;

    puzzle dut (
        .clk(clk), .rst_n(rst_n), .enable(enable), .I(I),
        .success(success), .O(O)
    );

    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    integer cyc, fd;
    initial begin
        rst_n = 0; enable = 0; I = 0;
        fd = $fopen("build/rom_dump.txt", "w");
        $fwrite(fd, "# cyc R467 R468 R471 R475 C355 C352 C354 C363 ROM n_620 n_721\n");
        repeat (3) @(posedge clk);
        #1; rst_n = 1; enable = 1;
        for (cyc = 0; cyc < 121; cyc = cyc + 1) begin
            #1;
            $fwrite(fd, "%0d %b%b%b%b %b%b%b%b %b%b%b%b %b %b\n",
                cyc,
                dut.inst467.Q, dut.inst468.Q, dut.inst471.Q, dut.inst475.Q,
                dut.inst355.Q, dut.inst352.Q, dut.inst354.Q, dut.inst363.Q,
                dut.n_293, dut.n_294, dut.n_295, dut.n_296,
                dut.n_620, dut.n_721);
            @(posedge clk);
        end
        $fclose(fd);
        $display("rom dump wrote 121 cycles");
        $finish;
    end
endmodule
