#!/usr/bin/env python3
"""Extract a gate-level Verilog netlist from a placed sky130 GDS layout."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from extract_lib import (  # noqa: E402
    assign_net_names,
    attach_terminals,
    build_clusters,
    bus_from_names,
    collect_instances,
    collect_power_boxes,
    collect_top_labels,
    collect_top_routing,
    emit_verilog,
    inject_pin_boxes,
    mark_power_roots,
    prune_pin_rects,
    parse_def_ports,
    resolve_top_cell,
    union_same_pin_terminals,
    coalesce_reset_nets,
    UnionFind,
)

try:
    import klayout.db as db
except ImportError:  # pragma: no cover - allows --help without klayout
    db = None  # type: ignore[assignment]


DEFAULT_PORTS = ["A", "B", "S", "clk", "en", "rst_n"]

# Round-counter Q nets as extracted for puzzle.gds (inst467/468/471/475).
# Kept as documentation; undriven combo is tied 0, not inferred as ~Q.


_OUT_PINS = {"X", "Y", "Q", "Q_N", "QN", "Z", "ZN", "HI", "LO"}
_SEQ_PREFIXES = ("dfrtp", "dfstp", "dfxtp")


def _parse_insts(verilog: str) -> list[tuple[str, str, dict[str, str]]]:
    inst_re = re.compile(r"(sky130_fd_sc_hd__\w+)\s+(\w+)\s+\((.*?)\);", re.S)
    pin_re = re.compile(r"\.(\w+)\(([^)]+)\)")
    out: list[tuple[str, str, dict[str, str]]] = []
    for master, inst, pins in inst_re.findall(verilog):
        pinsd = {p: n.strip() for p, n in pin_re.findall(pins)}
        out.append((master, inst, pinsd))
    return out


def _undriven_nets(verilog: str, insts: list[tuple[str, str, dict[str, str]]]) -> set[str]:
    port_re = re.compile(r"^\s*(input|output|inout)\s+(?:\[.*?\]\s+)?(\w+)", re.M)
    ports = {m.group(2) for m in port_re.finditer(verilog)}
    drivers: set[str] = set()
    loads: set[str] = set()
    for _master, _inst, pins in insts:
        for pin, net in pins.items():
            if pin in _OUT_PINS:
                drivers.add(net)
            else:
                loads.add(net)
    return {
        n for n in loads
        if n not in drivers and n not in ports and n.startswith("n_")
        and f"assign {n} " not in verilog
    }


def repair_undriven_mux_hold(verilog: str) -> str:
    """Wire undriven a221o hold pins to the flop Q that cell feeds.

    OG muxes are (enable & shift_in) | (idle & Q). Via-clipping dropped
    inst294.B1 / inst290.A2 off inst252.Q; unclipped LEF joins that Q, and
    Icarus then prints ASCII on the success bank.
    """
    insts = _parse_insts(verilog)
    undriven = _undriven_nets(verilog, insts)
    d_to_q: dict[str, str] = {}
    for master, _inst, pins in insts:
        short = master.split("__", 1)[1]
        if short.startswith(_SEQ_PREFIXES) and "D" in pins and "Q" in pins:
            d_to_q[pins["D"]] = pins["Q"]

    assigns: list[tuple[str, str]] = []
    seen: set[str] = set()
    for master, _inst, pins in insts:
        short = master.split("__", 1)[1]
        if not short.startswith("a221o"):
            continue
        q = d_to_q.get(pins.get("X", ""))
        if not q:
            continue
        b1, b2 = pins.get("B1", ""), pins.get("B2", "")
        if b1 in undriven and b2 not in undriven and b1 != q and b1 not in seen:
            assigns.append((b1, q))
            seen.add(b1)
        elif b2 in undriven and b1 not in undriven and b2 != q and b2 not in seen:
            assigns.append((b2, q))
            seen.add(b2)
    if not assigns:
        return verilog
    lines = "".join(f"  assign {src} = {dst};\n" for src, dst in assigns)
    return verilog.replace("endmodule", lines + "endmodule", 1)


def tie_undriven_to_zero(verilog: str) -> str:
    """Tie leftover undriven combo nets to 0.

    inst667.C (n_721) has no GDS driver. Inferring C=~inst468.Q made a round-8
    one-hot that zeroed a whole ROM row and split Star Battle regions. Icarus
    treats undriven as X; 0 matches a missing tap.
    """
    insts = _parse_insts(verilog)
    undriven = sorted(_undriven_nets(verilog, insts))
    if not undriven:
        return verilog
    ties = "".join(f"  assign {n} = 1'b0;\n" for n in undriven)
    return verilog.replace("endmodule", ties + "endmodule", 1)


def extract(
    gds_path: Path,
    top_name: str | None,
    lef_dir: Path | None,
    def_path: Path | None,
    ports: list[str],
) -> tuple[str, dict[str, int]]:
    if db is None:
        raise RuntimeError("klayout is not installed; run via `uv run python`")

    layout = db.Layout()
    layout.read(str(gds_path))
    top = resolve_top_cell(layout, top_name)

    routing = collect_top_routing(layout, top)
    instances, terminals = collect_instances(layout, top, lef_dir)
    terminals = prune_pin_rects(terminals, routing)
    inject_pin_boxes(routing, terminals)

    uf = UnionFind()
    clusters = build_clusters(routing, uf)
    power_roots = mark_power_roots(clusters, collect_power_boxes(layout, top, lef_dir), uf)
    terminal_root = attach_terminals(clusters, terminals, uf, power_roots)
    union_same_pin_terminals(terminals, terminal_root, uf)

    port_candidates = []
    if def_path is not None:
        port_candidates.extend(parse_def_ports(def_path))
    port_candidates.extend(collect_top_labels(layout, top))
    seen_ports: set[str] = set()
    unique_ports: list = []
    for p in port_candidates:
        if p.name in seen_ports:
            continue
        seen_ports.add(p.name)
        unique_ports.append(p)

    net_names = assign_net_names(
        uf, terminal_root, terminals, clusters, unique_ports, power_roots
    )
    if "rst_n" in ports:
        coalesce_reset_nets(terminals, net_names, "rst_n")
    buses = bus_from_names([p.name for p in unique_ports])
    emit_ports = list(ports)
    for bus in buses:
        if bus not in emit_ports:
            emit_ports.append(bus)
    verilog, dangling_pins = emit_verilog(
        top.name, instances, terminals, net_names, emit_ports, buses
    )
    verilog = repair_undriven_mux_hold(verilog)
    verilog = tie_undriven_to_zero(verilog)

    resolved = sorted({n for n in net_names.values() if n in emit_ports or n.split("[")[0] in buses})
    logic_masters = {i.master for i in instances}
    stats = {
        "instances": len(instances),
        "logic_cell_types": len(logic_masters),
        "terminals": len(terminals),
        "nets": len({net_names[t.tid] for t in terminals}),
        "dangling_pins": dangling_pins,
        "routing_shapes": sum(routing[m].count() for m in routing),
        "labels": sorted({p.name for p in unique_ports}),
        "resolved_ports": resolved,
        "power_clusters": len(power_roots),
        "buses": {k: v for k, v in buses.items()},
    }
    return verilog, stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract gate-level Verilog from a sky130_fd_sc_hd GDS layout.",
    )
    parser.add_argument("--gds", required=True, help="Input GDS file")
    parser.add_argument("--out", required=True, help="Output Verilog path")
    parser.add_argument("--top", help="Top cell name (default: layout top cell)")
    parser.add_argument("--lef-dir", type=Path, help="Directory of sky130 LEF files for pin shapes")
    parser.add_argument("--def", dest="def_file", type=Path, help="Optional DEF for port locations")
    parser.add_argument(
        "--ports",
        default=",".join(DEFAULT_PORTS),
        help="Comma-separated top-level port names (default: A,B,S,clk,en,rst_n)",
    )
    args = parser.parse_args()

    gds_path = Path(args.gds)
    if not gds_path.is_file():
        print(f"error: GDS not found: {gds_path}", file=sys.stderr)
        return 1

    ports = [p.strip() for p in args.ports.split(",") if p.strip()]
    try:
        verilog, stats = extract(gds_path, args.top, args.lef_dir, args.def_file, ports)
    except Exception as exc:  # noqa: BLE001 - CLI tool reports extraction failures
        print(f"error: extraction failed: {exc}", file=sys.stderr)
        return 1

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(verilog, encoding="utf-8")

    print(f"wrote {out_path}")
    print(
        "stats: "
        f"instances={stats['instances']} "
        f"cell_types={stats['logic_cell_types']} "
        f"nets={stats['nets']} "
        f"dangling_pins={stats['dangling_pins']} "
        f"routing_shapes={stats['routing_shapes']} "
        f"power_clusters={stats['power_clusters']}"
    )
    print(f"labels: {', '.join(stats['labels']) or '(none)'}")
    print(f"resolved ports: {', '.join(stats['resolved_ports']) or '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
