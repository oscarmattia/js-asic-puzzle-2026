#!/usr/bin/env python3
"""Classify success-cone flop D functions from the extracted netlist.

Prints instance names, polarities, and a short D expression in terms of I,
enable-qualified n_11, one-hot decodes, and other flop Qs. No GDS.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

INST_RE = re.compile(r"(sky130_fd_sc_hd__\w+)\s+(\w+)\s+\((.*?)\);", re.S)
PIN_RE = re.compile(r"\.(\w+)\(([^)]+)\)")
OUT_PINS = frozenset({"X", "Y", "Q", "Q_N", "QN", "Z", "ZN", "HI", "LO"})

# SET polarities from analyze_puzzle / probe TB (1 = must be 1 at success).
SET_WANT = {
    "inst106": 0, "inst107": 1, "inst108": 0, "inst117": 1, "inst118": 0,
    "inst121": 0, "inst122": 0, "inst123": 0, "inst124": 0, "inst126": 0,
    "inst141": 1, "inst142": 1, "inst143": 1, "inst153": 1, "inst178": 1,
    "inst179": 0, "inst180": 1, "inst188": 1, "inst189": 0, "inst190": 1,
    "inst194": 0, "inst197": 1, "inst198": 1, "inst209": 1, "inst215": 0,
    "inst226": 0, "inst231": 0, "inst232": 0, "inst233": 1, "inst26": 0,
    "inst350": 1, "inst390": 0, "inst419": 0, "inst447": 0, "inst449": 1,
    "inst451": 1, "inst453": 0, "inst454": 0, "inst459": 0, "inst460": 1,
    "inst461": 0, "inst595": 1, "inst596": 1, "inst597": 1, "inst600": 1,
    "inst601": 1, "inst602": 0, "inst603": 0, "inst614": 0, "inst622": 0,
    "inst625": 0, "inst634": 1, "inst635": 1, "inst647": 1, "inst651": 0,
    "inst661": 0,
}

# Known one-hot / protocol nets from history.
DECODE_NETS = {
    "n_172": "C=1100",
    "n_174": "C=0101",
    "n_186": "C=1101",
    "n_209": "C=1010",
    "n_211": "C=0011",
    "n_245": "C=1001",
    "n_268": "C=0000",
    "n_384": "C=0011 lock",
    "n_703": "ROM=0000",
    "n_696": "ROM=0101",
    "n_289": "ROM=0011",
    "n_687": "ROM=1100",
    "n_669": "ROM=1001",
    "n_284": "ROM=1010",
    "n_12": "ROM=1101",
    "n_11": "shift_en",
}


def parse_netlist(path: Path):
    text = path.read_text(encoding="utf-8")
    insts: dict[str, tuple[str, dict[str, str]]] = {}
    drivers: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    flop_q: dict[str, str] = {}
    q_flop: dict[str, str] = {}
    for master, inst, pins in INST_RE.findall(text):
        short = master.split("__", 1)[1]
        pinsd = {p: n.strip() for p, n in PIN_RE.findall(pins)}
        insts[inst] = (short, pinsd)
        for pin, net in pinsd.items():
            if pin in OUT_PINS:
                drivers[net].append((inst, short, pin))
        if short.startswith(("dfrtp", "dfstp", "dfxtp")) and "Q" in pinsd:
            flop_q[inst] = pinsd["Q"]
            q_flop[pinsd["Q"]] = inst
    return insts, drivers, flop_q, q_flop


def cell_expr(short: str, pins: dict[str, str]) -> str:
    p = pins
    def n(name: str) -> str:
        return p.get(name, f"?{name}")

    fam = short.rsplit("_", 1)[0]
    match fam:
        case "inv":
            return f"~{n('A')}"
        case "and2":
            return f"({n('A')} & {n('B')})"
        case "and2b":
            return f"(~{n('A_N')} & {n('B')})"
        case "and3":
            return f"({n('A')} & {n('B')} & {n('C')})"
        case "and4":
            return f"({n('A')} & {n('B')} & {n('C')} & {n('D')})"
        case "and4bb":
            return f"(~{n('A_N')} & ~{n('B_N')} & {n('C')} & {n('D')})"
        case "nand2":
            return f"~({n('A')} & {n('B')})"
        case "nand2b":
            return f"({n('A_N')} | ~{n('B')})"
        case "nand3":
            return f"~({n('A')} & {n('B')} & {n('C')})"
        case "nand4":
            return f"~({n('A')} & {n('B')} & {n('C')} & {n('D')})"
        case "nor2":
            return f"~({n('A')} | {n('B')})"
        case "nor3":
            return f"~({n('A')} | {n('B')} | {n('C')})"
        case "nor4":
            return f"~({n('A')} | {n('B')} | {n('C')} | {n('D')})"
        case "or2":
            return f"({n('A')} | {n('B')})"
        case "or3":
            return f"({n('A')} | {n('B')} | {n('C')})"
        case "xor2":
            return f"({n('A')} ^ {n('B')})"
        case "xnor2":
            return f"~({n('A')} ^ {n('B')})"
        case "a21o":
            return f"(({n('A1')} & {n('A2')}) | {n('B1')})"
        case "a21oi":
            return f"~(({n('A1')} & {n('A2')}) | {n('B1')})"
        case "a21bo":
            return f"(({n('A1')} & {n('A2')}) | ~{n('B1_N')})"
        case "a21boi":
            return f"~(({n('A1')} & {n('A2')}) | ~{n('B1_N')})"
        case "a31o":
            return f"(({n('A1')} & {n('A2')} & {n('A3')}) | {n('B1')})"
        case "a32o":
            return f"(({n('A1')} & {n('A2')} & {n('A3')}) | ({n('B1')} & {n('B2')}))"
        case "a221o":
            return f"(({n('A1')} & {n('A2')}) | ({n('B1')} & {n('B2')}) | {n('C1')})"
        case "a311o":
            return f"(({n('A1')} & {n('A2')} & {n('A3')}) | {n('B1')} | {n('C1')})"
        case "a31oi":
            return f"~(({n('A1')} & {n('A2')} & {n('A3')}) | {n('B1')})"
        case "o21a":
            return f"(({n('A1')} | {n('A2')}) & {n('B1')})"
        case "o21ai":
            return f"~(({n('A1')} | {n('A2')}) & {n('B1')})"
        case "o21ba":
            return f"(({n('A1')} | {n('A2')}) & ~{n('B1_N')})"
        case "o21bai":
            return f"~(({n('A1')} | {n('A2')}) & ~{n('B1_N')})"
        case "o31ai":
            return f"~(({n('A1')} | {n('A2')} | {n('A3')}) & {n('B1')})"
        case "mux2":
            return f"({n('S')} ? {n('A1')} : {n('A0')})"
        case _:
            args = ", ".join(f"{k}={v}" for k, v in p.items() if k not in OUT_PINS)
            return f"{fam}({args})"


def label_net(net: str, q_flop: dict[str, str]) -> str:
    if net in {"I", "clk", "rst_n", "enable", "success"}:
        return net
    if net in DECODE_NETS:
        return f"{net}/{DECODE_NETS[net]}"
    if net in q_flop:
        inst = q_flop[net]
        w = SET_WANT.get(inst)
        tag = f"w{w}" if w is not None else "?"
        return f"Q:{inst}({tag})"
    return net


def expand(net: str, insts, drivers, q_flop, depth: int, seen: set[str]) -> str:
    if net in {"I", "clk", "rst_n", "enable", "success"}:
        return net
    if net in DECODE_NETS:
        return f"{net}[{DECODE_NETS[net]}]"
    if net in q_flop:
        return label_net(net, q_flop)
    if depth <= 0 or net in seen:
        return label_net(net, q_flop)
    drvs = drivers.get(net, [])
    if not drvs:
        return f"{net}?"
    inst, short, _pin = drvs[0]
    if short.startswith(("dfrtp", "dfstp", "dfxtp")):
        return label_net(net, q_flop)
    seen = seen | {net}
    pins = insts[inst][1]
    expr = cell_expr(short, pins)
    subs: list[tuple[str, str]] = []
    for pin, n in pins.items():
        if pin in OUT_PINS:
            continue
        subs.append((n, expand(n, insts, drivers, q_flop, depth - 1, seen)))
    for n, sub in sorted(subs, key=lambda kv: len(kv[0]), reverse=True):
        expr = expr.replace(n, sub)
    return expr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--netlist", type=Path, default=Path("build/puzzle_extracted.v"))
    ap.add_argument("--depth", type=int, default=3)
    args = ap.parse_args()

    insts, drivers, flop_q, q_flop = parse_netlist(args.netlist)
    print(f"flops={len(flop_q)} set_cone={len(SET_WANT)}")
    print()
    for inst in sorted(SET_WANT, key=lambda s: int(s.replace("inst", "") or 0)):
        short, pins = insts[inst]
        dnet = pins["D"]
        want = SET_WANT[inst]
        expr = expand(dnet, insts, drivers, q_flop, args.depth, set())
        i_touch = "I" in expr
        print(f"{inst} want={want} D={dnet} I={int(i_touch)}")
        print(f"  {expr}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
