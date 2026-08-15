`timescale 1ns/1ps

module puzzle_tb;
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

    integer fd, nread, cycles, fails;
    integer rst_i, en_i, i_bit;
    integer prev_en, collecting, nchars;
    reg [8*9-1:0] message;

    initial begin
        $dumpfile("build/puzzle.vcd");
        $dumpvars(0, puzzle_tb);

        rst_n      = 0;
        enable     = 0;
        I          = 0;
        cycles     = 0;
        fails      = 0;
        prev_en    = 0;
        collecting = 0;
        nchars     = 0;
        message    = "         ";

        fd = $fopen("build/puzzle_stim.txt", "r");
        if (fd == 0) begin
            $display("FAIL: cannot open build/puzzle_stim.txt");
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

            if (rst_n === 1'b1 && success === 1'bx) begin
                $display("FAIL: success is X at cycle %0d", cycles);
                fails = fails + 1;
            end
            if (success === 1'b1) begin
                $display("FAIL: success went high at cycle %0d (expected 0)", cycles);
                fails = fails + 1;
            end

            if (prev_en == 1 && enable === 1'b0) begin
                collecting = 1;
                nchars     = 0;
                message    = "         ";
            end else if (collecting && nchars < 9) begin
                message = {message[8*8-1:0], O};
                nchars  = nchars + 1;
            end
            prev_en = enable;
        end
        $fclose(fd);

        $display("cycles=%0d success=%0d", cycles, success);
        $display("O after enable drop: %s", message);

        if (success !== 1'b0) begin
            $display("FAIL: final success=%0d (expected 0)", success);
            fails = fails + 1;
        end
        if (message !== "TRY AGAIN") begin
            $display("FAIL: expected ASCII 'TRY AGAIN', got '%s'", message);
            fails = fails + 1;
        end

        if (fails != 0) begin
            $display("FAIL: puzzle replay (%0d errors)", fails);
            $fatal(1);
        end
        $display("PASS: success=0 and O='TRY AGAIN'");
        $finish;
    end
endmodule
