#!/usr/bin/env python3
"""Cycle-accurate Python sim of build/puzzle_extracted.v. No VCD."""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

INST_RE = re.compile(r"(sky130_fd_sc_hd__\w+)\s+(\w+)\s+\((.*?)\);", re.S)
PIN_RE = re.compile(r"\.(\w+)\(([^)]+)\)")
OUT = frozenset({"X", "Y", "Q", "Q_N", "QN", "Z", "ZN", "HI", "LO"})
SEQ = ("dfrtp", "dfstp", "dfxtp")


def bnot(x: int) -> int:
    return 1 - x


def band(*xs: int) -> int:
    r = 1
    for x in xs:
        r &= x
    return r


def bor(*xs: int) -> int:
    r = 0
    for x in xs:
        r |= x
    return r


def FUN(short: str, p: dict[str, int]) -> int:
    n = re.sub(r"_\d+$", "", short)
    if n in {"buf", "clkbuf"}:
        return p["A"]
    if n == "inv":
        return bnot(p["A"])
    if n == "and2":
        return band(p["A"], p["B"])
    if n == "and2b":
        return band(bnot(p["A_N"]), p["B"])
    if n == "and3":
        return band(p["A"], p["B"], p["C"])
    if n == "and3b":
        return band(bnot(p["A_N"]), p["B"], p["C"])
    if n == "and4":
        return band(p["A"], p["B"], p["C"], p["D"])
    if n == "and4b":
        return band(bnot(p["A_N"]), p["B"], p["C"], p["D"])
    if n == "and4bb":
        return band(bnot(p["A_N"]), bnot(p["B_N"]), p["C"], p["D"])
    if n == "nand2":
        return bnot(band(p["A"], p["B"]))
    if n == "nand2b":
        return bnot(band(bnot(p["A_N"]), p["B"]))
    if n == "nand3":
        return bnot(band(p["A"], p["B"], p["C"]))
    if n == "nand3b":
        return bnot(band(bnot(p["A_N"]), p["B"], p["C"]))
    if n == "nand4":
        return bnot(band(p["A"], p["B"], p["C"], p["D"]))
    if n == "nor2":
        return bnot(bor(p["A"], p["B"]))
    if n == "nor3":
        return bnot(bor(p["A"], p["B"], p["C"]))
    if n == "nor3b":
        return band(bnot(bor(p["A"], p["B"])), p["C_N"])
    if n == "nor4":
        return bnot(bor(p["A"], p["B"], p["C"], p["D"]))
    if n == "nor4b":
        return bnot(bor(p["A"], p["B"], p["C"], bnot(p["D_N"])))
    if n == "or2":
        return bor(p["A"], p["B"])
    if n == "or3":
        return bor(p["A"], p["B"], p["C"])
    if n == "or3b":
        return bor(p["A"], p["B"], bnot(p["C_N"]))
    if n == "or4":
        return bor(p["A"], p["B"], p["C"], p["D"])
    if n == "or4b":
        return bor(p["A"], p["B"], p["C"], bnot(p["D_N"]))
    if n == "or4bb":
        return bor(p["A"], p["B"], bnot(p["C_N"]), bnot(p["D_N"]))
    if n == "xor2":
        return p["A"] ^ p["B"]
    if n == "xnor2":
        return 1 - (p["A"] ^ p["B"])
    if n == "mux2":
        return p["A1"] if p["S"] else p["A0"]
    if n == "a21o":
        return bor(band(p["A1"], p["A2"]), p["B1"])
    if n == "a21oi":
        return bnot(bor(band(p["A1"], p["A2"]), p["B1"]))
    if n == "a21bo":
        return bor(band(p["A1"], p["A2"]), bnot(p["B1_N"]))
    if n == "a21boi":
        return bnot(bor(band(p["A1"], p["A2"]), bnot(p["B1_N"])))
    if n == "a22o":
        return bor(band(p["A1"], p["A2"]), band(p["B1"], p["B2"]))
    if n == "a22oi":
        return bnot(bor(band(p["A1"], p["A2"]), band(p["B1"], p["B2"])))
    if n == "a31o":
        return bor(band(p["A1"], p["A2"], p["A3"]), p["B1"])
    if n == "a31oi":
        return bnot(bor(band(p["A1"], p["A2"], p["A3"]), p["B1"]))
    if n == "a32o":
        return bor(band(p["A1"], p["A2"], p["A3"]), band(p["B1"], p["B2"]))
    if n == "a211o":
        return bor(band(p["A1"], p["A2"]), p["B1"], p["C1"])
    if n == "a211oi":
        return bnot(bor(band(p["A1"], p["A2"]), p["B1"], p["C1"]))
    if n == "a2111oi":
        return bnot(bor(band(p["A1"], p["A2"]), p["B1"], p["C1"], p["D1"]))
    if n == "a221o":
        return bor(band(p["A1"], p["A2"]), band(p["B1"], p["B2"]), p["C1"])
    if n == "a221oi":
        return bnot(bor(band(p["A1"], p["A2"]), band(p["B1"], p["B2"]), p["C1"]))
    if n == "a311o":
        return bor(band(p["A1"], p["A2"], p["A3"]), p["B1"], p["C1"])
    if n == "a41oi":
        return bnot(bor(band(p["A1"], p["A2"], p["A3"], p["A4"]), p["B1"]))
    if n == "o21a":
        return band(bor(p["A1"], p["A2"]), p["B1"])
    if n == "o21ai":
        return bnot(band(bor(p["A1"], p["A2"]), p["B1"]))
    if n == "o21ba":
        return band(bor(p["A1"], p["A2"]), bnot(p["B1_N"]))
    if n == "o21bai":
        return bnot(band(bor(p["A1"], p["A2"]), bnot(p["B1_N"])))
    if n == "o22a":
        return band(bor(p["A1"], p["A2"]), bor(p["B1"], p["B2"]))
    if n == "o22ai":
        return bnot(band(bor(p["A1"], p["A2"]), bor(p["B1"], p["B2"])))
    if n == "o2bb2a":
        return band(bnot(band(p["A1_N"], p["A2_N"])), bor(p["B1"], p["B2"]))
    if n == "o211a":
        return band(bor(p["A1"], p["A2"]), p["B1"], p["C1"])
    if n == "o211ai":
        return bnot(band(bor(p["A1"], p["A2"]), p["B1"], p["C1"]))
    if n == "o221a":
        return band(bor(p["A1"], p["A2"]), bor(p["B1"], p["B2"]), p["C1"])
    if n == "o31a":
        return band(bor(p["A1"], p["A2"], p["A3"]), p["B1"])
    if n == "o31ai":
        return bnot(band(bor(p["A1"], p["A2"], p["A3"]), p["B1"]))
    if n == "o311a":
        return band(bor(p["A1"], p["A2"], p["A3"]), p["B1"], p["C1"])
    if n == "o32a":
        return band(bor(p["A1"], p["A2"], p["A3"]), bor(p["B1"], p["B2"]))
    if n == "o32ai":
        return bnot(band(bor(p["A1"], p["A2"], p["A3"]), bor(p["B1"], p["B2"])))
    if n == "diode":
        return 0
    raise KeyError(short)


