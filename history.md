# ASIC puzzle 2026 — working history

Jane Street rule still in force: AI for **scripts and warmup**, not for dumping `puzzle.gds` geometry into chat, and not for the final submission writeup. Scripts print counts, net names, sim PASS/FAIL. Acceptance for a real answer is **`success===1`**, then read ASCII from `O[7:0]`. `TRY AGAIN` is a failure banner, not the secret.

Icarus (`FUNCTIONAL` + `UNIT_DELAY`, per-cell `cells/<family>/<cell>.v`) is the source of truth. Do not trust Python `success=1` without an Icarus confirm.

## Warmup → extract

Warmup is the same OpenROAD / sky130-hd flow with names still attached (`warmup/00_source.v` … `04_final.gds`). Motifs that transferred:

- Serial datapath is `mux2` + `dfrtp`, `RESET_B` = `rst_n`.
- Clock is a **clkbuf** tree.
- Comparators show up as `and3` / `and4bb` cones.
- Fill (`decap`, `tap`) and power followpins are noise.

Extractor (`tools/extract_lib.py`, `tools/extract_netlist.py`):

- KLayout `db.Region(RecursiveShapeIterator)` ignores `max_depth` — walk hierarchy by hand.
- Skip sky130 internals; recurse into OpenROAD `VIA_*`. Skip power vias and power-mesh paths.
- Clip LEF pin PORTs to via landings (full straps short neighbors: mux2 `S`, clkbuf `X`, conb `HI`/`LO`).
- `coalesce_reset_nets` ties RESET_B/SET_B-only nets to `rst_n`.

Warmup extracted sim: **5/5**. Puzzle extract: 738 inst / 67 types, all ports resolved, 0 multi-driven. Three leftover undriven combo nets: `n_362`, `n_591`, `n_721`.

Example VCD replay (`tools/sim_puzzle.sh` + `tb/puzzle_tb.v`) is a **negative** test: `success=0`, `O='TRY AGAIN'`. PASS. A candidate TB must invert that (`tb/puzzle_candidate_tb.v`: PASS iff `success===1`).

## Protocol (from `example_inputs.vcd` + counters)

Ports: `clk`, `rst_n`, `enable`, serial `I`, `success`, `O[7:0]`. Toggle `rst_n` before every attempt.

- Enable-qualified shift/compare enable is `n_11 = ~lock & enable` (`and2b inst360`).
- **Bit counter** `inst355/352/354/363` (Q `n_182,n_184,n_183,n_185`), period **11**.
- **Round counter** `inst467/468/471/475`, increments once per 11-cycle round, also period 11.
- **Lock** `inst350` SET when bitcnt=`0011` (and4bb) **and** round=`1001` (`inst467=1,468=0,471=0,475=1`), while `n_11`. Fires at **cycle 120**, independent of `I`.
- `success` SET is a one-cycle window: `lock=1` and sticky `inst26` still 0. Sticky thereafter via `a32o`.

So one attempt is exactly **121 bits**. Bits after lock are ignored until reset. Do not brute `2^121`.

Example packing: 11-bit **LSB-first ASCII** (8 data bits + 3 zeros). The two failed attempts decode to `"The nights"` and `"ky awaits  "` — **“The night sky awaits”** split across two reset-separated windows. That is the packing demo, not the passphrase (both halves fail).

VCD `$date` is the 2016 leap second; `$version` is “Leave no stone unturned…”. Warmup secret **496** is a perfect number.

## Placement + success cone

`shots/puzzle_placement.png` vs labeled `layout.png`:

- Success cone = center spine + bottom-right xor/mux cluster.
- Faded top-right = **output generator**. Ignore it until `success=1`.
- Cone is unate in 56 `dfrtp` Qs (26 must be 1, 30 must be 0) plus lock/window flags.

Blocks in the cone:

