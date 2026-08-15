#!/usr/bin/env python3
"""Placement plot + success-cone summary for the extracted puzzle netlist.

Prints counts and net names only. Coordinates go to a PNG, not stdout.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

import klayout.db as db
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_lib import FILL_KEYWORDS, SKY130_PREFIX, is_fill_cell  # noqa: E402

INST_RE = re.compile(r"(sky130_fd_sc_hd__\w+)\s+(\w+)\s+\((.*?)\);", re.S)
PIN_RE = re.compile(r"\.(\w+)\(([^)]+)\)")
OUT_PINS = frozenset({"X", "Y", "Q", "Q_N", "QN", "Z", "ZN", "HI", "LO"})
SEQ_PREFIXES = ("dfrtp", "dfstp", "dfxtp")


def parse_netlist(path: Path) -> tuple[dict[str, tuple[str, dict[str, str]]], dict[str, list[tuple[str, str, str]]]]:
    text = path.read_text(encoding="utf-8")
    insts: dict[str, tuple[str, dict[str, str]]] = {}
    drivers: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for master, inst, pins in INST_RE.findall(text):
        short = master.split("__", 1)[1]
        pinsd = {p: n.strip() for p, n in PIN_RE.findall(pins)}
        insts[inst] = (short, pinsd)
        for pin, net in pinsd.items():
            if pin in OUT_PINS:
                drivers[net].append((inst, short, pin))
    return insts, drivers


def gds_logic_origins(gds: Path) -> list[tuple[str, float, float]]:
    layout = db.Layout()
    layout.read(str(gds))
    top = layout.top_cell()
    dbu = layout.dbu
    out: list[tuple[str, float, float]] = []

    def walk(cell: db.Cell, trans: db.ICplxTrans) -> None:
        for inst in cell.each_inst():
            master = inst.cell
            tr = trans * inst.cplx_trans
            if master.name.startswith(SKY130_PREFIX):
                if is_fill_cell(master.name):
                    continue
                disp = tr.disp
                out.append((master.name, disp.x * dbu, disp.y * dbu))
            else:
                walk(master, tr)

    walk(top, db.ICplxTrans())
    return out


def short_family(short: str) -> str:
    if short.startswith(SEQ_PREFIXES):
        return "flop"
    if short.startswith("mux2"):
        return "mux"
    if "xor" in short or "xnor" in short:
        return "xor"
    if short.startswith("and4bb") or short.startswith("nand4") or short.startswith("and4"):
        return "cmp"
    if short.startswith("clkbuf"):
        return "clk"
    if short.startswith("conb") or short.startswith("diode"):
        return "tie"
    return "combo"


def flop_q(insts: dict[str, tuple[str, dict[str, str]]], inst: str) -> str | None:
    short, pins = insts[inst]
    if not short.startswith(SEQ_PREFIXES):
        return None
    return pins.get("Q")


def success_cone(
    insts: dict[str, tuple[str, dict[str, str]]],
    drivers: dict[str, list[tuple[str, str, str]]],
    max_flop_depth: int = 8,
) -> tuple[set[str], dict[str, int]]:
    """Fanin from success. Stop expanding through flops after max_flop_depth hops."""
    success_drivers = drivers.get("success", [])
    if not success_drivers:
        return set(), {}
    start = success_drivers[0][0]
    seen_insts: set[str] = set()
    flop_depth: dict[str, int] = {}
    q: deque[tuple[str, int]] = deque([(start, 0)])
    while q:
        inst, depth = q.popleft()
        if inst in seen_insts:
            continue
        seen_insts.add(inst)
        short, pins = insts[inst]
        is_flop = short.startswith(SEQ_PREFIXES)
        if is_flop:
            flop_depth[inst] = depth
            if depth >= max_flop_depth:
                continue
            next_depth = depth + 1
            nets = [pins[p] for p in ("D", "S") if p in pins]
        else:
            next_depth = depth
            nets = [n for p, n in pins.items() if p not in OUT_PINS]
        for net in nets:
            if net in {"clk", "rst_n", "enable", "I"} or net.startswith("n_") is False and net in {
                "clk",
                "rst_n",
                "enable",
                "I",
                "success",
            }:
                pass
            for drv_inst, drv_short, _pin in drivers.get(net, []):
                if drv_inst not in seen_insts:
                    q.append((drv_inst, next_depth))
            if net == "I":
                continue
    return seen_insts, flop_depth


def plot_placement(
    named: list[tuple[str, str, float, float, bool]],
    out: Path,
) -> None:
    colors = {
        "flop": "#d62728",
        "mux": "#ff7f0e",
        "xor": "#2ca02c",
        "cmp": "#9467bd",
        "clk": "#8c564b",
        "tie": "#7f7f7f",
        "combo": "#1f77b4",
    }
    fig, ax = plt.subplots(figsize=(10, 8))
    by = defaultdict(list)
    for inst, fam, x, y, in_cone in named:
        by[fam].append((x, y, in_cone))
    for fam, pts in by.items():
        xs_c = [p[0] for p in pts if p[2]]
        ys_c = [p[1] for p in pts if p[2]]
        xs_o = [p[0] for p in pts if not p[2]]
        ys_o = [p[1] for p in pts if not p[2]]
        if xs_o:
            ax.scatter(xs_o, ys_o, s=12, c=colors[fam], alpha=0.25, label=f"{fam} (out)")
        if xs_c:
            ax.scatter(xs_c, ys_c, s=22, c=colors[fam], alpha=0.9, label=f"{fam} (success cone)")
    ax.set_aspect("equal")
    ax.set_xlabel("x (µm)")
    ax.set_ylabel("y (µm)")
    ax.set_title("Puzzle placement (logic cells)")
    ax.legend(loc="upper right", fontsize=8, markerscale=1.4)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=140)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gds", default="puzzle.gds")
    parser.add_argument("--netlist", default="build/puzzle_extracted.v")
    parser.add_argument("--plot", default="shots/puzzle_placement.png")
    parser.add_argument("--flop-depth", type=int, default=6)
    args = parser.parse_args()

    insts, drivers = parse_netlist(Path(args.netlist))
    origins = gds_logic_origins(Path(args.gds))
    logic_insts = [i for i, (s, _) in insts.items()]
    # extract inst order is GDS walk order of non-fill sky130
    ordered = sorted(insts, key=lambda n: int(n.replace("inst", "") or 0))
    if len(ordered) != len(origins):
        print(f"warn: netlist insts={len(ordered)} gds logic={len(origins)}", file=sys.stderr)

    cone, flop_depth = success_cone(insts, drivers, max_flop_depth=args.flop_depth)
    named: list[tuple[str, str, float, float, bool]] = []
    n = min(len(ordered), len(origins))
    xs_cone, xs_all = [], []
    for i in range(n):
        inst = ordered[i]
        master, x, y = origins[i]
        short = insts[inst][0]
        fam = short_family(short)
        in_cone = inst in cone
        named.append((inst, fam, x, y, in_cone))
        xs_all.append(x)
        if in_cone:
            xs_cone.append(x)

    plot_placement(named, Path(args.plot))

    cone_types = Counter(insts[i][0] for i in cone)
    flop_types = Counter(insts[i][0] for i, d in flop_depth.items())
    print(f"logic instances: {len(ordered)}")
    print(f"success cone insts: {len(cone)}  flops in cone: {len(flop_depth)}")
    print(f"cone cell types: {dict(cone_types)}")
    print(f"cone flop types: {dict(flop_types)}")
    print(f"flop depth histogram: {dict(Counter(flop_depth.values()))}")
    if xs_all and xs_cone:
        span = max(xs_all) - min(xs_all)
        core_frac = (sum(xs_cone) / len(xs_cone) - min(xs_all)) / span if span else 0
        print(f"cone mean x as fraction of die width: {core_frac:.2f} (0=left, 1=right)")
        print(f"wrote {args.plot}")

    print("\n=== cone flops (inst, type, depth, Q net, D driver) ===")
    for inst, depth in sorted(flop_depth.items(), key=lambda kv: (kv[1], kv[0])):
        short, pins = insts[inst]
        dnet = pins.get("D", "?")
        ddrv = drivers.get(dnet, [])
        print(f"  d={depth} {inst} {short} Q={pins.get('Q')} D={dnet} drv={[d[1] for d in ddrv]}")

    mux_s = Counter()
    for inst, (short, pins) in insts.items():
        if short.startswith("mux2") and inst in cone:
            mux_s[pins.get("S", "?")] += 1
    print(f"\ncone mux2 S nets: {dict(mux_s)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
