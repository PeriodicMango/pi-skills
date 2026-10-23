---
name: rainmeter-skin-layout
description: "Build and change the layout of data-driven Rainmeter skins safely - keep all pixel arithmetic in a backend, generate the .ini from a constant table instead of hand-editing it, and verify with a checker plus a window capture. Covers the WebParser capture-group limit, the lack of a scrolling container, refresh commands that wedge WebParser, UTF-16 ini encoding, and the anchoring and font-metric mistakes that keep recurring. Use when creating or restyling a Rainmeter skin whose content comes from an API or a file, when a skin ini has to be edited at all, or when a skin's geometry, fonts, spacing or block rendering needs to change."
---

# Data-driven Rainmeter skins

For a skin whose content changes (calendar, task list, timeline, dashboard), the workable
architecture is counter-intuitive: **put almost nothing in the skin.** A backend computes
every position and the skin only draws. This document is the set of constraints that shape
that design, most of which are only discoverable by hitting them.

`examples/minimal/` is a complete, runnable instance of everything below: a generator, a
checker, a sample payload, and no external dependencies.

## Rule 1 — generate the ini, never hand-edit it

The generated part of a skin is one template repeated per row and per column. A hand edit
lands on one copy and misses the others, and the failure is *silent*: one row reads another
row's value, or one hour label sits two pixels off, and nobody notices for a week.

A generator has three parts, and the third is the one people skip:

1. **A constant table at the top.** Every number that decides layout lives here and nowhere
   else.
2. **Derivation.** Grid lines, label positions, canvas size and the capture regex are all
   computed from the constants, so they cannot drift apart.
3. **A checker that re-derives them independently and reads the generated file back.** See
   "What a checker must verify" below. A generator alone gives you a fast way to be
   consistently wrong.

## Rule 2 — all pixel arithmetic in the backend

The skin has a fixed number of **slots**. Each slot is a shape plus a text meter, and every
option is bound to a measure:

```
[Slot1]
Meter=Shape
DynamicVariables=1
Shape=Rectangle [MeasureRect1] | Fill Color [MeasureRGB1],55 | Stroke Color [MeasureRGB1],255

[SlotText1]
Meter=String
DynamicVariables=1
MeasureName=MeasureText1
W=[MeasureTW1]
X=[MeasureTX1]
Y=[MeasureTY1]
```

The syntax fact this rests on: **`[MeasureName]` in any option position expands to that
measure's string value** — including `X=`, `Y=`, `W=` and `Shape=` — provided the meter sets
`DynamicVariables=1`. Without that, dynamic geometry is not expressible.

What this buys you: overlap handling (splitting colliding items into columns), converting a
duration into pixels, deciding whether an item is above or below the visible window, and
clipping to the window, all happen in a real language with a debugger. The skin never
computes anything.

Two consequences worth keeping:

- **Emit `rgb` as three channels and append alpha in the ini** (`Fill Color [MeasureRGB1],55`
  vs `Stroke Color [MeasureRGB1],255`). One capture group serves both fill and stroke, and
  the group budget is the binding constraint (next section).
- **Hide a slot by drawing it off-canvas** (`-100,-100,1,1`) rather than at zero size.
  Zero-size shapes behave inconsistently; off-canvas ones cannot be seen or hit.

## The capture-group budget

A single WebParser parent measure allows **99 `StringIndex` values**. That is the hard
ceiling, and it determines the entire field layout, so count before designing.

Every field you want from the backend is one capture group:

```
(?siU)(.*)\n(.*)\n ... labels ... \n(.*)\|(.*)\|(.*)\|(.*)\|(.*)\|(.*)\n ...
```

Three details that are cheap to get right and expensive to debug:

- **Escape the intra-row separator** (`\|`). A bare `|` is regex alternation, which turns the
  six fields into one optional branch and silently changes the group count.
- **The inline flags matter.** `s` lets `.` cross newlines; `U` (PCRE ungreedy) makes the
  repeated `(.*)` consume as little as possible, which is what keeps fields from swallowing
  each other. Without `U` the first group eats the document.
