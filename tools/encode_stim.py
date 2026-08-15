#!/usr/bin/env python3
"""Encode a candidate serial bitstream into a puzzle stim file.

Protocol recovered from example_inputs.vcd + extracted counters:
  3 cycles rst_n=0, then 121 enable cycles (11 chars x 11 bits), then drain.
  Default bit packing is 11-bit LSB-first ASCII (bits 8-10 are 0 for 7-bit text).
"""

from __future__ import annotations

import argparse
from pathlib import Path


def bits_11_lsb(text: str) -> list[int]:
    out: list[int] = []
    for ch in text:
        v = ord(ch)
        for i in range(11):
            out.append((v >> i) & 1)
    return out


def bits_11_msb(text: str) -> list[int]:
    out: list[int] = []
    for ch in text:
        v = ord(ch)
        for i in range(10, -1, -1):
            out.append((v >> i) & 1)
    return out


def bits_8_lsb(text: str) -> list[int]:
    out: list[int] = []
    for ch in text:
        v = ord(ch)
        for i in range(8):
            out.append((v >> i) & 1)
    return out


def bits_8_msb(text: str) -> list[int]:
    out: list[int] = []
    for ch in text:
        v = ord(ch)
        for i in range(7, -1, -1):
            out.append((v >> i) & 1)
    return out


ENCODERS = {
    "11lsb": bits_11_lsb,
    "11msb": bits_11_msb,
    "8lsb": bits_8_lsb,
    "8msb": bits_8_msb,
}


def write_stim(
    bits: list[int],
    path: Path,
    rst_cycles: int = 3,
    drain: int = 24,
    pad_to: int | None = 121,
) -> int:
    payload = list(bits)
    if pad_to is not None:
        if len(payload) < pad_to:
            payload = payload + [0] * (pad_to - len(payload))
        else:
            payload = payload[:pad_to]
    lines = ["# rst_n enable I"]
    for _ in range(rst_cycles):
        lines.append("0 0 0")
    for b in payload:
        lines.append(f"1 1 {b}")
    for _ in range(drain):
        lines.append("1 0 0")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True)
    parser.add_argument("--enc", choices=sorted(ENCODERS), default="11lsb")
    parser.add_argument("--out", default="build/candidate_stim.txt")
    parser.add_argument("--pad", type=int, default=121)
    parser.add_argument("--no-pad", action="store_true")
    args = parser.parse_args()
    bits = ENCODERS[args.enc](args.text)
    n = write_stim(bits, Path(args.out), pad_to=None if args.no_pad else args.pad)
    pad_note = "unpadded" if args.no_pad else f"pad_to={args.pad}"
    print(f"wrote {args.out} text={args.text!r} enc={args.enc} raw_bits={len(bits)} enable_bits={n} {pad_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
