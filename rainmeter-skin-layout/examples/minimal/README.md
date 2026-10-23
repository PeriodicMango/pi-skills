# Minimal timeline — a self-contained example

Everything the skill describes, in about 480 lines of Python, with no dependency on anything
outside this directory. Run it, break it, read it.

```bash
python3 layout.py -o Minimal.ini     # generate the skin (UTF-16LE + BOM, LF)
python3 check.py Minimal.ini --demo  # verify it, and parse sample-data.txt with its regex
python3 layout.py --shape            # print the wire format the backend must produce
python3 layout.py --regex            # print only the generated WebParser pattern
```

`check.py` should end with `all checks passed`. If it does not, that is the point of the
example — read the failing line and look at what it re-derived.

## Files

| file | what |
|---|---|
| `layout.py` | the constant table, the derivation, and the generator (287 lines) |
| `check.py` | the four verification layers, reading the generated file back (196 lines) |
| `sample-data.txt` | an example backend response, parsed by `check.py --demo` |
| `Minimal.ini` | generated output (regenerate it; do not edit it by hand) |

## The shape of it

A single-column, 8-hour timeline with 3 slots. That is small enough to hold in your head and
still exercises every part of the pattern: a repeated template, a capture-group budget, a
divisibility constraint, geometry that must be re-derivable, and a payload that must parse.

The wire format (`layout.py --shape`) is one field per line, with the slot fields piped
together on one line:

```
<header text>
<now-line rect: x,y,w,h  (or -100,-100,1,1 to hide it)>
<hour label 1>
...
<slot 1: rect | r,g,b | text-x | text-y | text-w | text>
...
```

Point `FeedUrl` in the generated `[Variables]` at whatever serves that text and it is a
working skin.

## The three things to take from it

1. **The constants are the layout.** `T0`, `WINDOW_H`, `PLATE_H`, `GRID_X`, `SLOTS`,
   `FIELDS_PER_SLOT` — change one and rerun; grid lines, label positions, the canvas anchor
   and the regex all move together. There is not a single hardcoded coordinate below the
   constant block.
2. **The budget is an assert, not a comment.** `GROUP_COUNT` is computed from the constants
   and asserted against the 99-group WebParser limit at generate time, so a field added in
   six months fails loudly instead of producing a skin that quietly stops updating.
3. **The checker re-derives rather than re-reads.** It does not ask "does this look right" —
   it recomputes every expected number from `layout.py` and compares. Which is why it can
   catch a duplicated `StringIndex`, a slot referencing its neighbour's measure, a grid line
   nudged by 3px, or a canvas that no longer equals the plate plus its inset.

Worth doing once: break each of those on purpose and confirm `check.py` fails. A checker
whose failure paths have never run is not a checker.
