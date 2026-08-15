#!/usr/bin/env python3
"""Screenshot one representative instance per unique DEF cell master."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import klayout.db as db

SKY130_PREFIX = "sky130_fd_sc_hd__"
COMPONENT_RE = re.compile(
    r"-\s+(\S+)\s+(sky130_fd_sc_hd__\S+)\s+.*?"
    r"(?:PLACED|FIXED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\S+)\s*;",
    re.MULTILINE,
)
DEF_TO_TRANS = {
    "N": db.Trans(0, False),
    "S": db.Trans(180, False),
    "E": db.Trans(90, False),
    "W": db.Trans(270, False),
    "FN": db.Trans(0, True),
    "FS": db.Trans(180, True),
    "FE": db.Trans(90, True),
    "FW": db.Trans(270, True),
}
PAD_UM = 0.3

# sky130 drawing layers: diff 65/20, poly 66/20, licon 66/44, li1 67/20, mcon 67/44, met1 68/20
LAYER_SETS = {
    # Original contacts view, plus diffusion and local interconnect.
    "composite": "65/20,66/20,66/44,67/20,67/44,68/20",
    # Routing-only fingerprint (pins and internal LI/M1).
    "li1_met1": "67/20,68/20",
    # Device fingerprint (active + gates).
    "diff_poly": "65/20,66/20",
}
SETS_RD = ";".join(f"{name}:{spec}" for name, spec in LAYER_SETS.items())


@dataclass(frozen=True)
class DefInstance:
    name: str
    master: str
    x_um: float
    y_um: float
    orient: str


def parse_def(def_path: Path) -> tuple[float, list[DefInstance]]:
    text = def_path.read_text(encoding="utf-8")
    units_match = re.search(r"UNITS\s+DISTANCE\s+MICRONS\s+(\d+)\s*;", text)
    units = int(units_match.group(1)) if units_match else 1000
    scale = 1.0 / units if units else 1.0

    instances: list[DefInstance] = []
    for match in COMPONENT_RE.finditer(text):
        x_um = int(match.group(3)) * scale
        y_um = int(match.group(4)) * scale
        instances.append(
            DefInstance(
                name=match.group(1),
                master=match.group(2),
                x_um=x_um,
                y_um=y_um,
                orient=match.group(5),
            )
        )
    return scale, instances


def first_per_master(instances: list[DefInstance]) -> dict[str, DefInstance]:
    seen: dict[str, DefInstance] = {}
    for inst in instances:
        if inst.master not in seen:
            seen[inst.master] = inst
    return seen


def instance_box_um(layout: db.Layout, inst: DefInstance) -> tuple[float, float, float, float]:
    cell = layout.cell(inst.master)
    if cell is None:
        raise KeyError(f"master not in GDS: {inst.master}")

    dbu = layout.dbu
    bbox = cell.bbox().to_dtype(dbu)
    base_trans = DEF_TO_TRANS.get(inst.orient)
    if base_trans is None:
        raise ValueError(f"unknown orient {inst.orient!r} for {inst.name}")

    placement = db.DTrans(base_trans)
    placement.disp = db.DVector(inst.x_um, inst.y_um)
    transformed = placement * bbox
    padded = transformed.enlarged(db.DVector(PAD_UM, PAD_UM))
    return padded.left, padded.bottom, padded.right, padded.top


def screenshot_cmd(
    script_path: Path,
    gds: Path,
    lyp: Path | None,
    box: tuple[float, float, float, float],
    out: Path,
) -> list[str]:
    x1, y1, x2, y2 = box
    cmd = [
        "klayout",
        "-z",
        "-r",
        str(script_path),
        "-rd",
        f"gds={gds}",
        "-rd",
        f"box={x1},{y1},{x2},{y2}",
        "-rd",
        f"out={out}",
        "-rd",
        f"sets={SETS_RD}",
    ]
    if lyp is not None:
        cmd.extend(["-rd", f"lyp={lyp}"])
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(description="Screenshot unique DEF cell masters.")
    parser.add_argument("--def", dest="def_path", required=True, help="DEF file")
    parser.add_argument("--gds", required=True, help="GDS file")
    parser.add_argument("--lyp", help="Layer properties file")
    parser.add_argument("--out-dir", required=True, help="Output directory for PNGs")
    args = parser.parse_args()

    def_path = Path(args.def_path)
    gds_path = Path(args.gds)
    lyp_path = Path(args.lyp) if args.lyp else None
    out_dir = Path(args.out_dir)
    script_path = Path(__file__).resolve().parent / "screenshot.py"

    if not def_path.is_file():
        print(f"error: DEF not found: {def_path}", file=sys.stderr)
        return 1
    if not gds_path.is_file():
        print(f"error: GDS not found: {gds_path}", file=sys.stderr)
        return 1
    if lyp_path is not None and not lyp_path.is_file():
        print(f"error: LYP not found: {lyp_path}", file=sys.stderr)
        return 1

    _, instances = parse_def(def_path)
    representatives = first_per_master(instances)

    layout = db.Layout()
    layout.read(str(gds_path))

    out_dir.mkdir(parents=True, exist_ok=True)
    klayout = shutil.which("klayout")
    written: list[Path] = []

    for master, inst in sorted(representatives.items()):
        safe_master = master.replace("/", "_")
        safe_name = inst.name.replace("/", "_")
        stem = out_dir / f"{safe_master}__{safe_name}_{inst.orient}.png"
        try:
            box = instance_box_um(layout, inst)
        except (KeyError, ValueError) as exc:
            print(f"skip {master}: {exc}", file=sys.stderr)
            continue

        cmd = screenshot_cmd(script_path, gds_path, lyp_path, box, stem)
        if klayout is None:
            print("klayout not in PATH; would run:")
            print(" ".join(cmd))
            continue

        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"error: screenshot failed for {master}", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            if result.stdout:
                print(result.stdout, file=sys.stderr)
            continue
        for set_name in LAYER_SETS:
            written.append(out_dir / f"{stem.stem}__{set_name}{stem.suffix}")

    print("manifest:")
    if written:
        for path in written:
            print(path)
    else:
        print("(no files written)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
