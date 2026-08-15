#!/usr/bin/env python3
"""Turn example_inputs.vcd into a per-posedge (rst_n, enable, I) stimulus file."""

from __future__ import annotations

import argparse
from pathlib import Path

CODE_MAP = {
    "!": "clk",
    '"': "rst_n",
    "#": "enable",
    "$": "I",
    "%": "O",
    "&": "success",
}


def parse_vcd(path: Path) -> list[tuple[int, str, str, str, str, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    body = text.split("$enddefinitions $end", 1)[1]
    time = 0
    vals = {name: "x" for name in CODE_MAP.values()}
    last_clk = "x"
    samples: list[tuple[int, str, str, str, str, str]] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("$"):
            continue
        if line.startswith("#"):
            time = int(line[1:])
            continue
        if line.startswith("b"):
            parts = line.split()
            code = parts[1]
            if code in CODE_MAP:
                vals[CODE_MAP[code]] = parts[0][1:]
            continue
        if len(line) >= 2 and line[1:] in CODE_MAP:
            name = CODE_MAP[line[1:]]
            vals[name] = line[0]
            if name == "clk" and last_clk == "0" and line[0] == "1":
                samples.append(
                    (time, vals["rst_n"], vals["enable"], vals["I"], vals["O"], vals["success"])
                )
            last_clk = vals["clk"]
    return samples


def ascii_from_o(bits: str) -> str:
    bits = bits.strip()
    if not bits or bits[0] in "xzXZ":
        return "?"
    try:
        return chr(int(bits, 2) & 0xFF)
    except ValueError:
        return "?"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vcd", default="example_inputs.vcd")
    parser.add_argument("--out", default="build/puzzle_stim.txt")
    args = parser.parse_args()
    samples = parse_vcd(Path(args.vcd))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# rst_n enable I"]
    for _t, rst_n, enable, i, _o, _s in samples:
        def bit(v: str) -> str:
            return "1" if v == "1" else "0"

        lines.append(f"{bit(rst_n)} {bit(enable)} {bit(i)}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(samples)} cycles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