class Sim:
    def __init__(self, netlist: Path) -> None:
        text = netlist.read_text(encoding="utf-8")
        self.insts: dict[str, tuple[str, dict[str, str]]] = {}
        self.drivers: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        self.flops: list[str] = []
        self.combo: list[str] = []
        self.conb: list[str] = []
        for master, inst, pins in INST_RE.findall(text):
            short = master.split("__")[-1]
            pinsd = {p: n.strip() for p, n in PIN_RE.findall(pins)}
            self.insts[inst] = (short, pinsd)
            if short.startswith(SEQ):
                self.flops.append(inst)
            elif short.startswith("conb"):
                self.conb.append(inst)
            elif not short.startswith("diode"):
                self.combo.append(inst)
            for p, n in pinsd.items():
                if p in OUT:
                    self.drivers[n].append((inst, short, p))
        self.q: dict[str, int] = {}
        self.reset()
        self._order = self._combo_order()

    def reset(self) -> None:
        for inst in self.flops:
            short = self.insts[inst][0]
            self.q[inst] = 1 if short.startswith("dfstp") else 0

    def _combo_order(self) -> list[str]:
        pending = set(self.combo)
        ready_nets = {"clk", "rst_n", "enable", "I", "success"}
        for inst in self.flops:
            ready_nets.add(self.insts[inst][1]["Q"])
        for inst in self.conb:
            pins = self.insts[inst][1]
            ready_nets.add(pins["HI"])
            ready_nets.add(pins["LO"])
        order: list[str] = []
        guard = 0
        while pending:
            progress = []
            for inst in list(pending):
                _s, pins = self.insts[inst]
                ins = [n for p, n in pins.items() if p not in OUT]
                if all(n in ready_nets for n in ins):
                    progress.append(inst)
            if not progress:
                # break cycles with remaining in arbitrary order (should not happen)
                progress = list(pending)[:1]
                guard += 1
                if guard > 50:
                    raise RuntimeError("combo has a cycle")
            for inst in progress:
                pending.remove(inst)
                order.append(inst)
                _s, pins = self.insts[inst]
                for p, n in pins.items():
                    if p in OUT:
                        ready_nets.add(n)
        return order

    def eval_combo(self, rst_n: int, enable: int, i_bit: int) -> dict[str, int]:
        nets: dict[str, int] = {
            "clk": 0,
            "rst_n": rst_n,
            "enable": enable,
            "I": i_bit,
        }
        for inst in self.flops:
            nets[self.insts[inst][1]["Q"]] = self.q[inst]
            if self.insts[inst][1].get("Q") == "success":
                nets["success"] = self.q[inst]
        for inst in self.conb:
            pins = self.insts[inst][1]
            nets[pins["HI"]] = 1
            nets[pins["LO"]] = 0
        for inst in self._order:
            short, pins = self.insts[inst]
            args = {p: nets.get(n, 0) for p, n in pins.items() if p not in OUT}
            val = FUN(short, args)
            for p, n in pins.items():
                if p in OUT:
                    nets[n] = val
        return nets

    def step(self, rst_n: int, enable: int, i_bit: int) -> dict[str, int]:
        # async reset/set
        if rst_n == 0:
            for inst in self.flops:
                short = self.insts[inst][0]
                if short.startswith("dfrtp"):
                    self.q[inst] = 0
                elif short.startswith("dfstp"):
                    self.q[inst] = 1
            nets = self.eval_combo(rst_n, enable, i_bit)
            return nets
        nets = self.eval_combo(rst_n, enable, i_bit)
        nxt = {}
        for inst in self.flops:
            dnet = self.insts[inst][1]["D"]
            nxt[inst] = nets[dnet]
        self.q.update(nxt)
        return nets


