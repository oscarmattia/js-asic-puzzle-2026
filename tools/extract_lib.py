"""Helpers for GDS gate-level netlist extraction (sky130_fd_sc_hd)."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import klayout.db as db

SKY130_PREFIX = "sky130_fd_sc_hd__"
POWER_PINS = frozenset({"VPWR", "VGND", "VNB", "VPB", "VPWRIN", "VGNDIN"})
FILL_KEYWORDS = ("decap", "fill", "tapvpwrvgnd", "tap", "nwell", "pwell", "filler")
# Antenna diodes have a real DIODE signal pin (see cells/diode/*.lef and netlist.tsv).
FOLLOWPIN_MET1_WIDTH = 400  # sky130-hd VPWR/VGND met1 PORT is 0.48 um
# Top-level power mesh / via landings vs signal paths (puzzle met3: 330 vs 300).
POWER_PATH_WIDTH = {
    "met1": 400,
    "met3": 320,
    "met4": 400,
    "met5": 400,
}

DRAW_LAYERS: dict[str, tuple[int, int]] = {
    "li1": (67, 20),
    "mcon": (67, 44),
    "met1": (68, 20),
    "via12": (68, 44),
    "met2": (69, 20),
    "via23": (69, 44),
    "met3": (70, 20),
    "via34": (70, 44),
    "met4": (71, 20),
    "via45": (71, 44),
    "met5": (72, 20),
}

PIN_SHAPE_LAYERS: dict[str, tuple[int, int]] = {
    "li1": (67, 16),
    "met1": (68, 16),
    "met2": (69, 16),
    "met3": (70, 16),
    "met4": (71, 16),
    "met5": (72, 16),
}

LABEL_LAYERS: dict[str, tuple[int, int]] = {
    "li1": (67, 5),
    "met1": (68, 5),
    "met2": (69, 5),
    "met3": (70, 5),
    "met4": (71, 5),
    "met5": (72, 5),
}

MERGE_LAYERS = ("li1", "met1", "met2", "met3", "met4", "met5")
VIA_BRIDGES = (
    ("li1", "mcon", "met1"),
    ("met1", "via12", "met2"),
    ("met2", "via23", "met3"),
    ("met3", "via34", "met4"),
    ("met4", "via45", "met5"),
)


def is_fill_cell(master_name: str) -> bool:
    if not master_name.startswith(SKY130_PREFIX):
        return True
    short = master_name[len(SKY130_PREFIX) :]
    return any(k in short for k in FILL_KEYWORDS)


def is_power_via_cell(name: str) -> bool:
    """OpenROAD signal vias are VIA_M1M2_PR / VIA_L1M1_PR_MR; power vias are VIA_via*."""
    return name.startswith("VIA_via")


def is_power_pin(name: str) -> bool:
    return name.upper() in POWER_PINS


BIT_PORT_RE = re.compile(r"^(\w+)\[(\d+)\]$")


def normalize_port_name(name: str) -> str:
    if name in {"input", "in"}:
        return "I"
    m = re.match(r"^out\[(\d+)\]$", name, re.I)
    if m:
        return f"O[{m.group(1)}]"
    return name


def bus_from_names(names: list[str]) -> dict[str, int]:
    buses: dict[str, int] = {}
    for name in names:
        m = BIT_PORT_RE.match(name)
        if m:
            bus, bit = m.group(1), int(m.group(2))
            buses[bus] = max(buses.get(bus, 0), bit)
    return buses


def net_is_port(net: str, port_order: list[str], buses: dict[str, int]) -> bool:
    if net in port_order or net in buses:
        return True
    m = BIT_PORT_RE.match(net)
    return bool(m and (m.group(1) in port_order or m.group(1) in buses))


@dataclass
class PinGeom:
    name: str
    metal: str
    box: db.Box


@dataclass
class Instance:
    name: str
    master: str
    pins: list[PinGeom] = field(default_factory=list)


@dataclass
class Port:
    name: str
    metal: str
    box: db.Box


@dataclass
class Terminal:
    tid: int
    inst_name: str
    pin_name: str
    metal: str
    box: db.Box


class UnionFind:
    def __init__(self) -> None:
        self.parent: list[int] = []

    def add(self) -> int:
        self.parent.append(len(self.parent))
        return len(self.parent) - 1

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _text_box(text: db.Text, margin_dbu: int = 200) -> db.Box:
    box = text.bbox()
    if box.empty():
        pt = text.position()
        box = db.Box(pt.x - margin_dbu, pt.y - margin_dbu, pt.x + margin_dbu, pt.y + margin_dbu)
    else:
        box = box.enlarged(margin_dbu)
    return box


def _label_box(text: db.Text, margin_dbu: int = 200) -> db.Box:
    return _text_box(text, margin_dbu)


def _shape_box(shape: db.Shape) -> db.Box:
    if shape.is_box():
        return shape.box
    if shape.is_polygon():
        return shape.polygon.bbox()
    if shape.is_path():
        return shape.path.bbox()
    if shape.is_text():
        return _label_box(shape.text)
    return db.Box()


def parse_lef_pins(
    lef_path: Path,
    dbu: float = 0.001,
) -> dict[str, list[tuple[str, db.Box]]] | None:
    if not lef_path.is_file():
        return None
    text = lef_path.read_text(encoding="utf-8", errors="replace")
    pins: dict[str, list[tuple[str, db.Box]]] = defaultdict(list)
    current_pin: str | None = None
    current_layer: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("PIN "):
            current_pin = line.split()[1]
            current_layer = None
            continue
        if line.startswith("END ") and current_pin and line.endswith(current_pin):
            current_pin = None
            current_layer = None
            continue
        if current_pin is None:
            continue
        if line.startswith("LAYER "):
            current_layer = line.split()[1].lower()
            continue
        m = re.match(r"RECT\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)", line)
        if m and current_layer:
            x1, y1, x2, y2 = (int(round(float(v) / dbu)) for v in m.groups())
            pins[current_pin].append((current_layer, db.Box(x1, y1, x2, y2)))
    return dict(pins) if pins else None


def find_lef(lef_dir: Path, cell_name: str) -> Path | None:
    direct = lef_dir / f"{cell_name}.lef"
    if direct.is_file():
        return direct
    matches = sorted(lef_dir.rglob(f"{cell_name}.lef"))
    return matches[0] if matches else None


def _nearest_label(layout: db.Layout, master: db.Cell, metal: str, box: db.Box) -> str | None:
    ln, dt = LABEL_LAYERS[metal]
    li = layout.layer(ln, dt)
    best: tuple[int, str] | None = None
    center = box.center()
    cx, cy = center.x, center.y
    for shape in master.shapes(li).each():
        if not shape.is_text():
            continue
        pt = shape.text.position()
        dist = abs(pt.x - cx) + abs(pt.y - cy)
        if best is None or dist < best[0]:
            best = (dist, shape.text.string)
    return best[1] if best else None


def pins_from_master(
    layout: db.Layout,
    master: db.Cell,
    lef_dir: Path | None,
    pin_cache: dict[tuple[str, bool], list[PinGeom]],
    include_power: bool = False,
) -> list[PinGeom]:
    cache_key = (master.name, include_power)
    if cache_key in pin_cache:
        return pin_cache[cache_key]

    geoms: list[PinGeom] = []
    if lef_dir is not None:
        lef_path = find_lef(lef_dir, master.name)
        lef_pins = parse_lef_pins(lef_path, dbu=layout.dbu) if lef_path else None
        if lef_pins:
            for pname, rects in lef_pins.items():
                if is_power_pin(pname) and not include_power:
                    continue
                for metal, box in rects:
                    geoms.append(PinGeom(pname, metal, box))

    if not geoms:
        seen: set[tuple[str, str]] = set()
        for metal, (ln, dt) in LABEL_LAYERS.items():
            li = layout.layer(ln, dt)
            for shape in master.shapes(li).each():
                if not shape.is_text():
                    continue
                name = shape.text.string
                if is_power_pin(name) and not include_power:
                    continue
                key2 = (name, metal)
                if key2 in seen:
                    continue
                seen.add(key2)
                geoms.append(PinGeom(name, metal, _label_box(shape.text)))
        for metal, (ln, dt) in PIN_SHAPE_LAYERS.items():
            li = layout.layer(ln, dt)
            for shape in master.shapes(li).each():
                box = _shape_box(shape)
                label = _nearest_label(layout, master, metal, box)
                if not label:
                    continue
                if is_power_pin(label) and not include_power:
                    continue
                key2 = (label, metal)
                if key2 in seen:
                    continue
                seen.add(key2)
                geoms.append(PinGeom(label, metal, box))

    pin_cache[cache_key] = geoms
    return geoms


def parse_def_ports(def_path: Path) -> list[Port]:
    if not def_path.is_file():
        return []
    text = def_path.read_text(encoding="utf-8", errors="replace")
    ports: list[Port] = []
    in_pins = False
    current: str | None = None
    current_metal: str | None = None

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("PINS "):
            in_pins = True
            continue
        if in_pins and line == "END PINS":
            break
        if not in_pins:
            continue
        if line.startswith("- ") and " + NET " in line:
            current = line.split()[1]
            current_metal = None
            continue
        if current is None or is_power_pin(current):
            continue
        if line.startswith("+ LAYER "):
            current_metal = line.split()[2].lower()
            continue
        if line.startswith("+ PLACED ") or line.startswith("+ FIXED "):
            parts = line.split()
            try:
                x = int(parts[2])
                y = int(parts[3])
            except (IndexError, ValueError):
                continue
            half = 300
            ports.append(
                Port(current, current_metal or "met3", db.Box(x - half, y - half, x + half, y + half))
            )
    return ports


def collect_top_labels(layout: db.Layout, top: db.Cell) -> list[Port]:
    ports: list[Port] = []
    for metal, (ln, dt) in LABEL_LAYERS.items():
        li = layout.layer(ln, dt)
        for shape in top.shapes(li).each():
            if not shape.is_text():
                continue
            name = normalize_port_name(shape.text.string)
            if is_power_pin(name):
                continue
            ports.append(Port(name, metal, _label_box(shape.text, margin_dbu=400)))
    for metal, (ln, dt) in PIN_SHAPE_LAYERS.items():
        li = layout.layer(ln, dt)
        for shape in top.shapes(li).each():
            box = _shape_box(shape)
            if box.empty() or box.width() > 5000 or box.height() > 5000:
                continue
            name = _nearest_label(layout, top, metal, box)
            if not name:
                continue
            name = normalize_port_name(name)
            if is_power_pin(name):
                continue
            ports.append(Port(name, metal, box))
    return ports


def _insert_shapes(
    region: db.Region,
    cell: db.Cell,
    layer_index: int,
    trans: db.ICplxTrans,
    skip_power: bool = False,
    layer_name: str = "",
) -> None:
    thresh = POWER_PATH_WIDTH.get(layer_name, 0) if skip_power else 0
    for shape in cell.shapes(layer_index).each():
        if thresh:
            if shape.is_path() and shape.path.width >= thresh:
                continue
            box = shape.bbox()
            if not box.empty() and min(box.width(), box.height()) >= thresh:
                continue
        poly = shape.polygon
        if poly is None or poly.bbox().empty():
            continue
        region.insert(poly.transformed(trans))


def collect_top_routing(layout: db.Layout, top: db.Cell) -> dict[str, db.Region]:
    """Top-level metals plus via cells; do not flatten stdcell internals.

    OpenROAD puts signal vias in VIA_* child cells. ``db.Region(RecursiveShapeIterator)``
    ignores max_depth, so we walk the hierarchy by hand and skip sky130 masters.
    HD followpin rails are 0.48 um met1 (LEF VPWR/VGND PORT); leave them out of the
    signal graph so via-flooding cannot merge signals into the power mesh.
    """
    regions: dict[str, db.Region] = {name: db.Region() for name in DRAW_LAYERS}
    layer_ids = {name: layout.layer(ln, dt) for name, (ln, dt) in DRAW_LAYERS.items()}

    def walk(cell: db.Cell, trans: db.ICplxTrans) -> None:
        for name, li in layer_ids.items():
            _insert_shapes(
                regions[name], cell, li, trans, skip_power=True, layer_name=name
            )
        for inst in cell.each_inst():
            master = inst.cell
            if master.name.startswith(SKY130_PREFIX) or is_power_via_cell(master.name):
                continue
            walk(master, trans * inst.cplx_trans)

    walk(top, db.ICplxTrans())
    return regions


VIA_FOR_METAL = {
    "li1": "mcon",
    "met1": "via12",
    "met2": "via23",
    "met3": "via34",
}


def inject_pin_boxes(routing: dict[str, db.Region], terminals: list[Terminal]) -> None:
    """Insert pin-access boxes (already clipped to vias / metal landings)."""
    for term in terminals:
        if term.box.area() > 2_000_000:
            continue
        if term.metal not in routing:
            routing[term.metal] = db.Region()
        routing[term.metal].insert(term.box)


def _clip_boxes(term: Terminal, routing: dict[str, db.Region]) -> list[db.Box]:
    """Intersect a LEF pin rect with via landings, else with same-layer routing.

    LEF PORTs include internal straps (mux2_1 S, clkbuf_16 X, conb_1 HI/LO in
    the .lef/.svg). Using the full rect shorts neighbors; via clips are the
    actual pin-access points.
    """
    probe = db.Region(term.box)
    via_name = VIA_FOR_METAL.get(term.metal)
    if via_name and via_name in routing:
        boxes: list[db.Box] = []
        for via in routing[via_name].interacting(probe).each():
            clipped = via.bbox() & term.box
            boxes.append(clipped if not clipped.empty() else via.bbox())
        if boxes:
            return boxes
    if term.metal in routing:
        boxes = []
        for poly in (routing[term.metal] & probe).each():
            box = poly.bbox()
            if box.empty() or box.area() > 2_000_000:
                continue
            boxes.append(box)
        if boxes:
            return boxes
    return []


def prune_pin_rects(
    terminals: list[Terminal],
    routing: dict[str, db.Region],
) -> list[Terminal]:
    """Replace full LEF pin rects with via/metal landing clips."""
    grouped: dict[tuple[str, str], list[Terminal]] = defaultdict(list)
    for term in terminals:
        grouped[(term.inst_name, term.pin_name)].append(term)

    kept: list[Terminal] = []
    tid = 0
    for group in grouped.values():
        boxes: list[tuple[str, db.Box]] = []
        for term in group:
            boxes.extend((term.metal, box) for box in _clip_boxes(term, routing))
        if not boxes:
            term = min(group, key=lambda t: t.box.area())
            boxes = [(term.metal, term.box)]
        inst_name, pin_name = group[0].inst_name, group[0].pin_name
        for metal, box in boxes:
            kept.append(Terminal(tid, inst_name, pin_name, metal, box))
            tid += 1
    return kept


def collect_power_boxes(
    layout: db.Layout,
    top: db.Cell,
    lef_dir: Path | None,
) -> list[tuple[str, db.Box]]:
    pin_cache: dict[tuple[str, bool], list[PinGeom]] = {}
    boxes: list[tuple[str, db.Box]] = []

    def walk(cell: db.Cell, trans: db.ICplxTrans) -> None:
        for inst in cell.each_inst():
            master = inst.cell
            tr = trans * inst.cplx_trans
            if master.name.startswith(SKY130_PREFIX):
                pins = pins_from_master(layout, master, lef_dir, pin_cache, include_power=True)
                for pin in pins:
                    if is_power_pin(pin.name):
                        boxes.append((pin.metal, db.Polygon(pin.box).transformed(tr).bbox()))
            else:
                walk(master, tr)

    walk(top, db.ICplxTrans())
    return boxes


def mark_power_roots(
    clusters: dict[str, LayerClusters],
    power_boxes: list[tuple[str, db.Box]],
    uf: UnionFind,
) -> set[int]:
    roots: set[int] = set()
    for metal, box in power_boxes:
        if metal in clusters:
            roots.update(clusters[metal].roots_for_box(box, uf))
    return {uf.find(r) for r in roots}


@dataclass
class LayerClusters:
    polys: list[db.Polygon]
    net_ids: list[int]

    def roots_for_box(self, box: db.Box, uf: UnionFind) -> set[int]:
        hits: set[int] = set()
        if not self.polys:
            return hits
        probe = db.Region(box)
        for i, poly in enumerate(self.polys):
            if not poly.bbox().overlaps(box):
                continue
            if not db.Region(poly).interacting(probe).is_empty():
                hits.add(uf.find(self.net_ids[i]))
        return hits


def _build_layer_clusters(region: db.Region, uf: UnionFind) -> LayerClusters:
    merged = region.merged()
    polys = [p for p in merged.each()]
    net_ids = [uf.add() for _ in polys]
    return LayerClusters(polys, net_ids)


def connect_clusters(a: LayerClusters, b: LayerClusters, bridge: db.Region, uf: UnionFind) -> None:
    if bridge.is_empty() or not a.polys or not b.polys:
        return
    a_regs = [db.Region(p) for p in a.polys]
    b_regs = [db.Region(p) for p in b.polys]
    a_bboxes = [p.bbox() for p in a.polys]
    b_bboxes = [p.bbox() for p in b.polys]
    for via in bridge.each():
        via_box = via.bbox()
        via_r = db.Region(via)
        a_hits = [
            i
            for i, ar in enumerate(a_regs)
            if a_bboxes[i].overlaps(via_box) and not ar.interacting(via_r).is_empty()
        ]
        if not a_hits:
            continue
        b_hits = [
            j
            for j, br in enumerate(b_regs)
            if b_bboxes[j].overlaps(via_box) and not br.interacting(via_r).is_empty()
        ]
        for i in a_hits:
            for j in b_hits:
                uf.union(a.net_ids[i], b.net_ids[j])


def build_clusters(routing: dict[str, db.Region], uf: UnionFind) -> dict[str, LayerClusters]:
    clusters: dict[str, LayerClusters] = {}
    for metal in MERGE_LAYERS:
        clusters[metal] = _build_layer_clusters(routing.get(metal, db.Region()), uf)
    clusters["mcon"] = _build_layer_clusters(routing.get("mcon", db.Region()), uf)
    for low, via, high in VIA_BRIDGES:
        connect_clusters(clusters[low], clusters[high], routing.get(via, db.Region()), uf)
        if via in clusters:
            connect_clusters(clusters[via], clusters[high], routing.get(via, db.Region()), uf)
            connect_clusters(clusters[via], clusters[low], routing.get(via, db.Region()), uf)
    return clusters


def _filter_power(roots: set[int], uf: UnionFind, power_roots: set[int]) -> set[int]:
    if not power_roots:
        return {uf.find(r) for r in roots}
    return {uf.find(r) for r in roots if uf.find(r) not in power_roots}


def attach_terminals(
    clusters: dict[str, LayerClusters],
    terminals: list[Terminal],
    uf: UnionFind,
    power_roots: set[int] | None = None,
) -> dict[int, int]:
    power_roots = power_roots or set()
    terminal_root: dict[int, int] = {}
    for term in terminals:
        probe = term.box.enlarged(50)
        roots = clusters[term.metal].roots_for_box(probe, uf) if term.metal in clusters else set()
        roots = _filter_power(roots, uf, power_roots)
        if not roots:
            for metal in ("mcon", "met1", "li1", "met2", "met3"):
                if metal in clusters:
                    roots = _filter_power(clusters[metal].roots_for_box(probe, uf), uf, power_roots)
                    if roots:
                        break
        terminal_root[term.tid] = min(roots) if roots else uf.add()
    return terminal_root


def union_same_pin_terminals(
    terminals: list[Terminal],
    terminal_root: dict[int, int],
    uf: UnionFind,
) -> None:
    """All LEF rects of one instance pin are the same electrical node."""
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for term in terminals:
        groups[(term.inst_name, term.pin_name)].append(term.tid)
    for tids in groups.values():
        if len(tids) < 2:
            continue
        first = terminal_root[tids[0]]
        for tid in tids[1:]:
            uf.union(first, terminal_root[tid])
    for tid in list(terminal_root):
        terminal_root[tid] = uf.find(terminal_root[tid])


def collect_instances(
    layout: db.Layout,
    top: db.Cell,
    lef_dir: Path | None,
) -> tuple[list[Instance], list[Terminal]]:
    pin_cache: dict[tuple[str, bool], list[PinGeom]] = {}
    instances: list[Instance] = []
    terminals: list[Terminal] = []
    idx = 0
    tid = 0

    def walk(cell: db.Cell, trans: db.ICplxTrans) -> None:
        nonlocal idx, tid
        for inst in cell.each_inst():
            master = inst.cell
            master_name = master.name
            tr = trans * inst.cplx_trans
            if master_name.startswith(SKY130_PREFIX):
                if is_fill_cell(master_name):
                    continue
                iname = getattr(inst, "name", "") or f"inst{idx}"
                idx += 1
                pins = pins_from_master(layout, master, lef_dir, pin_cache)
                transformed: list[PinGeom] = []
                for pin in pins:
                    box = db.Polygon(pin.box).transformed(tr).bbox()
                    transformed.append(PinGeom(pin.name, pin.metal, box))
                instances.append(Instance(iname, master_name, transformed))
                for pin in transformed:
                    terminals.append(Terminal(tid, iname, pin.name, pin.metal, pin.box))
                    tid += 1
            else:
                walk(master, tr)

    walk(top, db.ICplxTrans())
    return instances, terminals


def _roots_for_port(
    port: Port,
    clusters: dict[str, LayerClusters],
    uf: UnionFind,
    power_roots: set[int] | None = None,
) -> set[int]:
    metals = [port.metal] if port.metal in clusters else list(MERGE_LAYERS)
    roots: set[int] = set()
    for metal in metals:
        if metal not in clusters:
            continue
        roots.update(clusters[metal].roots_for_box(port.box, uf))
    return _filter_power(roots, uf, power_roots or set())


def assign_net_names(
    uf: UnionFind,
    terminal_root: dict[int, int],
    terminals: list[Terminal],
    clusters: dict[str, LayerClusters],
    port_candidates: list[Port],
    power_roots: set[int] | None = None,
) -> dict[int, str]:
    root_label: dict[int, str] = {}
    unnamed = 0

    def fresh_name() -> str:
        nonlocal unnamed
        name = f"n_{unnamed}"
        unnamed += 1
        return name

    for port in port_candidates:
        for root in _roots_for_port(port, clusters, uf, power_roots):
            if root not in root_label:
                root_label[root] = port.name

    net_names: dict[int, str] = {}
    for term in terminals:
        root = uf.find(terminal_root[term.tid])
        if root not in root_label:
            root_label[root] = fresh_name()
        net_names[term.tid] = root_label[root]
    return net_names


def coalesce_reset_nets(
    terminals: list[Terminal],
    net_names: dict[int, str],
    reset_port: str = "rst_n",
) -> int:
    """Tie undriven RESET_B/SET_B-only nets to the chip reset port.

    High-fanout reset is often a met1 trunk that pin-via clipping splits. If a
    net only touches flop reset pins, it is the same net as ``rst_n``.
    """
    pins_by_net: dict[str, set[str]] = defaultdict(set)
    for term in terminals:
        pins_by_net[net_names[term.tid]].add(term.pin_name)
    n = 0
    for tid, name in list(net_names.items()):
        if name == reset_port:
            continue
        pins = pins_by_net.get(name, set())
        if pins and pins <= {"RESET_B", "SET_B"}:
            net_names[tid] = reset_port
            n += 1
    return n


def emit_verilog(
    module_name: str,
    instances: list[Instance],
    terminals: list[Terminal],
    net_names: dict[int, str],
    port_order: list[str],
    buses: dict[str, int] | None = None,
) -> tuple[str, int]:
    buses = dict(buses or {})
    header: list[str] = []
    for port in port_order:
        if port not in header:
            header.append(port)
    for bus in buses:
        if bus not in header:
            header.append(bus)

    lines: list[str] = []
    lines.append(f"module {module_name} ({', '.join(header)});")
    outputs = {"S", "success", "O"}
    for port in header:
        direction = "output" if port in outputs or port.startswith("out") else "input"
        if port in buses:
            lines.append(f"  {direction} [{buses[port]}:0] {port};")
        else:
            lines.append(f"  {direction} {port};")

    inst_pins: dict[str, dict[str, str]] = defaultdict(dict)
    for term in terminals:
        inst_pins[term.inst_name][term.pin_name] = net_names.get(term.tid, "n_unknown")

    net_fanout: dict[str, int] = defaultdict(int)
    for pins in inst_pins.values():
        for net in pins.values():
            net_fanout[net] += 1

    used_nets = sorted(
        {
            net
            for pins in inst_pins.values()
            for net in pins.values()
            if not net_is_port(net, header, buses)
        }
    )
    for net in used_nets:
        lines.append(f"  wire {net};")

    dangling_pins = 0
    for inst in instances:
        pins = inst_pins.get(inst.name, {})
        if not pins:
            lines.append(f"  {inst.master} {inst.name} ();")
            continue
        for net in pins.values():
            if not net_is_port(net, header, buses) and net_fanout.get(net, 0) <= 1:
                dangling_pins += 1
        conn = ", ".join(f".{pin}({net})" for pin, net in sorted(pins.items()))
        lines.append(f"  {inst.master} {inst.name} ({conn});")

    lines.append("endmodule")
    return "\n".join(lines) + "\n", dangling_pins


def resolve_top_cell(layout: db.Layout, top_name: str | None) -> db.Cell:
    if top_name:
        cell = layout.cell(top_name)
        if cell is None:
            raise ValueError(f"top cell not found: {top_name}")
        return cell
    return layout.top_cell()
