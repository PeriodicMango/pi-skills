# pi-session-move

Move a pi session to a different project folder — properly.

pi stores sessions under `~/.pi/agent/sessions/--<encoded-cwd>--/`, and the project a
session "belongs to" lives in **two places at once**: the folder it sits in, and the
`cwd` recorded in the session's header line. Renaming the folder alone does nothing —
the session still resumes in the old project, and the web UI still groups it there.
Copying a folder also silently breaks `parentSession` links for subagent sessions,
and leaves the session index pointing at paths that no longer exist.

This skill does all four parts in one command, and keeps the index consistent without
restarting the web UI.

## Quick start

```bash
./install.sh pi-session-move
S=~/.pi/agent/skills/pi-session-move/scripts/session_move.py

python3 $S list --cwd /home/user/proj              # what's in this project
python3 $S move --to /home/user/proj/sub --dry-run 01a13cb5
python3 $S move --to /home/user/proj/sub 01a13cb5 2026-10-15T02-36
python3 $S fix-parents --dry-run                   # after hand-editing anything
```

## What it changes

For every session being moved:

| Field | Why |
|---|---|
| file location → `sessions/--<encoded cwd>--/` | where pi looks for the project |
| header `cwd` | authoritative on resume — `SessionManager.open()` reads it |
| `message.sections.cwd` | the system-prompt record of the same thing |
| other sessions' `parentSession` | subagent children point at the parent's absolute path |
| `pi-web-session-index.json` | drops entries for paths that no longer exist |

Untouched lines are copied byte-for-byte; only changed lines are re-serialized, so the
result is a minimal diff and the transcript body is never rewritten.

## Two things worth knowing

**Don't restart pi-web after moving files.** When the agent runs inside pi-web, that
service *is* the process running the conversation — restarting it kills the in-flight
tool call, and that turn's result is lost. The index rebuilds itself on the next
session-list scan; refresh the page instead.

**Subagent sessions may contain none of your project's keywords.** A research child
prompted "…describe the legal regimes that govern automated hiring…" mentions neither
the product nor the course name, but it belongs to the project. Find siblings by
timestamp cluster and by `parentSession`, not only by grep.

Full details, the storage internals, and the pitfalls list are in
[`SKILL.md`](SKILL.md) — that file is what the agent actually reads.

## Requirements

Python 3.8+, POSIX paths, `pi` / `pi-web` session layout (tested against
`@earendil-works/pi-coding-agent` and `@agegr/pi-web`, October 2026).

## License

MIT — see [../LICENSE](../LICENSE).