- 12-bit `mux2`+`dfrtp` SR on `S=n_11`, `I` → `inst370` … `inst389`.
- Bit counter + round counter as above.
- Dual-rail I-latches gated by **bitcnt one-hots** (`and4bb` of `n_182..n_185`) and by **4-bit ROM one-hots**.
- Small serial ALU (`inst447..461`) also in the SET tree.
- `dfxtp` (4) and `dfstp` (4) sit outside the success combo cone (OG control).

`I` has ~45 combo loads. It is checked every enable cycle, not only through the 12-bit SR.

## Output generator banners (still `success=0`)

| Input | `O` (Icarus) |
|---|---|
| all-0 / empty free-bits | `EMPTY SKY` |
| all-1 | `BIG BANG` |
| typical ASCII / other | `TRY AGAIN` |

Multiple canned strings. `TRY AGAIN` is the default miss. None of these had `success=1`.

## Xor / ALU cluster (what was actually recovered)

The bottom-right xor/xnor cone is a **combinational function of (bitcnt, round) only** — not of `I`. Icarus dump of `n_293,n_294,n_295,n_296` **with `n_721=0`** (inst667.C has no GDS driver):

Bitcnt `C=(355,352,354,363)` sequence:

`0000,1000,0001,1001,0100,1100,0101,1101,0010,1010,0011`

Round `R=(467,468,471,475)` sequence:

`0000,0010,0001,0011,0100,0110,0101,0111,1000,1010,1001`

ROM nibble `hex(n_293,n_294,n_295,n_296)` as 11×11 (row = round, col = bit time):

```
      0 1 2 3 4 5 6 7 8 9 A
r0    5 5 5 5 5 2 2 C 4 4 A
r1    5 5 0 5 5 2 C C 4 4 A
r2    5 5 0 2 2 2 2 C C 4 A
r3    5 5 0 2 8 8 8 A C C A
r4    0 5 0 2 8 A A A A A A
r5    0 0 0 2 8 8 8 A 1 1 1
r6    2 2 2 2 2 2 8 A 1 3 3
r7    2 D D D 8 8 8 A 1 3 3
r8    2 D D 9 A A A A 1 3 3
r9    2 2 D 9 9 A A A 1 1 1
r10   2 D D 9 A A A A A A A
```

Every nibble class is a single 4-connected polyomino. Tying `n_721=~n_498` instead made round 8 all-zero, split several classes, and left `0x3` as a 2×2 and `0x9` as an L-tromino — unsat for two non-touching stars. GDS: `inst667.C` has a via clip and **no other pin** on that net. `inst383` A1/A2/B1/B2/C1 match the extracted 390 taps (B1 is a dedicated `conb` HI). The extractor now wires undriven `a221o` hold pins to the flop Q they feed (`n_362 = n_96`) and ties leftover undriven combo nets (`n_721`, `n_591`) to 0.

One-hot decodes of that nibble (`and4bb`/`nor4`) enable the same dual-rail I-latches used on bitcnt:

| net | ROM `293..296` | used with I |
|---|---|---|
| `n_703` | `0000` | yes |
| `n_696` | `0101` | yes |
| `n_289` | `0011` | yes |
| `n_687` | `1100` | yes |
| `n_669` | `1001` | yes |
| `n_284` | `1010` | yes |
| `n_12`  | `1101` | yes |

This is an **index / hash of (bit time, round)**, not a stored 121-bit plaintext. Treating the nibble (or its bits, or “I=0 iff ROM in that set”) as `I` does **not** raise `success`.

`tb/puzzle_probe_tb.v` dumps the ROM each cycle and greedily picks `I` from SET-flop D vs desired polarities. Greedy always chooses `I=0` (I=1 immediately harms want-0 latches). Want-1 latches need lookahead / two-round AND (companion flop must already be 1).

## Candidate search already tried (all `success=0`)

