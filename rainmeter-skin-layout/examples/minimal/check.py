#!/usr/bin/env python3
"""Checker for the generated minimal skin. Run it after every layout change.

    python3 check.py Minimal.ini        # verify a generated skin
    python3 check.py Minimal.ini --demo # ...and also parse sample-data.txt with its RegExp

Four layers, ordered by how expensive the corresponding bug is. A checker that only verifies
"the sections I reference exist" passes while row 10 reads row 1's value, which is exactly
the bug that a weaker checker missed once and a human eye caught instead.
"""
import argparse
import re
import sys

import layout as L

FAILS = []


def check(ok, msg):
    print(("  ok   " if ok else "  FAIL ") + msg)
    if not ok:
        FAILS.append(msg)


def split_sections(text):
    """Section name -> body text.

    Comment lines are stripped from each body on purpose. Comments written above a
    [Section] header get attributed to the previous section, so a comment that mentions
    !CommandMeasure would otherwise register as a measure reference and produce a false
    failure. That happened for real.
    """
    lines = text.split("\n")
    starts = [(i, l) for i, l in enumerate(lines) if re.fullmatch(r"\[[^\]]+\]", l)]
    out = {}
    for k, (i, name) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        body = "\n".join(l for l in lines[i + 1:end] if not l.startswith(";"))
        out[name[1:-1]] = body
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ini")
    ap.add_argument("--demo", action="store_true",
                    help="also run sample-data.txt through the RegExp")
    args = ap.parse_args()

    raw = open(args.ini, "rb").read()
    print("== encoding ==")
    check(raw[:2] == b"\xff\xfe", "UTF-16LE with BOM (starts ff fe)")
    text = raw.decode("utf-16")
    check("\r" not in text, "LF line endings, no CR")
    check(text.endswith("\n"), "ends with a newline")

    S = split_sections(text)
    names = list(S)
    print("== structure ==")
    check(len(names) == len(set(names)), "section names are unique (%d sections)" % len(names))

    want = {"Rainmeter", "Metadata", "Variables", "MeasureData", "Plate", "Grid",
            "Header", "NowLine", "CanvasAnchor"}
    want |= {"Hour%d" % (i + 1) for i in range(L.WINDOW_H)}
    want |= {"Slot%d" % (i + 1) for i in range(L.SLOTS)}
    want |= {"SlotText%d" % (i + 1) for i in range(L.SLOTS)}
    want |= {"MeasureHeader", "MeasureNowRect"}
    want |= {"MeasureLabel%d" % (i + 1) for i in range(L.WINDOW_H)}
    for i in range(L.SLOTS):
        n = i + 1
        want |= {"Measure%s%d" % (f, n) for f in ("Rect", "RGB", "TX", "TY", "TW", "Text")}
    missing = sorted(want - set(names))
    extra = sorted(set(names) - want)
    check(len(names) == len(want), "section count = %d" % len(want))
    check(not missing, "every expected section is present" + ("" if not missing else " (missing %s)" % missing))
    check(not extra, "no unexpected sections" + ("" if not extra else " (%s)" % extra))

    print("== capture groups ==")
    regex = re.search(r"^RegExp=(.*)$", S["MeasureData"], re.M).group(1)
    n_groups = len(re.findall(re.escape("(.*)"), regex))
    check(regex == L.build_regex(), "RegExp matches the one derived from the constants")
    check(n_groups == L.GROUP_COUNT,
          "capture groups = %d (head %d + labels %d + slots %d x %d)"
          % (n_groups, L.HEAD_FIELDS, L.WINDOW_H, L.SLOTS, L.FIELDS_PER_SLOT))
    check(n_groups <= L.WEBPARSER_MAX_GROUPS,
          "within the WebParser limit of %d" % L.WEBPARSER_MAX_GROUPS)

    # Layers 1 and 2: StringIndex must COVER 1..N exactly, and slot i must only reference
    # slot i's measures. "<= N" is not enough - an off-by-one that pushes the last slot past
    # the end of the pattern is invisible until someone notices a row reading another row.
    used = {}
    for name, body in S.items():
        m = re.search(r"^StringIndex=(\d+)$", body, re.M)
        if m:
            used[name] = int(m.group(1))
    vals = sorted(used.values())
    check(len(vals) == len(set(vals)), "no StringIndex used twice")
    check(vals == list(range(1, L.GROUP_COUNT + 1)),
          "StringIndex covers 1..%d exactly (missing %s, out of range %s)"
          % (L.GROUP_COUNT,
             sorted(set(range(1, L.GROUP_COUNT + 1)) - set(vals)),
             sorted(v for v in vals if v > L.GROUP_COUNT)))

    print("== slot alignment ==")
    bad = []
    for i in range(L.SLOTS):
        n = i + 1
        shape = re.search(r"^Shape=(.*)$", S["Slot%d" % n], re.M).group(1)
        for want_ref in ("[MeasureRect%d]" % n, "[MeasureRGB%d]" % n):
            if want_ref not in shape:
                bad.append("Slot%d shape does not reference %s" % (n, want_ref))
        body = S["SlotText%d" % n]
        if not re.search(r"^MeasureName=MeasureText%d$" % n, body, re.M):
            bad.append("SlotText%d binds the wrong measure" % n)
        for opt, ref in (("W", "TW"), ("X", "TX"), ("Y", "TY")):
            if not re.search(r"^%s=\[Measure%s%d\]$" % (opt, ref, n), body, re.M):
                bad.append("SlotText%d %s does not reference the matching measure" % (n, opt))
    check(not bad, "each slot references only its own measures" + ("" if not bad else " (%s)" % bad[:4]))

    print("== derived geometry ==")
    shapes = re.findall(r"^Shape\d*=Rectangle (\d+),(\d+),(\d+),1 ", S["Grid"], re.M)
    ys = [int(y) for _, y, _ in shapes]
    want_ys = [L.T0 + k * L.HOUR_PX for k in range(L.WINDOW_H + 1)]
    check(ys == want_ys, "grid lines at T0 + k*HOUR_PX (%s)" % (ys if ys != want_ys else "ok"))
    ys2 = [int(re.search(r"^Y=(\d+)$", S["Hour%d" % (i + 1)], re.M).group(1))
           for i in range(L.WINDOW_H)]
    check(ys2 == [L.T0 + i * L.HOUR_PX + L.LABEL_DY for i in range(L.WINDOW_H)],
          "hour labels sit LABEL_DY above their grid line")
    check((L.PLATE_H - L.T0) % L.WINDOW_H == 0,
          "the timeline divides into whole hours, so the last grid line meets the plate edge")
    anchor = re.search(r"^Shape=Rectangle (\d+),(\d+),1,1", S["CanvasAnchor"], re.M)
    check((int(anchor.group(1)), int(anchor.group(2))) == (L.CANVAS_W, L.CANVAS_H),
          "canvas anchor = %dx%d (plate + inset on both sides)" % (L.CANVAS_W, L.CANVAS_H))

    print("== references ==")
    referenced = set()
    for body in S.values():
        referenced |= set(re.findall(r"^MeasureName=([A-Za-z0-9_]+)$", body, re.M))
        referenced |= set(re.findall(r"^URL=\[([A-Za-z0-9_]+)\]$", body, re.M))
        referenced |= set(re.findall(r"\[(Measure[A-Za-z0-9_]+)\]", body))
        referenced |= set(re.findall(r"!SetOption ([A-Za-z0-9_]+) ", body))
        referenced |= set(re.findall(r"!CommandMeasure ([A-Za-z0-9_]+) ", body))
    dangling = sorted(r for r in referenced if r not in names)
    check(not dangling, "every referenced section exists" + ("" if not dangling else " (missing %s)" % dangling))
    check("Live" in re.search(r"!UpdateMeterGroup (\w+)", S["MeasureData"]).group(1)
          and any("Group=Live" in b for b in S.values()),
          "FinishAction refreshes a meter group that actually has members")

    if args.demo:
        print("== sample data ==")
        data = open("sample-data.txt", encoding="utf-8").read()
        # Rainmeter's (?siU) uses PCRE's U flag (ungreedy), which Python's re has no
        # equivalent for. (.*?) is the faithful translation, and it matters: with greedy
        # (.*) the first field swallows the whole document and every later group is wrong.
        py_regex = regex.replace("(?siU)", "(?si)").replace("(.*)", "(.*?)")
        m = re.match(py_regex, data, re.S)
        check(bool(m) and len(m.groups()) == L.GROUP_COUNT,
              "sample-data.txt parses into %s groups (expected %d)"
              % (len(m.groups()) if m else None, L.GROUP_COUNT))
        if m:
            g = m.groups()
            slots = [g[L.HEAD_FIELDS + L.WINDOW_H + i * L.FIELDS_PER_SLOT:
                       L.HEAD_FIELDS + L.WINDOW_H + (i + 1) * L.FIELDS_PER_SLOT]
                     for i in range(L.SLOTS)]
            bad = []
            for i, s in enumerate(slots, 1):
                rect = s[0]
                if rect.startswith("-100"):
                    continue
                parts = rect.split(",")
                # x,y,w,h with an optional trailing corner radius - Rainmeter's Rectangle
                # accepts both, so the checker must too.
                if len(parts) not in (4, 5):
                    bad.append("slot %d rect %r is not x,y,w,h[,radius]" % (i, rect))
                    continue
                x, y, w, h = (int(v) for v in parts[:4])
                if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > L.CANVAS_W or y + h > L.CANVAS_H:
                    bad.append("slot %d rect %r falls outside the canvas" % (i, rect))
                if not re.fullmatch(r"\d{1,3},\d{1,3},\d{1,3}", s[1]):
                    bad.append("slot %d rgb %r is not three channels" % (i, s[1]))
            check(not bad, "every visible slot is inside the canvas and well formed"
                  + ("" if not bad else " (%s)" % bad[:3]))

    print()
    if FAILS:
        print("FAILED (%d)" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