def load_stim(path: Path) -> list[tuple[int, int, int]]:
    rows = []
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        a, b, c = line.split()[:3]
        rows.append((int(a), int(b), int(c)))
    return rows


def bits_from_text(s: str, msb_first: bool = True) -> list[int]:
    out: list[int] = []
    for ch in s:
        v = ord(ch)
        bits = [(v >> i) & 1 for i in range(8)]
        if msb_first:
            bits.reverse()
        out.extend(bits)
    return out


def run_attempt(sim: Sim, payload: list[int], rst_cycles: int = 3, tail: int = 16) -> tuple[int, str]:
    sim.reset()
    chars: list[str] = []
    prev_en = 0
    collecting = False
    nchars = 0
    last_success = 0
    for _ in range(rst_cycles):
        nets = sim.step(0, 0, 0)
        last_success = nets.get("success", sim.q.get("inst28", 0))
        prev_en = 0
    for bit in payload:
        nets = sim.step(1, 1, bit)
        last_success = nets.get("success", 0)
        prev_en = 1
    for _ in range(tail):
        nets = sim.step(1, 0, 0)
        last_success = nets.get("success", 0)
        o = nets.get("O")
        if o is None:
            # reconstruct O bus
            o = 0
            for i in range(8):
                o |= nets.get(f"O[{i}]", 0) << i
        if prev_en == 1:
            collecting = True
            nchars = 0
            chars = []
        elif collecting and nchars < 16:
            chars.append(chr(o & 0xFF))
            nchars += 1
        prev_en = 0
    return last_success, "".join(chars)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netlist", default="build/puzzle_extracted.v")
    parser.add_argument("--example", default="build/puzzle_stim.txt")
    parser.add_argument("--try-text", action="append", default=[])
    args = parser.parse_args()
    sim = Sim(Path(args.netlist))
    print(f"loaded {len(sim.insts)} insts combo_order={len(sim._order)} flops={len(sim.flops)}")

    if Path(args.example).is_file():
        stim = load_stim(Path(args.example))
        sim.reset()
        saw1 = 0
        o_msg = []
        prev_en = 0
        collecting = False
        nch = 0
        for rst, en, i in stim:
            nets = sim.step(rst, en, i)
            suc = nets.get("success", 0)
            if suc:
                saw1 += 1
            o = 0
            for b in range(8):
                o |= nets.get(f"O[{b}]", 0) << b
            if prev_en == 1 and en == 0:
                collecting = True
                nch = 0
                o_msg = []
            elif collecting and nch < 9:
                o_msg.append(chr(o & 0xFF))
                nch += 1
            prev_en = en
        print(f"example: success_high_cycles={saw1} final={sim.q.get('inst28', 'n/a')} O='{''.join(o_msg)}'")

    texts = args.try_text or [
        "JANE STREET",
        "jane street",
        "Jane Street",
        "TRY AGAIN",
        "SUCCESS",
        "HARDCAML",
        "ASICPUZZLE",
        "LEAVE NO STONE UNTURNED",
        "perfect",
        "496",
    ]
    for s in texts:
        for msb in (True, False):
            for lead in ([], [0], [1]):
                payload = lead + bits_from_text(s, msb_first=msb)
                # also pad/truncate to 121 like the example
                variants = [payload]
                if len(payload) < 121:
                    variants.append(payload + [0] * (121 - len(payload)))
                    variants.append([0] * (121 - len(payload)) + payload)
                if len(payload) > 121:
                    variants.append(payload[:121])
                for v in variants:
                    suc, msg = run_attempt(sim, v)
                    if suc:
                        print(f"PASS success=1 text={s!r} msb={msb} lead={lead} nbits={len(v)} O={msg!r}")
    print("done (no success=1 printed => none of the listed texts worked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
