---
name: pi-session-move
description: Move pi (pi-coding-agent / pi-web) session transcripts between project directories by rewriting the session header cwd, so the web UI and CLI list a conversation under a different project. Use when a session sits under the wrong working directory, when archiving sessions per project or course, when splitting one project folder into several, or when resuming a session from a different cwd. Handles the header cwd, the system-prompt cwd, parentSession links for subagent sessions, and the pi-web session index.
---

# pi-session-move

Re-home session transcripts (`<agent-dir>/sessions/**/*.jsonl`) from one project
cwd to another — file location, header `cwd`, and `parentSession` links all stay
consistent, and pi-web picks the change up **without restarting it**.

Tested against `@earendil-works/pi-coding-agent` + `@agegr/pi-web`, POSIX paths.

## Install

From the repo root (this skill ships inside the `pi-skills` monorepo):

```bash
./install.sh pi-session-move          # copies into ~/.pi/agent/skills/
./install.sh --list                   # show available skills
./install.sh pi-session-move --link   # symlink instead of copy (for development)
```

Or manually: `cp -r pi-session-move ~/.pi/agent/skills/` and
`chmod +x ~/.pi/agent/skills/pi-session-move/scripts/session_move.py`.

Everything below uses:

```bash
S=~/.pi/agent/skills/pi-session-move/scripts/session_move.py
```

## Hard facts about pi's session storage

Directory encoding — `dist/core/session-manager.js`, `getDefaultSessionDirPath()`:

```
--<cwd with leading separator stripped, [/ \ :] each replaced by ->--
/home/user/proj            -> sessions/--root-proj--
/home/user/proj/sub        -> sessions/--root-proj-sub--
```

- **The header `cwd` is authoritative**, not the directory name. `SessionManager.open()`
  reads `header.cwd` and resumes there (`cwdOverride ?? getSessionHeaderCwd(header)`),
  and `findMostRecentSession()` filters by header cwd. A file dropped into the new
  directory but left with the old `cwd` still behaves as the old project.
- Session discovery (`listSessions`) walks **every** subdirectory of `sessions/` and
  keys on the file, not the dir name — so a stale dir name is cosmetic. Keep them
  aligned anyway, or the next `/new` in that project creates a second directory.
- Two places hold cwd inside a file: the top-level `type:"session"` header line, and
  `message.sections.cwd` on the system-prompt message. Update both.
- Subagent sessions carry `parentSession: <absolute path to parent .jsonl>`. Move the
  parent and not the child and the link dangles; move both and the child still points
  at the parent's old path unless you rewrite it.
- `<agent-dir>/pi-web-session-index.json` is a **cache**: a `Map` loaded once at process
  start, then on every scan compared against the real file list; missing paths are
  dropped, new or changed files re-parsed, and when anything changed the whole map is
  rewritten to disk in a `queueMicrotask` (`.next/server/chunks/5582.js`). It heals
  itself on the next session-list scan — no service restart, no manual edit.

## Do not restart the web service for this

With pi-web, the agent session itself runs inside the `pi-web.service` process (the
agent's shell has `PPID == systemd MainPID`, `next-server`). Restarting it kills the
in-flight tool call: no `toolResult` is ever written, the UI shows "no result
provided", and that turn's work is lost. pi-web does re-`session_start` open sessions
on boot, so the conversation survives and the next message resumes it — but the
interrupted call does not come back.

The index needs no restart. After moving files, **refresh the pi-web session list**
(that triggers a scan) and dead/new entries are reconciled automatically.

## Workflow

```bash
# 1. find candidates (filters by header cwd / date / first user message)
python3 $S list --cwd /path/to/project --since 2026-10-01
python3 $S list --grep 'interview|ethics'

# 2. dry-run: prints source -> destination, writes nothing
python3 $S move --to /path/to/project/sub --dry-run 01a13cb5 2026-10-15T02-36

# 3. move (id prefix / filename / timestamp prefix / absolute path all accepted)
python3 $S move --to /path/to/project/sub 01a13cb5 01a13d6a-ead4

# 4. repair links moved by hand or by an older script
python3 $S fix-parents --dry-run
python3 $S fix-parents --match=--root-proj--/2026-10-14T23-18-13
```

`move` does: `mkdir` the target dir → rewrite `cwd` + `sections.cwd` → `os.replace`
into `--<encoded cwd>--/` → repoint every `parentSession` that referenced a moved
file → prune dead index entries. Untouched lines are copied byte-for-byte; only
changed lines are re-serialized, so diffs stay small.

`--match` scopes `fix-parents` to parents whose stale path contains that substring —
useful because unrelated sessions elsewhere may already carry dangling links. A value
starting with `--` needs the `--match=VALUE` form, or argparse reads it as a flag.

## Identifying which sessions belong to the project

A keyword grep over the whole file gives false positives: injected context/memory and
system prompts mention project names in sessions that have nothing to do with them.
Grep **user-role messages only** — that is what `list --grep` does.

The trap that actually broke a real move: **subagent sessions often contain none of the
project's keywords.** A research child prompted "Give me an accurate, citable
description of the legal regimes that govern automated hiring…" mentions neither the
product name nor the course, yet it belongs to the project. So:

1. list by keyword, then
2. **scan the same time window for siblings** — agents spawned in one batch share a
   timestamp cluster (`2026-10-15T02-36-1x`) and a uuid prefix;
3. **check `parentSession`** — any session whose parent is already in the move set
   belongs in the same move;
4. after moving, run `fix-parents --dry-run`; a non-empty result means a child was
   left behind.

Never move the session file of the conversation that is currently running — it is
still being appended to.

## Verify

```bash
ls ~/.pi/agent/sessions/--root-proj-sub-- | wc -l
python3 - <<'PY'
import json, os
p = os.path.expanduser('~/.pi/agent/pi-web-session-index.json')
d = json.load(open(p))
print('target cwd entries:', len([v for v in d['entries'].values()
                                  if v['info']['cwd'] == '/path/to/project/sub']))
print('dead entries:', len([k for k in d['entries'] if not os.path.exists(k)]))
PY
systemctl is-active pi-web.service   # expect: active
```

Expect: file count == moved count, target-cwd entries == moved count, dead entries 0.
Then refresh the pi-web UI once so its scan rewrites the index.

## Pitfalls

- **Always run `fix-parents --dry-run` after a move.** When a parent and its subagent
  children move in the *same* batch, a naive "patch cwd only" script leaves every child
  pointing at the parent's old path. In the run that produced this skill, 12 research
  children kept `parentSession` on the old parent path and needed a separate repair.
  `move` handles it; hand edits do not.
- Fixes are keyed by **old path**, not by session: one stale parent path is often shared
  by a dozen children, so the fix list looks short while the repair touches many files.
  Read the `(N session(s))` count, not the number of printed lines.
- Only header lines are rewritten. The same old path also appears inside transcript
  bodies (tool results that rendered the file path); that is history — leave it.
- Don't rename the `.jsonl`: the filename (`<iso-timestamp>_<uuid>.jsonl`) is how the
  session id maps to a file.
- Don't delete the index file; `prune-index` is enough, and a running service would
  rewrite it from memory anyway.
- Test in a sandbox: `--agent-dir /tmp/agent-test` keeps your real sessions untouched.
