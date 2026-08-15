The puzzle
We’ve designed an ASIC, and we’re giving you its final mask: all of its metal, routing, and active transistor layers, along with some sample inputs and outputs.

Your job is to reverse engineer it. First, recover a netlist from the layout. Then figure out the circuit’s true purpose. And then comes the puzzle within the puzzle: once you understand what the chip does, use it to tease out the output it’s looking for, and find the string value that’s your final answer.

Some pointers for getting started:

The circuit is physically arranged to hint at its functionality, so look closely at the layout!
There is one section of the design that is used to generate the output but does not affect the [success] output. You can safely ignore it for the initial reverse-engineering steps.
You’ll need to come up with a way to simulate the underlying circuit to test your solution and get the final output!
You’ll know you have the correct solution when the [success] output signal goes high. Don’t forget to toggle [rst_n] before each input attempt.
We hid a few fun Easter eggs in the circuit and in the repository (including in parts you don’t need to look at to solve the main puzzle), see if you can spot them once you’re done with the puzzle.