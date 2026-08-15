#!/usr/bin/env python3
"""Inventory sky130 cell instances in a GDS layout."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import klayout.db as db

SKY130_PREFIX = "sky130_fd_sc_hd__"


def trans_to_orient(trans: db.Trans) -> str:
    angle = trans.angle
    mirror = trans.is_mirror()
    if angle == 0 and not mirror:
        return "N"
    if angle == 180 and not mirror:
        return "S"
    if angle == 90 and not mirror:
        return "E"
    if angle == 270 and not mirror:
        return "W"
    if angle == 0 and mirror:
        return "FN"
    if angle == 180 and mirror:
        return "FS"
    if angle == 90 and mirror:
        return "FE"
    if angle == 270 and mirror:
        return "FW"
    return f"R{angle}{'M' if mirror else ''}"


def classify_master(name: str) -> str | None:
    if not name.startswith(SKY130_PREFIX):
        return None
    short = name[len(SKY130_PREFIX) :]
    if short.startswith(("decap", "fill", "tap")):
        return "fill"
    if short.startswith(("dfrt", "dfxt", "dfst", "dly")):
        return "seq"
    if short.startswith(("clkbuf", "clkinv", "clkdly")):
        return "clock"
    return "combo"


def collect_instances(layout: db.Layout, cell: db.Cell) -> list[dict]:
    instances: list[dict] = []
    dbu = layout.dbu

    def walk(parent: db.Cell) -> None:
        for inst in parent.each_inst():
            master = inst.cell
            master_name = master.name
            if master_name.startswith(SKY130_PREFIX):
                trans = inst.trans
                origin_um = (trans.disp.x * dbu, trans.disp.y * dbu)
                inst_name = ""
                try:
                    inst_name = inst.property("NAME") or inst.property("name") or ""
                except Exception:
                    inst_name = ""
                instances.append(
                    {
                        "master": master_name,
                        "origin_um": [origin_um[0], origin_um[1]],
                        "orient": trans_to_orient(trans),
                        "name": inst_name,
                    }
                )
                continue
            walk(master)

    walk(cell)
    return instances


def print_table(unique_counts: Counter[str]) -> None:
    by_class: dict[str, list[tuple[str, int]]] = {
        "fill": [],
        "seq": [],
        "clock": [],
        "combo": [],
    }
    for name, count in sorted(unique_counts.items()):
        category = classify_master(name)
        if category:
            by_class[category].append((name, count))

    print(f"{'master':<45} {'count':>6}  class")
    print("-" * 60)
    for category in ("fill", "seq", "clock", "combo"):
        for name, count in sorted(by_class[category]):
            print(f"{name:<45} {count:>6}  {category}")
    print("-" * 60)
    print(f"{'TOTAL':<45} {sum(unique_counts.values()):>6}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory sky130 instances in a GDS file.")
    parser.add_argument("--gds", required=True, help="Path to GDS file")
    parser.add_argument("--out", help="Write JSON inventory to this path")
    args = parser.parse_args()

    gds_path = Path(args.gds)
    if not gds_path.is_file():
        print(f"error: GDS not found: {gds_path}", file=sys.stderr)
        return 1

    layout = db.Layout()
    layout.read(str(gds_path))
    top = layout.top_cell()
    instances = collect_instances(layout, top)
    unique_counts = Counter(inst["master"] for inst in instances)

    payload = {
        "top": top.name,
        "dbu": layout.dbu,
        "instances": instances,
        "unique_counts": dict(sorted(unique_counts.items())),
    }

    print_table(unique_counts)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
        print(f"\nwrote {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
