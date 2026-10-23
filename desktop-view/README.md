# desktop-view

A [pi](https://github.com/badlogic/pi) skill that lets the agent **see a Windows desktop
over ssh** — list the open windows, or capture one window's pixels — instead of asking you
to take a screenshot.

```
$ winshot.sh list
6753740|CASCADIA_HOSTING_WINDOW_CLASS|Terminal|3702,210,682,666
7998136|ApplicationFrameWindow|Settings|2552,-8,1936,1048
5117558|RainmeterMeterWindow|...\Skins\Widget\Widget.ini|2969,0,739,1003

$ winshot.sh shot "Widget.ini" widget.png
MATCHCOUNT|1
CHOSEN|5117558|...\Skins\Widget\Widget.ini
PRINTWINDOW|True
SIZE|739x1003|dst=0,0
wrote widget.png (20819 bytes)
```

## Why this exists

An agent working on a GUI has no eyes. The usual workaround is a human taking screenshots
and describing them, which is slow and lossy: "looks a bit off" is not a number, and the
agent cannot check its own work.

If the Windows box is reachable over ssh, that workaround is unnecessary. Two commands
replace it, and the agent can iterate on pixel-exact results by itself.

## Install

Clone into your pi skills directory:

```bash
git clone <this repo> ~/.pi/agent/skills/desktop-view
```

The skill directory name must match the `name` in `SKILL.md` (`desktop-view`). Pi scans the
skills directory at startup, so a **new session** is needed before it is offered; you can
also force it with `/skill:desktop-view`.

## Configure

```bash
mkdir -p ~/.config/pi-desktop-view
cp config.example ~/.config/pi-desktop-view/config
$EDITOR ~/.config/pi-desktop-view/config
```

Two values are required:

| key | what |
|---|---|
| `WIN_SSH_TARGET` | ssh target for the Windows host — `me@host` or an `~/.ssh/config` alias |
| `WIN_TMP` | a temp dir on the Windows side, as `C:/Users/you/AppData/Local/Temp` or `/mnt/c/Users/you/AppData/Local/Temp` |

The driver derives whichever form you did not write and refuses to proceed if the far side
cannot see it, so a typo fails immediately with a specific message instead of halfway
through a capture.

Optional keys (`WIN_SSH_KEY`, `WIN_POWERSHELL`, `WIN_TMP_SHELL`, `WIN_SSH_OPTS`) are
documented in `config.example`.

## Requirements on the far side

- ssh into a **POSIX-ish shell whose filesystem exposes the Windows drives**. WSL is the
  tested path; Git Bash or Cygwin should work too.
- **PowerShell 5.1 or newer**, reachable from that shell at `WIN_POWERSHELL` (the default is
  the WSL path to `powershell.exe`).
- No mount of the Windows filesystem is needed **on the machine running the agent** —
  every transfer goes over ssh, so the agent can live on a different host entirely.

If you ssh into a *native* Windows OpenSSH server (cmd.exe or PowerShell as the login shell,
no `/mnt/c`), the driver's `cat`/`md5sum` calls will not work. That setup would need the
transfer rewritten to base64 through PowerShell; it is not implemented, and contributions
are welcome.

## Usage

```
winshot.sh list                                     # open windows, text only
winshot.sh screen                                   # monitors + DPI awareness of the querying process
winshot.sh shot <title-substring> [out.png] [pad]   # capture one window
```

Exit codes: `0` ok, `1` configuration/usage problem, `2` the capture failed at the far end.

Run `screen` before comparing coordinates that came from two different programs. A
DPI-unaware process sees a virtualized coordinate space and a per-monitor-aware one sees
physical pixels, so identical windows produce different numbers depending on who is asking.

## How it works, and the one decision that matters

`win_shot.ps1` enumerates top-level windows with `EnumWindows` + `GetWindowRect`, and
captures with:

```csharp
PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT /* = 2 */)
```

**Not `Graphics.CopyFromScreen`**, which is the obvious choice and the wrong one: it captures
the composited screen, so it returns whatever window is stacked on top of the target. A
capture meant to show one application comes back containing a different one — including
whatever private thing the user happens to have open. `PrintWindow` asks the target window
itself, so occlusion and off-screen placement are irrelevant.

`PW_RENDERFULLCONTENT` is required for DWM-composited windows; without it `PrintWindow`
returns a blank bitmap.

Practical consequence: you get the window's own pixels, so a semi-transparent or layered
window composites against black rather than the desktop behind it. Trust these captures for
geometry and text, not for appearance over the wallpaper.

## Limitations

- Cannot capture menu popups, tooltips or context menus — they are separate top-level
  windows, so find them by their own title or class in `list` and capture those.
- The desktop/wallpaper is not a window and cannot be captured this way.
- Minimized windows may come back blank.
- `-Pad` adds a ring grabbed from the screen, and that ring contains whatever is stacked
  there, including other windows. Off by default for that reason.

## Privacy

This reads a real desktop. `list` reveals window titles; `shot` reveals one window's pixels;
`-Pad` and any full-screen capture reveal the surroundings. The skill instructs the agent to
treat those as three different consent levels, to keep to window-only capture by default, and
to report and discard anything captured beyond what was intended.

## License

MIT — see [LICENSE](LICENSE).
