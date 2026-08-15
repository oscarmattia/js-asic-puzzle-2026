`timescale 1ns/1ps

// Probe: dump 4-bit xor-ROM (n_293..n_296) and greedily pick I from SET-flop Ds.
module puzzle_probe_tb;
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

    integer fd, cyc, pick, s0, s1, h0, h1;
    integer prev_en, collecting, nchars, success_cycle;
    reg [8*32-1:0] message;
    reg [120:0] bits;

    // SET polarities (1 = want 1). Order matches score_q.
    function integer want;
        input integer idx;
        begin
            case (idx)
                0,2,4,5,6,7,8,9: want = 0;          // 106 108 118 121 122 123 124 126
                1,3: want = 1;                      // 107 117
                10,11,12,13,14: want = 1;           // 141 142 143 153 178
                15: want = 0;                       // 179
                16,17: want = 1;                    // 180 188
                18: want = 0;                       // 189
                19: want = 1;                       // 190
                20: want = 0;                       // 194
                21,22,23: want = 1;                 // 197 198 209
                24,25,26,27: want = 0;              // 215 226 231 232
                28: want = 1;                       // 233
                29: want = 0;                       // 26
                30: want = 1;                       // 350 lock
                31,32,33: want = 0;                 // 390 419 447
                34,35: want = 1;                    // 449 451
                36,37,38: want = 0;                 // 453 454 459
                39: want = 1;                       // 460
                40: want = 0;                       // 461
                41,42,43,44,45: want = 1;           // 595 596 597 600 601
                46,47,48,49,50: want = 0;           // 602 603 614 622 625
                51,52,53: want = 1;                 // 634 635 647
                54,55: want = 0;                    // 651 661
                default: want = 0;
            endcase
        end
    endfunction

    function integer qbit;
        input integer idx;
        begin
            case (idx)
                0: qbit = dut.inst106.Q;  1: qbit = dut.inst107.Q;
                2: qbit = dut.inst108.Q;  3: qbit = dut.inst117.Q;
                4: qbit = dut.inst118.Q;  5: qbit = dut.inst121.Q;
                6: qbit = dut.inst122.Q;  7: qbit = dut.inst123.Q;
                8: qbit = dut.inst124.Q;  9: qbit = dut.inst126.Q;
                10: qbit = dut.inst141.Q; 11: qbit = dut.inst142.Q;
                12: qbit = dut.inst143.Q; 13: qbit = dut.inst153.Q;
                14: qbit = dut.inst178.Q; 15: qbit = dut.inst179.Q;
                16: qbit = dut.inst180.Q; 17: qbit = dut.inst188.Q;
                18: qbit = dut.inst189.Q; 19: qbit = dut.inst190.Q;
                20: qbit = dut.inst194.Q; 21: qbit = dut.inst197.Q;
                22: qbit = dut.inst198.Q; 23: qbit = dut.inst209.Q;
                24: qbit = dut.inst215.Q; 25: qbit = dut.inst226.Q;
                26: qbit = dut.inst231.Q; 27: qbit = dut.inst232.Q;
                28: qbit = dut.inst233.Q; 29: qbit = dut.inst26.Q;
                30: qbit = dut.inst350.Q; 31: qbit = dut.inst390.Q;
                32: qbit = dut.inst419.Q; 33: qbit = dut.inst447.Q;
                34: qbit = dut.inst449.Q; 35: qbit = dut.inst451.Q;
                36: qbit = dut.inst453.Q; 37: qbit = dut.inst454.Q;
                38: qbit = dut.inst459.Q; 39: qbit = dut.inst460.Q;
                40: qbit = dut.inst461.Q; 41: qbit = dut.inst595.Q;
                42: qbit = dut.inst596.Q; 43: qbit = dut.inst597.Q;
                44: qbit = dut.inst600.Q; 45: qbit = dut.inst601.Q;
                46: qbit = dut.inst602.Q; 47: qbit = dut.inst603.Q;
                48: qbit = dut.inst614.Q; 49: qbit = dut.inst622.Q;
                50: qbit = dut.inst625.Q; 51: qbit = dut.inst634.Q;
                52: qbit = dut.inst635.Q; 53: qbit = dut.inst647.Q;
                54: qbit = dut.inst651.Q; 55: qbit = dut.inst661.Q;
                default: qbit = 0;
            endcase
        end
    endfunction

    function integer dbit;
        input integer idx;
        begin
            case (idx)
                0: dbit = dut.inst106.D;  1: dbit = dut.inst107.D;
                2: dbit = dut.inst108.D;  3: dbit = dut.inst117.D;
                4: dbit = dut.inst118.D;  5: dbit = dut.inst121.D;
                6: dbit = dut.inst122.D;  7: dbit = dut.inst123.D;
                8: dbit = dut.inst124.D;  9: dbit = dut.inst126.D;
                10: dbit = dut.inst141.D; 11: dbit = dut.inst142.D;
                12: dbit = dut.inst143.D; 13: dbit = dut.inst153.D;
                14: dbit = dut.inst178.D; 15: dbit = dut.inst179.D;
                16: dbit = dut.inst180.D; 17: dbit = dut.inst188.D;
                18: dbit = dut.inst189.D; 19: dbit = dut.inst190.D;
                20: dbit = dut.inst194.D; 21: dbit = dut.inst197.D;
                22: dbit = dut.inst198.D; 23: dbit = dut.inst209.D;
                24: dbit = dut.inst215.D; 25: dbit = dut.inst226.D;
                26: dbit = dut.inst231.D; 27: dbit = dut.inst232.D;
                28: dbit = dut.inst233.D; 29: dbit = dut.inst26.D;
                30: dbit = dut.inst350.D; 31: dbit = dut.inst390.D;
                32: dbit = dut.inst419.D; 33: dbit = dut.inst447.D;
                34: dbit = dut.inst449.D; 35: dbit = dut.inst451.D;
                36: dbit = dut.inst453.D; 37: dbit = dut.inst454.D;
                38: dbit = dut.inst459.D; 39: dbit = dut.inst460.D;
                40: dbit = dut.inst461.D; 41: dbit = dut.inst595.D;
                42: dbit = dut.inst596.D; 43: dbit = dut.inst597.D;
                44: dbit = dut.inst600.D; 45: dbit = dut.inst601.D;
                46: dbit = dut.inst602.D; 47: dbit = dut.inst603.D;
                48: dbit = dut.inst614.D; 49: dbit = dut.inst622.D;
                50: dbit = dut.inst625.D; 51: dbit = dut.inst634.D;
                52: dbit = dut.inst635.D; 53: dbit = dut.inst647.D;
                54: dbit = dut.inst651.D; 55: dbit = dut.inst661.D;
                default: dbit = 0;
            endcase
        end
    endfunction

    function integer score_d;
        integer i, s;
        begin
            s = 0;
            for (i = 0; i < 56; i = i + 1) begin
                if (i != 29 && i != 30) begin
                    if (dbit(i) === want(i))
                        s = s + 1;
                end
            end
            score_d = s;
        end
    endfunction

    function integer harm_d;
        integer i, h;
        begin
            h = 0;
            for (i = 0; i < 56; i = i + 1) begin
                if (i != 29 && i != 30) begin
                    if (qbit(i) === want(i) && dbit(i) !== want(i))
                        h = h + 1;
                end
            end
            harm_d = h;
        end
    endfunction

    initial begin
        rst_n = 0; enable = 0; I = 0;
        prev_en = 0; collecting = 0; nchars = 0; success_cycle = 0;
        message = {32{" "}};
        bits = 0;
        fd = $fopen("build/probe_rom.txt", "w");
        $fwrite(fd, "# cyc I C355 C352 C354 C363 R467 R468 R471 R475 ROM293 294 295 296 n11 lock\n");

        repeat (3) @(posedge clk);
        #1;
        rst_n = 1;
        enable = 1;

        for (cyc = 0; cyc < 121; cyc = cyc + 1) begin
            I = 0;
            #1;
            s0 = score_d();
            h0 = harm_d();
            I = 1;
            #1;
            s1 = score_d();
            h1 = harm_d();
            if ((h1 < h0) || (h1 == h0 && s1 > s0))
                pick = 1;
            else
                pick = 0;
            I = pick[0];
            #1;
            $fwrite(fd, "%0d %0d %b %b %b %b %b %b %b %b %b %b %b %b %b %b  h0=%0d h1=%0d s0=%0d s1=%0d pick=%0d\n",
                cyc, pick,
                dut.inst355.Q, dut.inst352.Q, dut.inst354.Q, dut.inst363.Q,
                dut.inst467.Q, dut.inst468.Q, dut.inst471.Q, dut.inst475.Q,
                dut.n_293, dut.n_294, dut.n_295, dut.n_296,
                dut.n_11, dut.inst350.Q,
                h0, h1, s0, s1, pick);
            bits[120-cyc] = pick[0];
            @(posedge clk);
            #1;
            if (success === 1'b1 && success_cycle == 0)
                success_cycle = cyc;
        end

        enable = 0; I = 0;
        prev_en = 1;
        repeat (24) begin
            @(posedge clk);
            #1;
            if (prev_en == 1) begin
                collecting = 1; nchars = 0; message = {32{" "}};
            end else if (collecting && nchars < 32) begin
                message = {message[8*31-1:0], O};
                nchars = nchars + 1;
            end
            prev_en = 0;
            if (success === 1'b1 && success_cycle == 0)
                success_cycle = 200;
        end
        $fclose(fd);
        $display("probe success=%0d success_cycle=%0d", success, success_cycle);
        $display("O='%s'", message);
        $display("bits=");
        for (cyc = 0; cyc < 121; cyc = cyc + 1)
            $write("%0d", bits[120-cyc]);
        $display("");
        $finish;
    end
endmodule