- **Match the trailing newline** if the backend emits one, or the last field goes missing.

When the budget runs out, the answer is a **second parent measure with its own 99 groups**
— not clever chaining. Chaining `URL=[OtherMeasure]` off an existing parent to save requests
is a documented-looking optimisation that once made every day after the 10th of the month
disappear from a calendar. Pay the extra request.

Python's `re` has no ungreedy flag, so a checker that re-parses a sample payload in Python
must translate `(?siU)` to `(?si)` **and** `(.*)` to `(.*?)`. Getting only the first half
right produces a checker that passes on wrong data.

## Hard limits, all verified by hitting them

- **There is no scrolling container.** Rainmeter sizes the skin to the union of its meters
  and has no clipping viewport, so a "scrolled" element is still drawn — over the header and
  outside the plate. Scrolling therefore has to be implemented as *changing which range the
  fixed rows represent*: the backend emits the labels and only the in-window items, and the
  grid never moves. (There is a `Container` option for clipping, but it interacts with
  dynamic geometry in ways worth testing in isolation before committing to it.)
- **`!UpdateMeasure` does not re-download a WebParser.** Use
  `!CommandMeasure <Measure> Update`. Conversely, a refresh command aimed at a measure that
  is already downloading is **discarded**, so having several data measures means dropped
  input while a user is interacting. One data measure per widget is faster, not just tidier.
- **`!RefreshApp` (or refreshing repeatedly) can wedge WebParser.** The symptom is every
  endpoint's request rate halving and then going to zero, presented as "all text vanished and
  the buttons stopped responding" — which reads like a logic bug. Recovery requires quitting
  the Rainmeter process entirely; refreshing a skin does not help. Refresh one skin, once.
- **`Update` and `UpdateRate` are coupled.** `UpdateRate` counts `Update` ticks. Setting
  `Update=1000` → `200` turned a 30-second poll into 6 seconds until `UpdateRate` was scaled
  too. Static meters should carry `UpdateDivider=-1` so they stop recomputing.
- **A skin ini containing non-ASCII must be UTF-16LE with a BOM**, or the glyphs come out
  mangled.
- **`StrokeColor` and `Stroke Color` are equivalent.** Shape modifier parsing is prefix
  matching, so a missing space never matters (`FillColor 255,0,0` works as well). Do not
  "fix" it, and note that `StrokeWidth`, `StrokeDashes`, `StrokeDashCap` and `StrokeEndCap`
  are documented without a space in the first place.
- **Mouse events only fire on drawn pixels.** An empty String meter is not clickable, so give
  it placeholder text or hang the action on a shape that is actually painted.
- **Layer order is file order** — later sections draw on top. Error text and buttons must be
  placed after any panel they need to appear over.

## Change protocol

