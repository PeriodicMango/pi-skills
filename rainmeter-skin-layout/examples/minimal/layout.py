#!/usr/bin/env python3
"""Generator for a minimal data-driven Rainmeter timeline skin.

    python3 layout.py -o Minimal.ini      write the skin (UTF-16LE + BOM, LF)
    python3 layout.py --regex             print only the WebParser RegExp
    python3 layout.py --shape             print the wire format the backend must produce

Why the skin is generated instead of hand-written: the sections are the same template
repeated once per slot and once per hour, and a hand edit lands on one copy and misses the
others. The failure is silent - one row behaves differently and nobody notices for a week.
Here one constant table produces every repeated section, and the checker re-derives them
independently.

THE ARCHITECTURE THIS DEMONSTRATES

    All pixel arithmetic happens in the backend. Python computes absolute x,y,w,h and the
    text position; the skin has a fixed number of "slots" whose every option is bound to a
    measure. That puts overlap handling, duration-to-pixels conversion and clipping in a
    language with a debugger, and leaves Rainmeter doing only what it is good at: drawing.

    The one syntax fact this rests on: [MeasureName] in any option position - X=, Y=, W=,
    even Shape= - expands to that measure's string value, provided the meter sets
    DynamicVariables=1.
"""
import argparse
import sys

# ============================================================================
# Constants. This table is the whole layout. Everything below derives from it.
# ============================================================================
PLATE_X, PLATE_Y = 14, 14          # plate inset inside the canvas
PLATE_W, PLATE_H = 372, 600        # plate size
PLATE_RADIUS = 10

LABEL_RIGHT = 52                   # hour labels are right-aligned so their ink ends here
LABEL_DY = -6                      # hour label Y, relative to its grid line
T0 = 40                            # y of the first grid line (= first hour of the window)
WINDOW_H = 8                       # how many hours fit on screen at once
HOUR_PX = (PLATE_H - T0) // WINDOW_H
assert (PLATE_H - T0) % WINDOW_H == 0, \
    "the timeline must divide evenly into whole hours, or the last grid line will not land " \
    "on the plate edge"

GRID_X = 54                        # grid lines start here
GRID_W = PLATE_W - GRID_X - 14     # and end 14px before the plate's right edge
AREA_X = GRID_X + 4                # blocks start 4px right of the grid, so the grid reads
AREA_W = PLATE_W - AREA_X - 14     # as a rail rather than as the block's own left edge
BLOCK_RADIUS = 4
BLOCK_FILL_ALPHA = 55              # fill is translucent, stroke is solid

SLOTS = 3                          # how many items can be drawn at once
FIELDS_PER_SLOT = 6                # rect | rgb | text-x | text-y | text-w | text
HEAD_FIELDS = 2                    # header text, "now" line rect
WEBPARSER_MAX_GROUPS = 99          # hard limit: StringIndex values on one WebParser measure

CANVAS_W = PLATE_X * 2 + PLATE_W
CANVAS_H = PLATE_Y * 2 + PLATE_H

GROUP_COUNT = HEAD_FIELDS + WINDOW_H + SLOTS * FIELDS_PER_SLOT

FONT = "#FontName#"
VERSION = "1.0"

# Fail loudly at generate time rather than producing a skin that silently stops working.
assert GROUP_COUNT <= WEBPARSER_MAX_GROUPS, \
    "capture-group budget blown: %d needed, %d allowed on one WebParser measure. Fold fields " \
    "together (rgb as three channels, alpha appended in the ini) or split across two parent " \
    "measures." % (GROUP_COUNT, WEBPARSER_MAX_GROUPS)


def build_regex():
    """The capture pattern, derived from the same constants as the measures below.

    Every field is captured on its own line except the slot fields, which share a line
    separated by a literal pipe. Two details that are easy to get wrong and expensive to
    debug:
      * the pipe inside a slot must be escaped (\\|). A bare | is regex alternation, which
        collapses the six fields into one optional branch and silently changes the group
        count.
      * the inline (?siU) flags matter: s lets . match across newlines, U makes the repeated
        (.*) consume as little as possible so fields do not bleed into each other.
    """
    lines = ["(.*)"] * HEAD_FIELDS
    lines += ["(.*)"] * WINDOW_H
    lines += [r"\|".join(["(.*)"] * FIELDS_PER_SLOT)] * SLOTS
    return r"(?siU)" + r"\n".join(lines) + r"\n"


