I have an analog IC background. I attempted this as a fun challenge, relying solely on my intuition about circuit design to come up with a strategy. I used Cursor with Grok 4.5 High extensively as the coding and brainstorming agent, but told it explicitly to respect the challenge rules. I fed it the blog post in a .md file, together with the repo. This is the original prompt, straight out from the top of my head:

"I want to come up with a plan to reverse-engineer this chip, a challenge proposed by Jane Street. The instructions for the challenge are on the blog.md and on the readme.md files. A few strategies that come to mind:

1. setup environment (can we simulate verilog and generate .vcd?). what's missing? I'm on a MacbookAir with M4 laptop.
1.1 I installed surfer for waveform viewing and klayout for gds browsing, with sky130.lyp file for the layer properties
1.2 can you browse klayout images independently, zoom in and out, and screenshot sections? what would it take to enable that?

2. learning from examples
2.1 read warmup/ directory and files, understand what they are, since they describe the step by step flow used to generate puzzle.gds. In the case of puzzle.gds, we don't have the previous files, just the final output
2.2 propose strategies to infer or reverse engineer information from the gds file based on the previous files
2.3 simulate the design, exciting its inputs with a somewhat educated guess, and reading its outputs
2.4 the gds has easter eggs like a jane street logo - ignore it

3. looking for regularity on puzzle.gds
3.1 can you parse the puzzle.gds file for a list of individual standard cells, tap cells, decoupling caps, logic gates, registers (flip flops) etc so that we have the unique list of all cells
3.2 can you identify repeating patterns on similar nets, like registering the outputs with FFs? 
3.3 can you identify the clock tree? it should be multiple inverters as repeaters starting from the clk input
3.4 can you map out the rst_b path? where does it go, from the initial pin placement?
3.5 can you map out the sucess output, going backwards?

4. lets brainstorm on high level strategies based on what you've learned from 1-3"

I've attached the full trace as well. Reverse engineering the flow was somewhat quick and did what I expected to do myself if I had to decode a small full custom mixed-signal block by hand, something I've done multiple times in the context of serializers, high-speed SAR ADCs, decoders, etc. It boils down to identifying patterns in standard cell layouts (I suggested base layers, wiring up to M1, and composite base + metal) as the pattern matching abstraction level. I had Grok write a python script to screenshot the location of each cell based on the def file and the downloaded .lyp from sky130. Later I downloaded the full sky130 library, and found out they have .svg files with the cells isolated already, so that was helpful. Most of the strategies Grok suggested were similar to what a couple of Gemini questions on the Google search bar resulted as well, so I'm interpreting that reverse engineering a .gds is somewhat of an established dark art - it feels similar to analog design in that it's based on intuition much more so than tackling the problem by brute force. 

One the flow was understood and a gate level netlist was generated, I got a bit lost to be honest, and relied 100% on the LLM and some basic prompts. I tried some parallel agents to teach myself some concepts and double check what the main agent was doing, but it seems like it was very effective staying on track and finding a solution. One thing that made sense to me and that I internalized was attempting to write all 0s and all 1s, as common "signature" patterns that might tell you something. We do this a lot in analog design, "wiggle" the inputs with different shapes and forms and see what the outputs do. I now know a little bit about two-star puzzles. This took me down a bit of a rabbit hole, but I didn't expect to fully understand the implementation, as a reverse-engineering approach with a time limit of an afternoon, I'm actually pretty impressed but not entirely suprised with the result, since it seems like LLMs are particularly good at this sort of thing. 

This was fun. I found a couple of easter eggs on the Jane Street logos on both .gds files, as well as a weird time stamp with :60 seconds on it - I guess you guys have to care about that periodically. 

Full solution and repo as finished at github.com/oscarmattia/js-asic-puzzle-2026
