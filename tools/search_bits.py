#!/usr/bin/env python3
"""Backtrack 11x11 I-bits: 2 ones per bitcnt column and 2 per ROM nibble class.

Dual-rail pairs need exactly two I=1 pulses on each decode. Bitcnt one-hots
are columns; ROM one-hots are the nibble regions dumped from Icarus.
"""

from __future__ import annotations

import argparse
import itertools
from collections import defaultdict
from pathlib import Path

# hex(n_293, n_294, n_295, n_296); 293 is MSB. Row = round, col = bit time.
# Dumped with n_721 tied 0 (inst667.C undriven in GDS). Tying ~n_498 zeroes row 8
# and splits several regions; n_721=0 yields 11 4-connected polyominoes.
ROM = [
    [0x5, 0x5, 0x5, 0x5, 0x5, 0x2, 0x2, 0xC, 0x4, 0x4, 0xA],
    [0x5, 0x5, 0x0, 0x5, 0x5, 0x2, 0xC, 0xC, 0x4, 0x4, 0xA],
    [0x5, 0x5, 0x0, 0x2, 0x2, 0x2, 0x2, 0xC, 0xC, 0x4, 0xA],
    [0x5, 0x5, 0x0, 0x2, 0x8, 0x8, 0x8, 0xA, 0xC, 0xC, 0xA],
    [0x0, 0x5, 0x0, 0x2, 0x8, 0xA, 0xA, 0xA, 0xA, 0xA, 0xA],
    [0x0, 0x0, 0x0, 0x2, 0x8, 0x8, 0x8, 0xA, 0x1, 0x1, 0x1],
    [0x2, 0x2, 0x2, 0x2, 0x2, 0x2, 0x8, 0xA, 0x1, 0x3, 0x3],
    [0x2, 0xD, 0xD, 0xD, 0x8, 0x8, 0x8, 0xA, 0x1, 0x3, 0x3],
    [0x2, 0xD, 0xD, 0x9, 0xA, 0xA, 0xA, 0xA, 0x1, 0x3, 0x3],
    [0x2, 0x2, 0xD, 0x9, 0x9, 0xA, 0xA, 0xA, 0x1, 0x1, 0x1],
    [0x2, 0xD, 0xD, 0x9, 0xA, 0xA, 0xA, 0xA, 0xA, 0xA, 0xA],
]


def rom_classes() -> dict[int, list[tuple[int, int]]]:
    cells: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for r, row in enumerate(ROM):
        for c, v in enumerate(row):
            cells[v].append((r, c))
    return cells


# Optional inst390 tap names to ignore (extract-short experiments).
DROP_LAGS: set[str] = set()


def n425(c: int, hist: list[int]) -> int:
    d1, d10, d11, d12 = hist[1], hist[10], hist[11], hist[12]
    if "d1" in DROP_LAGS:
        d1 = 0
    if "d10" in DROP_LAGS:
        d10 = 0
    if "d11" in DROP_LAGS:
        d11 = 0
    if "d12" in DROP_LAGS:
        d12 = 0
    if c == 0:
        return d10 | d11
    if c == 10:
        return d11 | d1 | d12
    return d10 | d11 | d1 | d12


def prefix_390_ok(bits: list[int]) -> bool:
    """inst390 stays 0 on a (possibly short) prefix of I."""
    hist = [0] * 13
    for t, bit in enumerate(bits):
        if bit and n425(t % 11, hist):
            return False
        hist = [0, bit, *hist[1:12]]
    return True


def sr390_clean(bits: list[int]) -> bool:
    return prefix_390_ok(bits)


def _two_cells_390_ok(a: tuple[int, int], b: tuple[int, int]) -> bool:
    if a[0] * 11 + a[1] > b[0] * 11 + b[1]:
        a, b = b, a
    bits = [0] * 121
    bits[a[0] * 11 + a[1]] = 1
    bits[b[0] * 11 + b[1]] = 1
    return prefix_390_ok(bits)


