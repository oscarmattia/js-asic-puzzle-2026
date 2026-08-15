# Plan

Current phase: **done for the puzzle itself.** Icarus `success=1` and `O` is ASCII. See [history.md](history.md).

**RAM:** 24 GB. `tools/search_bits.py` streams, `--limit` default 8, never unbounded. One `vvp` at a time.

## Done

- Warmup, extract, protocol, dual-rail pairs, `inst419` row-sum, ALU popcount 22.
- `inst390` is king-adjacency (SR delays 1,10,11,12). GDS confirms `inst383` A/B/C taps.
- **`n_721` is undriven.** Tying `~n_498` zeroed ROM row 8 and split regions. Tying **0** yields 11 4-connected polyominoes.
- Full `inst390` + 2 per row/col/ROM class: one 2-factor. Icarus **`success=1`**.
- **`n_362 = inst252.Q` (`n_96`)** — OG mux hold that via-clipping dropped. Then `O` = `(* TWO STARS *)`.
- `n_591` stays tied 0 (no driver even unclipped; fail-bank only).

## Later (human-only)

- Easter eggs, submission writeup. Do not brute 2^121.