- 11-char 11-lsb (and some 8-bit / 11-msb): `Jane Street`, `ASIC PUZZLE`, `The nights`, leap-second / warmup / night-sky phrases, etc. (`tools/encode_stim.py`, `tools/sim_candidate.sh`).
- 11×11 bitmaps: identity, checker, all-1, anti-identity.
- ROM-derived bitstreams (each nibble bit, eq/ne each value, “zero-set” map).
- 4 “free” bitcnt columns under a sticky-OR-I=1 reading of the C one-hots, 16 constant nibbles.
- First four column-only 2-ones matrices (`tools/search_bits.py --limit 4`): all 22 dual-rail pairs plus low ALU match want; `inst390` / `inst419` / high ALU do not.

## Dual-rail pairs (Icarus-confirmed)

Each success-cone pair is a two-pulse transfer: first `I=1` on that decode sets the want-0 flop; a later `I=1` clears it and sets the want-1 companion. A third pulse sticks at `11`. Bitcnt columns and ROM nibble classes each need exactly two ones.

`inst419` / `inst416` / `inst420`: per-round 2-bit ones counter, sampled at col 10. Forces **exactly two ones per round**. Together with columns that is an 11×11 2-factor (22 ones). ALU `447..461` then matches popcount 22 (`453..447=0110`, `460=1`).

`inst390` (Icarus-checked): `D = Q | (I & n_11 & n_425)` with
`n_425 = (n_421 & Q395) | Q391 | (n_400 & (Q370|Q389))`.
Taps are SR delays 1,10,11,12 — king-adjacency on the 11×11. Banner `TWO"NOT TOUCH` is this constraint.

With `n_721=0` ROM classes, `tools/search_bits.py --limit 8` finds one 2-factor (stim `build/search_bits_tie0/sol0000.txt`). Icarus on `build/puzzle_extracted_n721.v` (**no** `inst383` patch): **`success=1`** at cycle 125. All 56 SET bits match want (`inst390=0`, `inst419=0`; `inst26=1` at end-of-run is expected).

`O` after enable drop is 15 bytes then 0. With leftover `n_362` tied 0 those bytes were garbage. `n_362` is the OG mux **hold** pin: sibling `a221o` cells take `(enable & shift_in) | (idle & Q)`, and via-clipping dropped `inst294.B1` / `inst290.A2` off `inst252.Q` (`n_96`). Unclipped LEF joins that Q. Extractor repair: `assign n_362 = n_96`. Icarus then prints ASCII:

`(* TWO STARS *)`

(`28 2a 20 54 57 4f 20 53 54 41 52 53 20 2a 29`). Fail path is unchanged (`TRY AGAIN` on the example VCD). `n_591` stays tied 0: even unclipped it has no driver, and it only feeds the fail-bank decode.

Earlier `n_721=~n_498` searches were unsat / needed a fake `inst383` patch; that patch is retired. `sim_candidate.sh` stamps the compiled netlist path so `NETLIST=` cannot reuse a stale `vvp`.

Do **not** enumerate the full 2-ones set (blew RAM). Cap `--limit`, stream. `+dumpo` prints `O` bytes.

INTERNAL_3 / INTERNAL_7 on layer 200/0 are a 1-row 3/7 barcode below the die, not the 11×11 key.

## Commands

```bash
uv run python tools/extract_netlist.py --gds puzzle.gds --lef-dir third_party/sky130_fd_sc_hd \
  --ports clk,rst_n,enable,I,success --out build/puzzle_extracted.v
tools/sim_warmup.sh extracted
tools/sim_puzzle.sh                          # example: success=0, TRY AGAIN
uv run python tools/analyze_puzzle.py --flop-depth 8
uv run python tools/encode_stim.py --text 'Jane Street' --enc 11lsb --out build/candidate_stim.txt
uv run python tools/search_bits.py --limit 8 --write-stim --out-dir build/search_bits_tie0
NETLIST=build/puzzle_extracted_n721.v tools/sim_candidate.sh build/search_bits_tie0/sol0000.txt
vvp build/puzzle_candidate.vvp +stim=build/search_bits_tie0/sol0000.txt +dumpo
```

Python: **`uv run` only**. `third_party/` is gitignored. Do not commit unless asked.