def iter_cell_solutions(max_yield: int = 8, max_nodes: int = 2_000_000):
    """Fill I in time order: 2 per row/col/ROM class, inst390 clean. O(121) memory.

    Tiny ROM classes (size <= 6) are assigned a 390-legal pair first so the
    small polyominoes do not starve the later columns.
    """
    if max_yield <= 0:
        raise ValueError("max_yield must be a positive cap")
    cells = rom_classes()
    values = sorted(cells)
    small = [v for v in values if len(cells[v]) <= 6]
    pair_opts: list[list[tuple[tuple[int, int], tuple[int, int]]]] = []
    for v in small:
        opts = []
        for a, b in itertools.combinations(cells[v], 2):
            if _two_cells_390_ok(a, b):
                opts.append((a, b))
        print(f"# class {v:#x} size={len(cells[v])} legal_pairs={len(opts)}", flush=True)
        if not opts:
            print("# cell-search unsat: a small ROM class has no 390-legal pair", flush=True)
            return
        pair_opts.append(opts)

    produced = 0
    n_seed = 0
    remaining = max_yield
    for combo in itertools.product(*[list(reversed(opts)) for opts in pair_opts]):
        must_one: set[tuple[int, int]] = set()
        must_zero: set[tuple[int, int]] = set()
        seed_bits = [0] * 121
        ok = True
        for v, (a, b) in zip(small, combo):
            for cell in cells[v]:
                must_zero.add(cell)
            for cell in (a, b):
                if cell in must_one:
                    ok = False
                    break
                must_one.add(cell)
                must_zero.discard(cell)
                seed_bits[cell[0] * 11 + cell[1]] = 1
            if not ok:
                break
        if not ok or not prefix_390_ok(seed_bits):
            continue
        n_seed += 1
        for grid in iter_solutions(
            max_yield=remaining,
            max_nodes=max_nodes,
            check_390=True,
            check_rom=True,
            must_one=must_one,
            must_zero=must_zero,
            quiet=True,
        ):
            produced += 1
            remaining -= 1
            yield grid
            if remaining <= 0:
                print(f"# cell-search seeds={n_seed} produced={produced}", flush=True)
                return
    print(f"# cell-search seeds={n_seed} produced={produced}", flush=True)


def sr390_clean(bits: list[int]) -> bool:
    return prefix_390_ok(bits)


def iter_solutions(
    max_yield: int = 8,
    max_nodes: int = 200_000,
    check_390: bool = True,
    check_rom: bool = True,
    must_one: set[tuple[int, int]] | None = None,
    must_zero: set[tuple[int, int]] | None = None,
    quiet: bool = False,
):
    """Round-wise 2-ones search. Optional inst390 prefix check and ROM-class sums."""
    if max_yield <= 0:
        raise ValueError("max_yield must be a positive cap")
    cells = rom_classes()
    later_rom = [dict.fromkeys(cells, 0) for _ in range(12)]
    later_col = [[0] * 11 for _ in range(12)]
    for r in range(10, -1, -1):
        later_rom[r] = later_rom[r + 1].copy()
        later_col[r] = later_col[r + 1][:]
        for c, v in enumerate(ROM[r]):
            later_rom[r][v] += 1
            later_col[r][c] += 1
    grid = [[0] * 11 for _ in range(11)]
    col_count = [0] * 11
    rom_count = dict.fromkeys(cells, 0)
    produced = 0
    nodes = 0
    stop = False
    max_r = 0
    one_row = [set() for _ in range(11)]
    zero_row = [set() for _ in range(11)]
    for r, c in must_one or ():
        one_row[r].add(c)
    for r, c in must_zero or ():
        zero_row[r].add(c)

    def feasible(r: int) -> bool:
        for c in range(11):
            if col_count[c] + later_col[r][c] < 2:
                return False
        if check_rom:
            for v, n in rom_count.items():
                if n > 2 or n + later_rom[r][v] < 2:
                    return False
        return True

    def bt(r: int):
        nonlocal produced, nodes, stop, max_r
        if stop:
            return
        nodes += 1
        if r > max_r:
            max_r = r
        if nodes > max_nodes:
            stop = True
            return
        if not feasible(r):
            return
        if r == 11:
            produced += 1
            yield [row[:] for row in grid]
            if produced >= max_yield:
                stop = True
            return
        pairs = sorted(itertools.combinations(range(11), 2), key=lambda p: p[0] - p[1])
        for c1, c2 in pairs:
            if stop:
                return
            chosen = {c1, c2}
            if not one_row[r] <= chosen:
                continue
            if chosen & zero_row[r]:
                continue
            if col_count[c1] >= 2 or col_count[c2] >= 2:
                continue
            v1, v2 = ROM[r][c1], ROM[r][c2]
            if check_rom:
                if v1 == v2:
                    if rom_count[v1] + 2 > 2:
                        continue
                elif rom_count[v1] + 1 > 2 or rom_count[v2] + 1 > 2:
                    continue
            grid[r][c1] = grid[r][c2] = 1
            col_count[c1] += 1
            col_count[c2] += 1
            rom_count[v1] += 1
            rom_count[v2] += 1
            bits = [grid[i][j] for i in range(r + 1) for j in range(11)]
            if (not check_390) or prefix_390_ok(bits):
                yield from bt(r + 1)
            rom_count[v1] -= 1
            rom_count[v2] -= 1
            col_count[c1] -= 1
            col_count[c2] -= 1
            grid[r][c1] = grid[r][c2] = 0

    yield from bt(0)
    print(f"# search nodes={nodes} max_round={max_r} produced={produced}", flush=True)