1. Edit the constant table, not the ini.
2. Regenerate and **run the checker**, and only deploy if it passes.
3. Back up whatever is being replaced.
4. Deploy, then verify the copy landed (compare a checksum).
5. Refresh that one skin — never `!RefreshApp`.
6. **Verify by capturing the window and measuring pixels**, not by asking someone to look.
   Calibrate the image-to-window mapping from a feature whose coordinates you know (a
   program's own grid line, a status colour); never from an assumption about padding.
   Guessing an offset has produced a confident, completely false finding. If you have the
   `desktop-view` skill available, it captures a window through PrintWindow, which works even
   when the window is occluded or off-screen.

## What a checker must verify

Ordered by how expensive the corresponding bug is:

1. **Every `StringIndex` used exactly once, covering `1..N` with no gaps and nothing above
   the capture-group count.** Not "≤ limit" — *covering*. An off-by-one that pushes the last
   rows past the end of the pattern is otherwise invisible.
2. **Row N references only row N's measures.** A checker that only verifies "the sections I
   reference exist" passes happily while row 10 reads row 1's value. Check both directions:
   the shape's rect and colour references, and every `W`/`X`/`Y` of the text meter.
3. **Derived geometry reconstructs.** Grid line positions, label offsets and the canvas
   anchor must come out of the constants, so a stray hand-edit is caught.
4. **Budget and encoding**: group count within the limit, UTF-16LE + BOM, LF, unique section
   names, every referenced section present.
5. **Divisibility constraints** that make the grid land correctly — e.g. the timeline height
   must divide evenly into whole hours, asserted in the generator so it cannot break quietly.
6. **A sample payload parses into exactly `N` groups**, which catches regex/group-count
   mismatches that static checks cannot.

Implementing the checker is not enough; **verify the checker**. Break each thing it claims to
catch (duplicate an index, point row 2 at row 1, delete a group, nudge a grid line) and
confirm it fails. A checker whose failure paths are untested is worse than none, because it
buys confidence it has not earned.

One trap while writing it: when splitting an ini into sections, strip comment lines from each
body first. A comment written above a `[Section]` header belongs to the *previous* section in
a naive split, so a comment mentioning `!CommandMeasure` registers as a measure reference and
produces a false failure. That happened for real.

## Layout judgement calls that keep coming back

- **Font metrics are measured, not guessed.** A String meter's `Y` is the top of the text
  box, not the top of the ink. For Segoe UI at FontSize 10, the ink starts about 3px below
  `Y` and is about 10px tall. Keep those numbers as named constants next to the offsets they
  justify, note how they were measured, and re-measure when the font size changes. Pixel
  measurement is the only way to get them.
- **When two elements compete for the same vertical space, anchor the one that must not
  collide to the one it must not collide with.** A banner positioned by an absolute `y`
  consumed the first row label's ink *every time* it was enlarged. Deriving its position from
  the label instead (`y = timeline_top - label_ink_offset - gap - height`) made the collision
  structurally impossible rather than fixed by luck. **If you find yourself re-tuning the
  same number twice, the anchoring is wrong, not the number.**
- **"Make the padding bigger" is ambiguous — ask which one**: inside the box, or the gap
  between boxes. Guessing costs a whole round trip.
- **Two lines of text in one slot** cannot use extra capture groups when the budget is full.
  The approach that fits: put a sentinel byte in one field (something that cannot appear in
  the content, e.g. `U+001F`), set `RegExpSubstitute=1` with `Substitute="\x1f":"#CRLF#"` on
  the meter, then style the second line in place with `InlineSetting` / `InlinePattern`
  (`InlineSetting=Size | 9`, `InlineSetting2=Color | 150,150,150`). **Caveat:** the docs
  describe inline formatting as applying to the final displayed string and `Substitute` as a
  measure option, which implies InlinePattern runs *after* substitution — but no sentence
  says so. Verify visually before relying on it. The fallback is a second text meter with
  `Y=([MeasureTY1]+offset)`, which is documented to work and needs `DynamicVariables=1`.
  Formulas must be entirely wrapped in parentheses, and are not allowed in a `Text` option.

## Primary sources

Worth reading rather than re-deriving:

- String meter inline formatting — <https://docs.rainmeter.net/manual/meters/string/inline/>
- Formulas in option values — <https://docs.rainmeter.net/manual/formulas/>
- Substitute / RegExpSubstitute — <https://docs.rainmeter.net/manual/measures/general-options/substitute/>
- Built-in variables, including `#CRLF#` — <https://docs.rainmeter.net/manual/variables/built-in-variables/>
- WebParser tutorial, including what `s` does to `.` — <https://docs.rainmeter.net/tips/webparser-tutorial/>

## Performance, if the widget polls

- Cache the upstream data once and share it across every endpoint, with a lock plus a
  double-check so a cache expiry under a threading HTTP server does not stampede into N
  simultaneous upstream fetches. Serve expired-but-present data immediately and refresh in
  the background, so no request pays the cold-cache cost. Bust the cache on writes.
- **Measure before optimising.** Two rounds of plausible-sounding optimisation did nothing;
  what found the real cause was adding request timing to the backend and reading the arrival
  timestamps. Never change code for a "slow" report without data first.
- Check the machine's load before benchmarking, and make sure it is not your own doing.
