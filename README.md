# ASIC Reverse-Engineering Puzzle

This repository provides the files for the Jane Street ASIC reverse-engineering puzzle! See the [blog post](https://blog.janestreet.com/can-you-reverse-engineer-an-asic/) for more details.

### Puzzle GDS

The puzzle GDS is in this repository, in the file named `puzzle.gds`. You can preview it using [KLayout](https://www.klayout.de/) or the [TinyTapeout Online GDS Viewer](https://gds-viewer.tinytapeout.com/).

See `example_inputs.vcd` which shows some inputs being fed to the design (unfortunately, not the correct inputs to make `success` go high!). You can view it using [Surfer](https://surfer-project.org/) or a similar tool.

To help you get started, below is an image with some hints. The region labelled as "output generator" is safe to ignore during your initial reverse-engineering steps, but you'll need to simulate it to get your final answer!

![](layout.png)

### Warm-up Puzzle

To familiarize yourself with the flow and help develop your tools, we've put together a small example design and run it through a very similar flow to the one used for the real thing! The example design consists of two shift registers, an adder, and a comparator, outputting success if `A + B == 496`.

You'll find the following files related to the warm-up puzzle:

- `warmup/00_source.v`: The original Verilog source code of the example design
- `warmup/01_netlist.v`: Synthesized netlist comprising of a list of standard cells
  and connections
- `warmup/02_netlist_with_power_rails.v`: Netlist with VDD and GND rails added
- `warmup/03_post_place_and_route.def`: Physical layout of cells and routing
  connections, corresponding to cell and net names.
- `warmup/04_final.gds`: The final manufacturable layout file, with many internal names
  removed

---

## Retrospective: reverse-engineering this ASIC (AI-assisted, one afternoon)

I come from an analog / mixed-signal (AMS) IC design background and attempted this as
a personal challenge, with no prior experience in digital reverse-engineering or GDS
extraction. The strategy was my own — driven by full-custom layout intuition — and
an LLM coding agent (Cursor + Grok) did the scripting and the bulk of the
combinatorial puzzle-solving. I kept to the spirit of the challenge: AI was used for
tooling, the warm-up, and search scripts, **not** for pasting `puzzle.gds` geometry
into a chat window or for writing the final answer.

The full toolchain is in `tools/`; the running log is in `history.md`; the personal
narrative is in `writeup.md`; complete agent transcripts are in `traces.md`.

### Final result

`success=1` reached in Icarus at cycle 125 on an extracted-from-GDS netlist. The
circuit is a **Star Battle** ("two stars") puzzle over an 11×11 grid: a MUX-ROM
labels each (bit-time, round) cell with a region, and the datapath enforces exactly
two ones per row, per column, per region, and no two ones king-adjacent. Solving that
constraint problem and streaming the solution back in as the serial input raises
`success`. The output generator then prints `(* TWO STARS *)`.

### What worked well

- **Warm-up first, as a test fixture.** The warm-up ships the same OpenROAD / sky130
  flow with names still attached at every stage. Building the GDS→Verilog extractor
  and the simulation harness against that ground truth (extractor scored 5/5 on the
  warm-up) meant every tool was validated before it touched the real puzzle.
- **Standard-cell pattern matching as the abstraction level.** Treating the problem
  as "recognize repeated base-layer + up-to-M1 fingerprints" is exactly how you decode
  a hand-drawn full-custom block. Scripting per-cell layout screenshots from the DEF +
  sky130 `.lyp` (`tools/screenshot_cells.py`), then discovering sky130 ships isolated
  per-cell SVGs, made cell identification mechanical.
- **Programmatic extraction with KLayout's Python API.** `tools/extract_lib.py` /
  `extract_netlist.py` walk the hierarchy, union routing shapes into nets, clip LEF
  pin PORTs to via landings, and emit Verilog: 738 instances / 67 cell types, all
  ports resolved, zero multi-driven nets.
- **Icarus as the single source of truth.** sky130 `FUNCTIONAL` + `UNIT_DELAY` cell
  models in Icarus were the acceptance oracle. A fast hand-written Python model was
  useful for triage but was explicitly never trusted for a `success=1` claim without
  an Icarus confirm — and it did produce false positives.
- **Negative-test discipline.** The provided `example_inputs.vcd` is a known *failing*
  vector. The harness was built to pass only on `success===1`, and the failing path
  was re-checked after every netlist change so a "fix" couldn't quietly break it.
- **Protocol recovery from counters + the example waveform.** Reading the bit counter
  (period 11), round counter, and lock logic off the netlist showed each attempt is
  exactly **121 bits**, not 2¹²¹ — which killed the brute-force idea on day one.
- **"Wiggle the inputs."** All-zeros / all-ones signature vectors — standard analog
  bring-up practice — exposed the canned output banners (`EMPTY SKY`, `BIG BANG`,
  `TRY AGAIN`) and helped bound what the `success` cone actually depends on.
- **Layout-as-hint paid off.** A placement screenshot against the labeled `layout.png`
  cleanly separated the `success` cone (center spine + bottom-right XOR/MUX cluster)
  from the output generator (faded top-right), which could then be ignored until the
  end, exactly as the puzzle promised.
- **Physical reasoning about extraction artifacts.** Three combinational nets came out
  undriven because of via-clipping. Each was resolved by looking at the geometry
  (`n_362` is an output-generator MUX hold pin = `inst252.Q`; `n_721` genuinely has no
  driver on that pin) rather than by guessing a convenient logic function.
- **Cross-checking the agent.** Throwaway parallel agents and quick web-search queries
  independently converged on the same GDS-RE techniques, which raised confidence that
  the main agent wasn't wandering.

### What didn't work, and what it cost

- **Domain intuition ran out at the gate-level netlist.** Everything up to a clean
  netlist mapped onto analog experience. The constraint-satisfaction phase
  (Star Battle, 11×11 2-factor search) did not, and I leaned almost entirely on the
  LLM there. It got the answer; it did not leave me with deep understanding.
- **The `n_721` rabbit hole.** An early guess that the undriven pin was `~inst468.Q`
  looked plausible, corrupted one ROM row, split the puzzle regions, and *forced a
  fake netlist patch* to make the search converge. It was only retired once the
  geometry was taken seriously. Lesson: **a search that only succeeds with an
  unexplained netlist edit is a red flag, not a result.**
- **KLayout API surprises.** `db.Region(RecursiveShapeIterator)` silently ignores
  `max_depth`; the hierarchy had to be walked by hand. Full power straps in the LEF
  short neighboring signal pins unless PORTs are clipped to via landings.
- **Brute force didn't scale even at 121 bits.** Enumerating the full "two ones per
  row" set blew 24 GB of RAM. The search had to be streamed and `--limit`-capped.
- **Fast-model vs. Icarus mismatches** cost debugging time — the Python model reported
  `success=1` on vectors Icarus rejected.
- **Stale build artifacts.** A compiled `vvp` could be silently reused against a new
  netlist; the fix was to stamp the netlist path into the artifact.
- **Almost stopped one bug short of the real answer.** With `n_362` left tied to 0,
  `success=1` but the recovered output string was garbage. The final answer only
  appeared after repairing that one via-clipped hold pin — it would have been easy to
  declare victory at `success=1` and report the wrong string.
- **Parallel self-teaching agents had mixed value.** The main agent stayed on track
  well on its own; the side agents were more for my understanding than for progress.

### Takeaways for AI-assisted IC work

- LLM agents are strong force-multipliers for the *mechanical* layers of RE —
  environment setup, GDS parsing, netlist emission, simulation plumbing, and
  well-posed combinatorial search — especially when there is a labeled warm-up to
  validate against.
- Domain judgment stays on the critical path for *framing* the problem (what
  abstraction level, which block to ignore, what a signature vector should be) and as
  the *safeguard* against confident-but-wrong results (unexplained patches, fast-model
  false positives, "success but garbage output").
- A ground-truth fixture and a strict acceptance oracle are what make it safe to let
  an agent iterate quickly.
