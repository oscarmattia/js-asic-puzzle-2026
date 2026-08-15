#!/usr/bin/env python3
"""Report multi-driven and undriven nets in a gate-level Verilog netlist."""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

OUT_PINS = frozenset({"X", "Y", "Q", "Q_N", "QN", "Z", "ZN", "HI", "LO"})
PORT_RE = re.compile(r"^\s*(input|output|inout)\s+(?:\[.*?\]\s+)?(\w+)", re.M)
INST_RE = re.compile(r"(sky130_fd_sc_hd__\w+)\s+(\w+)\s+\((.*?)\);", re.S)
PIN_RE = re.compile(r"\.(\w+)\(([^)]+)\)")


def diagnose(text: str) -> int:
    ports = {m.group(2) for m in PORT_RE.finditer(text)}
    drivers: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    loads: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for master, inst, pins in INST_RE.findall(text):
        for pin, net in PIN_RE.findall(pins):
            net = net.strip()
            if pin in OUT_PINS:
                drivers[net].append((inst, master, pin))
            else:
                loads[net].append((inst, master, pin))

    multi = {n: ds for n, ds in drivers.items() if len(ds) > 1}
    undriven = {
        n: ls
        for n, ls in loads.items()
        if n not in drivers and n not in ports
    }

    print(f"ports: {sorted(ports)}")
    print(f"driven nets: {len(drivers)}  loaded nets: {len(loads)}")
    print(f"multi-driven: {len(multi)}  undriven loads: {len(undriven)}")
    if multi:
        print("\n=== multi-driven nets ===")
        for net, ds in sorted(multi.items()):
            print(f"  {net}: {ds}")
    if undriven:
        print("\n=== undriven nets with loads ===")
        for net, ls in sorted(undriven.items()):
            print(f"  {net}: {ls}")
    return 1 if multi or undriven else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("netlist")
    args = parser.parse_args()
    path = Path(args.netlist)
    if not path.is_file():
        print(f"error: not found: {path}", file=sys.stderr)
        return 2
    return diagnose(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
