`timescale 1ns/1ps

// Candidate attempt: PASS iff success goes high, then print O.
module puzzle_candidate_tb;
    reg        clk;
    reg        rst_n;
    reg        enable;
    reg        I;
    wire       success;
    wire [7:0] O;

    puzzle dut (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .I(I),
        .success(success),
        .O(O)
    );

    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    integer fd, nread, cycles, success_cycle, dumpfd, do_dump;
    integer rst_i, en_i, i_bit;
    integer prev_en, collecting, nchars;
    reg [8*32-1:0] message;
    reg [1024*8-1:0] stim_path;

    initial begin
        rst_n         = 0;
        enable        = 0;
        I             = 0;
        cycles        = 0;
        success_cycle = 0;
        prev_en       = 0;
        collecting    = 0;
        nchars        = 0;
        message       = {32{" "}};

        stim_path = "build/candidate_stim.txt";
        if ($value$plusargs("stim=%s", stim_path)) begin
        end
        do_dump = $test$plusargs("dumpflops");
        dumpfd  = 0;
        if (do_dump)
            dumpfd = $fopen("build/icarus_flops.txt", "w");
        fd = $fopen(stim_path, "r");
        if (fd == 0) begin
            $display("FAIL: cannot open stim %0s", stim_path);
            $fatal(1);
        end

        nread = $fgetc(fd);
        while (nread != "\n" && nread != -1)
            nread = $fgetc(fd);

        while (!$feof(fd)) begin
            nread = $fscanf(fd, "%d %d %d\n", rst_i, en_i, i_bit);
            if (nread != 3)
                continue;
            rst_n  = rst_i[0];
            enable = en_i[0];
            I      = i_bit[0];
            @(posedge clk);
            cycles = cycles + 1;

            if (prev_en == 1 && enable === 1'b0) begin
                collecting = 1;
                nchars     = 0;
                message    = {32{" "}};
            end else if (collecting && nchars < 32) begin
                if ($test$plusargs("dumpo"))
                    $display("O[%0d]=%03d 0x%02h", nchars, O, O);
                message = {message[8*31-1:0], O};
                nchars  = nchars + 1;
            end
            prev_en = enable;

            #1;
            if (do_dump) begin
                $fwrite(dumpfd, "%0d %b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b%b\n",
                    cycles,
                    dut.inst106.Q, dut.inst107.Q, dut.inst108.Q, dut.inst117.Q, dut.inst118.Q,
                    dut.inst121.Q, dut.inst122.Q, dut.inst123.Q, dut.inst124.Q, dut.inst126.Q,
                    dut.inst141.Q, dut.inst142.Q, dut.inst143.Q, dut.inst153.Q, dut.inst178.Q,
                    dut.inst179.Q, dut.inst180.Q, dut.inst188.Q, dut.inst189.Q, dut.inst190.Q,
                    dut.inst194.Q, dut.inst197.Q, dut.inst198.Q, dut.inst209.Q, dut.inst215.Q,
                    dut.inst226.Q, dut.inst231.Q, dut.inst232.Q, dut.inst233.Q, dut.inst26.Q,
                    dut.inst350.Q, dut.inst390.Q, dut.inst419.Q, dut.inst447.Q, dut.inst449.Q,
                    dut.inst451.Q, dut.inst453.Q, dut.inst454.Q, dut.inst459.Q, dut.inst460.Q,
                    dut.inst461.Q, dut.inst595.Q, dut.inst596.Q, dut.inst597.Q, dut.inst600.Q,
                    dut.inst601.Q, dut.inst602.Q, dut.inst603.Q, dut.inst614.Q, dut.inst622.Q,
                    dut.inst625.Q, dut.inst634.Q, dut.inst635.Q, dut.inst647.Q, dut.inst651.Q,
                    dut.inst661.Q);
            end

            if (rst_n === 1'b1 && success === 1'bx) begin
                $display("FAIL: success is X at cycle %0d", cycles);
                $fatal(1);
            end
            if (success === 1'b1 && success_cycle == 0)
                success_cycle = cycles;
        end
        $fclose(fd);
        if (do_dump)
            $fclose(dumpfd);

        $display("cycles=%0d success=%0d success_cycle=%0d", cycles, success, success_cycle);
        $display("O after enable drop: %s", message);

        if (success !== 1'b1) begin
            $display("FAIL: success stayed 0");
            $fatal(1);
        end
        $display("PASS: success=1 O='%s'", message);
        $finish;
    end
endmodule
