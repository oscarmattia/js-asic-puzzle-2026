#!/usr/bin/env python3
"""Compare sky130 cell counts between a Verilog netlist and a GDS inventory."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gds_inventory import SKY130_PREFIX, classify_master, collect_instances

import klayout.db as db

CELL_RE = re.compile(rf"\b({re.escape(SKY130_PREFIX)}\w+)\b")


def is_logic_master(name: str) -> bool:
    category = classify_master(name)
    return category is not None and category != "fill"


def count_verilog_cells(netlist_path: Path) -> Counter[str]:
    text = netlist_path.read_text(encoding="utf-8")
    return Counter(CELL_RE.findall(text))


def count_gds_cells(gds_path: Path) -> Counter[str]:
    layout = db.Layout()
    layout.read(str(gds_path))
    instances = collect_instances(layout, layout.top_cell())
    return Counter(inst["master"] for inst in instances)


def print_table(verilog_counts: Counter[str], gds_counts: Counter[str]) -> None:
    all_names = sorted(set(verilog_counts) | set(gds_counts))
    print(f"{'master':<45} {'verilog':>8} {'gds':>8} {'match':>6}")
    print("-" * 72)
    for name in all_names:
        v_count = verilog_counts.get(name, 0)
        g_count = gds_counts.get(name, 0)
        match = "ok" if v_count == g_count else "DIFF"
        print(f"{name:<45} {v_count:>8} {g_count:>8} {match:>6}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare netlist and GDS cell counts.")
    parser.add_argument("--ref", required=True, help="Reference Verilog netlist")
    parser.add_argument("--gds", required=True, help="GDS file")
    args = parser.parse_args()

    ref_path = Path(args.ref)
    gds_path = Path(args.gds)
    if not ref_path.is_file():
        print(f"error: netlist not found: {ref_path}", file=sys.stderr)
        return 1
    if not gds_path.is_file():
        print(f"error: GDS not found: {gds_path}", file=sys.stderr)
        return 1

    verilog_counts = count_verilog_cells(ref_path)
    gds_counts = count_gds_cells(gds_path)
    print_table(verilog_counts, gds_counts)

    mismatches = []
    logic_names = {
        name
        for name in set(verilog_counts) | set(gds_counts)
        if is_logic_master(name)
    }
    for name in sorted(logic_names):
        if verilog_counts.get(name, 0) != gds_counts.get(name, 0):
            mismatches.append(name)

    if mismatches:
        print(f"\nlogic cell mismatches: {len(mismatches)}", file=sys.stderr)
        return 1

    print("\nall logic cell counts match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
