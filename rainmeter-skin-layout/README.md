# rainmeter-skin-layout

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-green)
![Rainmeter](https://img.shields.io/badge/Rainmeter-skin-orange)

English | [简体中文](README.zh-CN.md)

A [pi](https://github.com/earendil-works/pi) skill for building and reshaping **data-driven
Rainmeter skins** — the kind whose content comes from an API or a file (a calendar, a task
list, a timeline) rather than being fixed at author time.

The value here is not a template. It is a list of constraints that are only discoverable by
hitting them: the 99-capture-group ceiling on a WebParser measure, the fact that a skin has
no scrolling container so "scrolling" has to be redefined, refresh commands that wedge
WebParser until you restart the whole process, a coupled `Update`/`UpdateRate`, and an ini
encoding requirement that mangles every glyph if you get it wrong.

## The two rules

1. **Generate the ini, never hand-edit it.** The repeated sections are one template applied
   N times; a hand edit silently misses the other N−1 copies.
2. **Keep all pixel arithmetic in a backend.** The skin has fixed "slots" whose every option
   is bound to a measure, and the backend decides where things go. Overlap handling,
   duration-to-pixel conversion and clipping then live somewhere you can debug.

## Install

```bash
./install.sh rainmeter-skin-layout   # from the pi-skills repo root
```

To install by hand, copy this directory into `~/.pi/agent/skills/rainmeter-skin-layout`.

Pi scans its skills directory at startup, so a **new session** picks it up; you can also
force it with `/skill:rainmeter-skin-layout`. Nothing else to configure — the skill is
documentation plus a runnable example, with no dependency on any particular machine.

## The example

`examples/minimal/` is a complete, self-contained instance of the pattern — about 480 lines
of Python, no external dependencies:

```bash
cd examples/minimal
python3 layout.py -o Minimal.ini     # generate the skin
python3 check.py Minimal.ini --demo  # verify it; parse the sample payload
```

It is deliberately small (one column, 8 hours, 3 slots) but it exercises every part that
matters: a repeated template, a capture-group budget with an assert, a divisibility
constraint, geometry that has to be re-derivable from constants, and a payload that has to
parse into exactly the expected number of groups.

## What is actually hard here

Most of the difficulty is not Rainmeter syntax. It is that **a layout bug is silent**. Text
that reads another row's value, a grid line two pixels off, a label whose ink is covered by
the element above it — none of these throw. They just look slightly wrong, and you find out
when a human notices.

So the skill spends most of its length on two things: which constraints are hard limits, and
how to build a checker that re-derives the layout from the constants instead of re-reading
the file. The example's checker catches, among others:

- a `StringIndex` used twice, or one pointing past the end of the pattern
- a slot referencing its neighbour's measure
- a grid line not at its derived position
- a canvas size that no longer equals the plate plus its inset

A checklist item in the skill: **verify the checker** by breaking each of those on purpose.
A checker whose failure paths have never executed buys confidence it has not earned.

## Related

The companion skill **desktop-view** captures a single window's pixels over ssh, including
when it is occluded or off-screen. The final step of the change protocol here is "verify by
capturing the window and measuring pixels", and that skill is how you get the capture.

## License

MIT — see [LICENSE](LICENSE).