def wire_format():
    """What the backend has to produce, in order, one field per line."""
    out = ["<header text>", "<now-line rect: x,y,w,h  (or -100,-100,1,1 to hide it)>"]
    out += ["<hour label %d>" % (i + 1) for i in range(WINDOW_H)]
    for i in range(SLOTS):
        out.append("<slot %d: rect | r,g,b | text-x | text-y | text-w | text>" % (i + 1))
        if i == 0:
            out.append("          rect is x,y,w,h[,radius]; the radius is optional "
                       "(Rainmeter defaults to square corners)")
    out.append("<trailing newline required: the pattern ends with \\n>")
    return "\n".join(out)


def build():
    S = []
    a = S.append

    a("[Rainmeter]")
    a("Update=1000")
    a("AccurateText=1")
    a("")

    a("[Metadata]")
    a("Name=Minimal Timeline")
    a("Version=" + VERSION)
    a("Information=Generated by layout.py. Edit the constants there, not this file.")
    a("")

    a("[Variables]")
    a("FeedUrl=http://127.0.0.1:8080/timeline")
    a("FontName=Segoe UI")
    a("")

    a("; One data measure for the whole widget. Fewer measures in flight is not just tidier:")
    a("; a refresh command aimed at a measure that is already downloading is discarded, so")
    a("; more measures means more dropped input while the user is interacting.")
    a("; %d groups = %d head + %d labels + %d slots x %d fields (limit %d)."
      % (GROUP_COUNT, HEAD_FIELDS, WINDOW_H, SLOTS, FIELDS_PER_SLOT, WEBPARSER_MAX_GROUPS))
    a("[MeasureData]")
    a("Measure=WebParser")
    a("URL=#FeedUrl#")
    a("RegExp=" + build_regex())
    a("UpdateRate=30")
    a("Flags=ForceReload")
    a("FinishAction=[!UpdateMeterGroup Live][!Redraw]")
    a("")

    idx = 1

    def measure(name, comment=None):
        nonlocal idx
        if comment:
            a("; " + comment)
        a("[%s]" % name)
        a("Measure=WebParser")
        a("URL=[MeasureData]")
        a("StringIndex=%d" % idx)
        a("")
        idx += 1

    measure("MeasureHeader")
    measure("MeasureNowRect")
    for i in range(WINDOW_H):
        measure("MeasureLabel%d" % (i + 1), comment="hour labels" if i == 0 else None)
    for i in range(SLOTS):
        n = i + 1
        if i == 0:
            a("; One group of measures per slot. rect is an absolute x,y,w,h,radius in canvas")
            a("; coordinates, so the same slot can draw anywhere - the backend decides, not the skin.")
        measure("MeasureRect%d" % n)
        measure("MeasureRGB%d" % n)
        measure("MeasureTX%d" % n)
        measure("MeasureTY%d" % n)
        measure("MeasureTW%d" % n)
        measure("MeasureText%d" % n)

    a("; Static meters never change, so stop recomputing them every update.")
    a("[Plate]")
    a("Meter=Shape")
    a("UpdateDivider=-1")
    a("Shape=Rectangle %d,%d,%d,%d,%d | Fill Color 12,12,14,220 | StrokeWidth 0"
      % (PLATE_X, PLATE_Y, PLATE_W, PLATE_H, PLATE_RADIUS))
    a("")

    a("[Grid]")
    a("Meter=Shape")
    a("UpdateDivider=-1")
    for k in range(WINDOW_H + 1):
        y = T0 + k * HOUR_PX
        alpha = 34 if k in (0, WINDOW_H) else 16
        key = "Shape" if k == 0 else "Shape%d" % (k + 1)
        a("%s=Rectangle %d,%d,%d,1 | Fill Color 255,255,255,%d | StrokeWidth 0"
          % (key, GRID_X, y, GRID_W, alpha))
    a("")

    a("; Group=Live is refreshed by the data measure's FinishAction, so a value that has just")
    a("; arrived is drawn immediately instead of waiting for the next skin update.")
    for i in range(WINDOW_H):
        a("[Hour%d]" % (i + 1))
        a("Meter=String")
        a("Group=Live")
        a("MeasureName=MeasureLabel%d" % (i + 1))
        a("FontFace=" + FONT)
        a("FontSize=9")
        a("FontColor=255,255,255,110")
        a("StringAlign=Right")
        a("AntiAlias=1")
        a("X=%d" % LABEL_RIGHT)
        a("Y=%d" % (T0 + i * HOUR_PX + LABEL_DY))
        a("")

    a("[Header]")
    a("Meter=String")
    a("Group=Live")
    a("MeasureName=MeasureHeader")
    a("FontFace=" + FONT)
    a("FontSize=13")
    a("FontColor=255,255,255,235")
    a("StringStyle=Bold")
    a("AntiAlias=1")
    a("ClipString=1")
    a("W=%d" % (PLATE_W - 28))
    a("X=%d" % (PLATE_X + 14))
    a("Y=%d" % (PLATE_Y + 6))
    a("")

    a("; rgb arrives as three channels and the alpha is appended here, which saves one capture")
    a("; group per slot - worth doing, because the group budget is the binding constraint.")
    for i in range(SLOTS):
        n = i + 1
        a("[Slot%d]" % n)
        a("Meter=Shape")
        a("Group=Live")
        a("DynamicVariables=1")
        a("Shape=Rectangle [MeasureRect%d] | Fill Color [MeasureRGB%d],%d | StrokeWidth 1 "
          "| Stroke Color [MeasureRGB%d],255" % (n, n, BLOCK_FILL_ALPHA, n))
        a("")

    for i in range(SLOTS):
        n = i + 1
        a("[SlotText%d]" % n)
        a("Meter=String")
        a("Group=Live")
        a("MeasureName=MeasureText%d" % n)
        a("DynamicVariables=1")
        a("FontFace=" + FONT)
        a("FontSize=10")
        a("FontColor=240,240,240,255")
        a("StringAlign=Left")
        a("ClipString=1")
        a("AntiAlias=1")
        a("W=[MeasureTW%d]" % n)
        a("X=[MeasureTX%d]" % n)
        a("Y=[MeasureTY%d]" % n)
        a("")

    a("[NowLine]")
    a("Meter=Shape")
    a("Group=Live")
    a("DynamicVariables=1")
    a("Shape=Rectangle [MeasureNowRect] | Fill Color 235,85,85,230 | StrokeWidth 0")
    a("")

    a("; An invisible 1x1 shape at the canvas corner. Rainmeter sizes the skin to the union of")
    a("; its meters, so this is what fixes the skin size when everything else is dynamic.")
    a("[CanvasAnchor]")
    a("Meter=Shape")
    a("UpdateDivider=-1")
    a("Shape=Rectangle %d,%d,1,1 | Fill Color 0,0,0,0 | StrokeWidth 0" % (CANVAS_W, CANVAS_H))

    return "\n".join(S) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", help="write the skin here (UTF-16LE + BOM)")
    ap.add_argument("--regex", action="store_true", help="print the RegExp only")
    ap.add_argument("--shape", action="store_true", help="print the wire format only")
    args = ap.parse_args()

    if args.regex:
        print(build_regex())
        return
    if args.shape:
        print(wire_format())
        return

    text = build()
    if args.out:
        # UTF-16LE with a BOM: required as soon as the skin contains a non-ASCII glyph.
        with open(args.out, "wb") as f:
            f.write(b"\xff\xfe" + text.encode("utf-16-le"))
        print("wrote %s (%d groups, %d chars)" % (args.out, GROUP_COUNT, len(text)))
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
