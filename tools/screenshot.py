#!/usr/bin/env python3
"""Capture a zoomed layout screenshot (run via KLayout batch mode)."""

from __future__ import annotations

import os
import sys

USAGE = """usage: klayout -z -r tools/screenshot.py \\
  -rd gds=PATH -rd lyp=PATH -rd box=x1,y1,x2,y2 -rd out=PATH \\
  [-rd layers=66/20,66/44,67/44,68/20] \\
  [-rd sets=composite:65/20,66/20,66/44,67/20,67/44,68/20;diff_poly:65/20,66/20]

If `sets` is given, `out` is a filename stem and one PNG is written per set
as `{stem}__{setname}.png`.
"""


def _missing_rd(name: str) -> bool:
    return name not in globals()


def main() -> int:
    try:
        import pya
        from pya import Application
    except ImportError:
        print("run via klayout -z -r tools/screenshot.py -rd gds=... -rd box=... -rd out=...")
        return 1

    if Application is None or Application.instance() is None:
        print("run via klayout -z -r tools/screenshot.py -rd gds=... -rd box=... -rd out=...")
        return 1

    required = ("gds", "box", "out")
    if any(_missing_rd(name) for name in required):
        print(USAGE, file=sys.stderr)
        return 1

    gds_path = str(globals()["gds"])
    box_str = str(globals()["box"])
    out_path = str(globals()["out"])
    lyp_path = str(globals()["lyp"]) if not _missing_rd("lyp") else ""
    layers_str = (
        str(globals()["layers"])
        if not _missing_rd("layers")
        else "66/20,66/44,67/44,68/20"
    )
    sets_str = str(globals()["sets"]) if not _missing_rd("sets") else ""

    try:
        coords = [float(v.strip()) for v in box_str.split(",")]
        if len(coords) != 4:
            raise ValueError("expected four coordinates")
        x1, y1, x2, y2 = coords
    except ValueError:
        print("error: box must be x1,y1,x2,y2 in micrometers", file=sys.stderr)
        return 1

    def parse_layers(spec: str) -> set[tuple[int, int]]:
        visible: set[tuple[int, int]] = set()
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            layer_s, datatype_s = part.split("/")
            visible.add((int(layer_s), int(datatype_s)))
        return visible

    jobs: list[tuple[str, set[tuple[int, int]]]] = []
    if sets_str:
        for item in sets_str.split(";"):
            item = item.strip()
            if not item:
                continue
            name, spec = item.split(":", 1)
            jobs.append((name.strip(), parse_layers(spec)))
    else:
        jobs.append(("", parse_layers(layers_str)))

    app = pya.Application.instance()
    mw = app.main_window()
    mw.load_layout(gds_path, 0)
    view = mw.current_view()
    if view is None:
        print("error: no active layout view", file=sys.stderr)
        return 1

    if lyp_path:
        view.load_layer_props(lyp_path)

    view.max_hier()
    view.zoom_box(pya.DBox(x1, y1, x2, y2))
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    stem, ext = os.path.splitext(out_path)
    if not ext:
        ext = ".png"

    for set_name, visible_layers in jobs:
        for layer_node in view.each_layer():
            key = (layer_node.source_layer, layer_node.source_datatype)
            layer_node.visible = key in visible_layers
        view.update_content()
        dest = f"{stem}__{set_name}{ext}" if set_name else out_path
        view.save_image(dest, 1024, 1024)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