def solve(limit: int = 8) -> list[list[list[int]]]:
    return list(iter_solutions(max_yield=limit))


def matrix_to_bits(grid: list[list[int]]) -> list[int]:
    return [grid[r][c] for r in range(11) for c in range(11)]


def bits_to_ascii_11lsb(bits: list[int]) -> str:
    chars = []
    for i in range(0, 121, 11):
        v = 0
        for b, bit in enumerate(bits[i : i + 11]):
            v |= bit << b
        chars.append(chr(v & 0x7F) if 32 <= (v & 0x7F) < 127 else ".")
    return "".join(chars)


def write_stim(bits: list[int], path: Path) -> None:
    lines = ["# rst_n enable I"]
    for _ in range(3):
        lines.append("0 0 0")
    for b in bits:
        lines.append(f"1 1 {b}")
    for _ in range(24):
        lines.append("1 0 0")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=8, help="max solutions to keep (hard cap, default 8)")
    ap.add_argument("--out-dir", type=Path, default=Path("build/search_bits"))
    ap.add_argument("--write-stim", action="store_true")
    ap.add_argument("--no-sr390", action="store_true", help="skip inst390 SR tap filter")
    ap.add_argument("--no-rom", action="store_true", help="do not require ROM-class sums of 2")
    ap.add_argument(
        "--drop-lag",
        action="append",
        choices=("d1", "d10", "d11", "d12"),
        default=[],
        help="ignore an inst390 SR tap (repeatable; extract-short test)",
    )
    ap.add_argument("--max-nodes", type=int, default=5_000_000)
    args = ap.parse_args()
    DROP_LAGS.clear()
    DROP_LAGS.update(args.drop_lag)
    if DROP_LAGS:
        print(f"drop_lags {sorted(DROP_LAGS)}", flush=True)
    if args.limit <= 0:
        print("error: --limit must be >= 1 (refusing unbounded enumeration)", flush=True)
        return 2

    cells = rom_classes()
    print("rom_classes", {hex(v): len(ps) for v, ps in sorted(cells.items())}, flush=True)
    check_390 = not args.no_sr390
    check_rom = not args.no_rom
    if check_390 and check_rom:
        gen = iter_cell_solutions(max_yield=args.limit, max_nodes=args.max_nodes)
    else:
        gen = iter_solutions(
            max_yield=args.limit,
            max_nodes=min(args.max_nodes, 2_000_000),
            check_390=check_390,
            check_rom=check_rom,
        )
    n = 0
    for g in gen:
        bits = matrix_to_bits(g)
        print(f"sol{n} ascii11lsb={bits_to_ascii_11lsb(bits)!r} ones={sum(bits)}", flush=True)
        for row in g:
            print(" ", "".join(str(b) for b in row), flush=True)
        if args.write_stim:
            write_stim(bits, args.out_dir / f"sol{n:04d}.txt")
        n += 1
    print(f"emitted={n} (capped at {args.limit})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
