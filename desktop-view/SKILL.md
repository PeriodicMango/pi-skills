---
name: desktop-view
description: "See and read any window on a remote Windows host over ssh - list what windows are open (title, class, position, size) or capture one window's pixels. Captures the window's own pixels via PrintWindow, so occlusion and off-screen placement do not matter. Use when a task needs to SEE something rendered on a Windows machine instead of asking the user to screenshot it, including verifying a GUI, theme or layout change, reading an on-screen state or an error dialog, checking whether a window is open, minimized or where it sits, doing pixel-level measurement of anything displayed, or finding a window before automating it."
compatibility: "Needs ssh to a Windows host that gives a POSIX-ish shell exposing the Windows drives (WSL is the tested path), PowerShell 5.1+ on that host, and the ability to run ssh from wherever the agent runs. Configure WIN_SSH_TARGET and WIN_TMP before first use."
---

# Seeing a Windows desktop from another machine

If you have ssh access to a Windows box, you can **read its screen yourself** rather than
asking the user to take a screenshot and describe it. Everything goes through one driver
script, so there is nothing machine-specific to remember.

Do not claim you cannot see the screen. Read the boundaries below and state them
accurately, but the default is: *look, don't ask.*

## Configure once

```bash
cp <skill dir>/config.example ~/.config/pi-desktop-view/config
$EDITOR ~/.config/pi-desktop-view/config      # set WIN_SSH_TARGET and WIN_TMP
```

`WIN_SSH_TARGET` is the ssh target (`me@host` or an `~/.ssh/config` alias), `WIN_TMP` is a
temp directory on the Windows side — give it as `C:/Users/you/AppData/Local/Temp` or as
`/mnt/c/Users/you/AppData/Local/Temp` (the driver derives the other form and tells you if
the far side cannot see it). `~/.config` is preferred over a config inside the skill
directory because reinstalling the skill would wipe the latter.

If any command below reports `WIN_SSH_TARGET is not set`, that is the fix.

## Step 1 — what is on the desktop (text only, zero pixels)

```bash
<skill dir>/scripts/winshot.sh list
```

One line per visible top-level window:

```
<hwnd>|<class>|<window title>|<x>,<y>,<w>,<h>
```

- Always do this first. It is how you get the exact title substring for step 2, and often it
  answers the question outright ("is it running", "which window is that", "where did it
  move to") with no pixels and no privacy cost.
- A rect of `-32000,-32000,237,39` means **minimized**.
- Window titles are the windows' own text, so one line can be a whole browser tab title or a
  full file path.

## Step 2 — geometry you should check before trusting any coordinate

```bash
<skill dir>/scripts/winshot.sh screen
```

Prints the virtual desktop bounds, every monitor's bounds, and **this process's DPI
awareness**. Do this before comparing coordinates from two programs: a DPI-unaware process
sees a *virtualized* coordinate space while a per-monitor-aware one sees physical pixels, so
the same window has different numbers depending on who is asking. Multi-monitor virtual
desktops routinely have negative origins and monitor origins that do not match either
monitor's width, so do not assume a single screen.

## Step 3 — capture one window

```bash
<skill dir>/scripts/winshot.sh shot "<substring of the title>" out.png
<skill dir>/scripts/winshot.sh shot "<substring>" out.png 20     # with a 20px screen ring
```

Then read `out.png` with the image-reading tool. Matching is a case-sensitive substring of
the window title; when several windows match, all are printed and the largest is captured.
The script reports `PRINTWINDOW` (must be `True`) and `SIZE`, pulls the PNG back over ssh,
and deletes the remote copy.

## Why PrintWindow and not CopyFromScreen

`scripts/win_shot.ps1` uses `PrintWindow(hwnd, hdc, 2)`. **Do not replace it with
`Graphics.CopyFromScreen`.** CopyFromScreen captures the composited screen, so it returns
whatever window is stacked on top of the target — an image meant to show one application
can come back full of a different one, including whatever private thing the user has open.

- `PrintWindow` asks the target window itself, so occlusion and even off-screen placement do
  not matter.
- Flag `2` is `PW_RENDERFULLCONTENT` and is **required** for DWM-composited windows;
  without it you get a blank bitmap.
- Consequence for interpretation: you get the window's own pixels, so a semi-transparent or
  layered window composites against black rather than against the desktop behind it. Trust
  these captures for **geometry and text**, not for "does it look right over the wallpaper".

## Consent boundary — read this before capturing

- **Window-only capture is the sanctioned default.** It returns exactly one window's pixels.
- `-Pad <n>` adds a screen-grabbed ring around the window, and **that ring contains whatever
  is stacked there**, including other windows. Only use it when the surroundings are the
  thing under discussion, and say so.
- Full-screen capture is a different consent tier: it hands you everything currently visible.
  Ask first, every time.
- `list` reveals window titles, i.e. what apps and tabs are open. That is often necessary,
  but do not volunteer the window list when it is not relevant to the task.
- If you capture something the user did not intend you to see, say so plainly and delete it.
  Do not analyse it or quote from it.

## Limits — state these accurately, do not overclaim

Cannot capture: menu popups, tooltips, context menus (they are separate top-level windows —
find them by their own title or class in `list`), the desktop or wallpaper itself (not a
window), and minimized windows (may come back blank). PrintWindow cannot see composited
effects that fall outside the window's own bounds.

## Measuring pixels in a capture

Getting numbers out is usually the point. Two habits that matter:

1. **Calibrate the image-to-window mapping from a known feature, never from an assumption
   about padding.** Find something whose coordinates you know independently — a window edge,
   a UI element with a known position, a distinctive colour the program draws at a known
   coordinate — and solve for the offset. Guessing the offset has produced a confident and
   completely false finding.
2. **Colours are composited with alpha**, so a brightness threshold tuned on one background
   fails on another. Print the actual pixel values before trusting a detector, and prefer
   detecting a known-saturated colour (a status red, a brand blue) over "brighter than N".

A useful sanity anchor: capture a window whose size you can predict from the program's own
configuration (a canvas, a fixed dialog). If the `SIZE` line does not match, your
coordinates are being read in a different DPI space than the program's.

## Beyond looking

The same ssh -> PowerShell path can also *act* on that desktop (send keys, click, launch
programs). That is a higher consent tier than looking and is deliberately not part of this
skill. If a task needs it, discuss the boundary explicitly first.
