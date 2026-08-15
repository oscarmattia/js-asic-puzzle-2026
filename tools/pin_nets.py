#!/usr/bin/env python3
"""Print pin-net fanout for a few puzzle instances. Names only, no geometry."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_lib import (  # noqa: E402
    UnionFind,
    assign_net_names,
    attach_terminals,
    build_clusters,
    collect_instances,
    collect_power_boxes,
    collect_top_labels,
    collect_top_routing,
    inject_pin_boxes,
    mark_power_roots,
    prune_pin_rects,
    resolve_top_cell,
    union_same_pin_terminals,
    coalesce_reset_nets,
)
import klayout.db as db

WATCH = {
    "inst667": {"C", "A_N", "B_N", "D", "X"},
    "inst383": {"A1", "A2", "B1", "B2", "C1", "X"},
    "inst431": {"HI", "LO"},
    "inst369": {"A1", "A2", "B1", "B2", "X"},
    "inst395": {"Q", "D"},
    "inst391": {"Q", "D"},
    "inst290": {"A1", "A2", "B1", "X"},
    "inst294": {"A1", "A2", "B1", "B2", "C1", "X"},
    "inst252": {"Q", "D"},
    "inst525": {"A1", "A2", "A3", "B1", "Y"},
}


def main() -> int:
    layout = db.Layout()
    layout.read("puzzle.gds")
    top = resolve_top_cell(layout, None)
    lef = Path("third_party/sky130_fd_sc_hd")
    routing = collect_top_routing(layout, top)
    instances, terminals = collect_instances(layout, top, lef)
    # map inst name -> master
    masters = {i.name: i.master for i in instances}

    def report(label: str, terms, net_names, terminal_root, uf) -> None:
        by_pin: dict[tuple[str, str], list] = defaultdict(list)
        for t in terms:
            by_pin[(t.inst_name, t.pin_name)].append(t)
        pins_by_net: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for t in terms:
            pins_by_net[net_names[t.tid]].append((t.inst_name, t.pin_name))
        print(f"=== {label} ===")
        for inst, pins in WATCH.items():
            print(f"  {inst} {masters.get(inst, '?')}")
            for pin in pins:
                ts = by_pin.get((inst, pin), [])
                if not ts:
                    print(f"    .{pin} MISSING")
                    continue
                nets = sorted({net_names[t.tid] for t in ts})
                metals = sorted({t.metal for t in ts})
                nbox = len(ts)
                for net in nets:
                    others = sorted(set(pins_by_net[net]) - {(inst, pin)})
                    print(
                        f"    .{pin} net={net} metal={','.join(metals)} "
                        f"clips={nbox} others={len(others)}"
                    )
                    if len(others) <= 12:
                        print(f"      {others}")
                    else:
                        print(f"      {others[:12]} ...")

    terminals_clipped = prune_pin_rects(terminals, routing)
    inject_pin_boxes(routing, terminals_clipped)
    uf = UnionFind()
    clusters = build_clusters(routing, uf)
    power_roots = mark_power_roots(clusters, collect_power_boxes(layout, top, lef), uf)
    terminal_root = attach_terminals(clusters, terminals_clipped, uf, power_roots)
    union_same_pin_terminals(terminals_clipped, terminal_root, uf)
    ports = collect_top_labels(layout, top)
    net_names = assign_net_names(uf, terminal_root, terminals_clipped, clusters, ports, power_roots)
    coalesce_reset_nets(terminals_clipped, net_names, "rst_n")
    report("clipped (extractor)", terminals_clipped, net_names, terminal_root, uf)

    # Unclipped: keep full LEF rects, see if inst667.C joins a real net.
    routing2 = collect_top_routing(layout, top)
    instances2, terminals2 = collect_instances(layout, top, lef)
    inject_pin_boxes(routing2, terminals2)
    uf2 = UnionFind()
    clusters2 = build_clusters(routing2, uf2)
    power2 = mark_power_roots(clusters2, collect_power_boxes(layout, top, lef), uf2)
    tr2 = attach_terminals(clusters2, terminals2, uf2, power2)
    union_same_pin_terminals(terminals2, tr2, uf2)
    nn2 = assign_net_names(uf2, tr2, terminals2, clusters2, ports, power2)
    coalesce_reset_nets(terminals2, nn2, "rst_n")
    report("unclipped LEF", terminals2, nn2, tr2, uf2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
