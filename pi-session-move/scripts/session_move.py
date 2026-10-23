#!/usr/bin/env python3
"""Move pi coding-agent session files between project directories.

Usage:
  session_move.py list [--cwd PATH] [--grep REGEX] [--since YYYY-MM-DD] [--all]
  session_move.py move --to PATH [--dry-run] TARGET...
  session_move.py fix-parents [--dry-run]
  session_move.py prune-index

TARGET: session id (full uuid, or >=6 char prefix), filename, or full path.

A "move" does three things:
  1. rewrites the session header cwd (and the system-prompt section cwd) to --to
  2. moves the file into sessions/--<encoded cwd>--/
  3. repoints any other session whose header parentSession references a moved file
The pi-web index is pruned of dead paths. Nothing is restarted: pi-web rebuilds
itself on the next session-list scan (see SKILL.md).
"""

import argparse
import json
import os
import re
import sys
import tempfile

SESSIONS = "sessions"
INDEX = "pi-web-session-index.json"


# ---------- paths ----------

def agent_dir(args):
    return os.path.abspath(os.path.expanduser(args.agent_dir))


def sessions_root(args):
    return os.path.join(agent_dir(args), SESSIONS)


def encode_cwd(cwd):
    """Mirror of pi's getDefaultSessionDirPath(): --<cwd without leading /, [/\\:] -> ->--"""
    abs_cwd = os.path.abspath(os.path.expanduser(cwd))
    stripped = abs_cwd.lstrip("/" + os.sep)
    return "--" + re.sub(r"[/\\:]", "-", stripped) + "--"


def dir_for_cwd(args, cwd):
    return os.path.join(sessions_root(args), encode_cwd(cwd))


def iter_session_files(args):
    root = sessions_root(args)
    if not os.path.isdir(root):
        return
    for d in sorted(os.listdir(root)):
        full = os.path.join(root, d)
        if not os.path.isdir(full):
            continue
        for f in sorted(os.listdir(full)):
            if f.endswith(".jsonl"):
                yield os.path.join(full, f)


# ---------- jsonl helpers ----------

def read_header(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                return None
            return obj if obj.get("type") == "session" else None
    return None


def scan_file(path, want_user_text=False):
    """Return (header, message_count, first_user_text)."""
    header, count, first = None, 0, ""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("type") == "session":
                header = obj
                continue
            if obj.get("type") != "message":
                continue
            msg = obj.get("message") or {}
            if msg.get("role") in ("user", "assistant"):
                count += 1
            if want_user_text and msg.get("role") == "user":
                content = msg.get("content")
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    text = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
                else:
                    text = ""
                if not first and text:
                    first = text
    return header, count, first


def rewrite_file(src, dst, header_cwd=None, parent_map=None):
    """Copy src -> dst rewriting cwd/parentSession. Returns set of changed field names."""
    changed = set()
    with open(src, encoding="utf-8") as fin, open(dst, "w", encoding="utf-8") as fout:
        for line in fin:
            stripped = line.strip()
            if not stripped:
                fout.write(line)
                continue
            try:
                obj = json.loads(stripped)
            except Exception:
                fout.write(line)
                continue
            touched = False
            if header_cwd and isinstance(obj.get("cwd"), str):
                obj["cwd"] = header_cwd
                touched = True
                changed.add("cwd")
            if parent_map:
                ps = obj.get("parentSession")
                if isinstance(ps, str) and ps in parent_map:
                    obj["parentSession"] = parent_map[ps]
                    touched = True
                    changed.add("parentSession")
            msg = obj.get("message")
            if header_cwd and isinstance(msg, dict):
                sections = msg.get("sections")
                if isinstance(sections, dict) and isinstance(sections.get("cwd"), str):
                    sections["cwd"] = header_cwd
                    touched = True
                    changed.add("sections.cwd")
            fout.write(json.dumps(obj, ensure_ascii=False) + "\n" if touched else line)
    return changed


def atomic_write_json(path, data):
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    os.replace(tmp, path)


# ---------- resolve targets ----------

def resolve_target(args, token):
    if os.path.isfile(token):
        return os.path.abspath(token)
    files = list(iter_session_files(args))
    base = os.path.basename(token)
    for p in files:
        if os.path.basename(p) == base:
            return p
    pat = re.compile("^" + re.escape(token), re.I)
    hits = []
    for p in files:
        name = os.path.basename(p)
        m = re.search(r"_([0-9a-f-]{36})\.jsonl$", name)
        sid = m.group(1) if m else ""
        # id prefix, or filename/timestamp prefix (e.g. 2026-10-21T06-13)
        if (sid and pat.match(sid)) or pat.match(name):
            hits.append(p)
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        sys.exit(f"ambiguous target {token!r}: {len(hits)} sessions match, be more specific")
    sys.exit(f"no session matches {token!r}")


# ---------- commands ----------

def cmd_list(args):
    rows = []
    for p in iter_session_files(args):
        if not args.all:
            header = read_header(p)
            if not header:
                continue
            if args.cwd and os.path.abspath(header.get("cwd") or "") != os.path.abspath(os.path.expanduser(args.cwd)):
                continue
            if args.since and (header.get("timestamp") or "")[:10] < args.since:
                continue
        header, count, first = scan_file(p, want_user_text=True)
        if not header:
            continue
        if args.grep and not re.search(args.grep, first, re.I):
            continue
        rows.append((header.get("timestamp", "")[:10], os.path.getsize(p) // 1024, count,
                     (header.get("id") or "")[:8], header.get("cwd", ""), first[:60].replace("\n", " "), p))
    rows.sort()
    for date, kb, count, sid, cwd, first, p in rows:
        print(f"{date}  {kb:>6}KB  msgs={count:<3} {sid}  {cwd}")
        print(f"          {first}")
    print(f"-- {len(rows)} sessions")


def cmd_move(args):
    target_cwd = os.path.abspath(os.path.expanduser(args.to))
    dest_dir = dir_for_cwd(args, target_cwd)
    moved = {}
    for token in args.targets:
        src = resolve_target(args, token)
        dst = os.path.join(dest_dir, os.path.basename(src))
        if os.path.abspath(src) == os.path.abspath(dst):
            print(f"already in place: {os.path.basename(src)}")
            continue
        if os.path.exists(dst):
            sys.exit(f"destination already exists: {dst}")
        moved[src] = dst

    if not moved:
        print("nothing to do")
        return

    if args.dry_run:
        for src, dst in moved.items():
            print(f"[dry-run] {src}\n       -> {dst}")
        print(f"[dry-run] would patch cwd -> {target_cwd} and repoint {len(moved)} parentSession ref(s)")
        return

    os.makedirs(dest_dir, exist_ok=True)
    report = []
    for src, dst in moved.items():
        tmp = dst + ".tmp"
        changed = rewrite_file(src, tmp, header_cwd=target_cwd)
        os.replace(tmp, dst)
        os.remove(src)
        report.append((os.path.basename(dst), sorted(changed)))

    # repoint children anywhere in the tree
    fixed_children = 0
    for p in list(iter_session_files(args)):
        header = read_header(p)
        if not header:
            continue
        ps = header.get("parentSession")
        if isinstance(ps, str) and ps in moved:
            tmp = p + ".tmp"
            rewrite_file(p, tmp, parent_map=moved)
            os.replace(tmp, p)
            fixed_children += 1

    pruned = prune_index(args)

    for name, fields in report:
        print(f"moved {name}  patched: {', '.join(fields) or 'none'}")
    print(f"-- {len(report)} moved into {dest_dir}")
    print(f"-- parentSession repointed: {fixed_children}")
    print(f"-- index dead paths pruned: {pruned}")
    print("-- pi-web: refresh the session list; do NOT restart the service "
          "(it hosts the running agent).")


def cmd_fix_parents(args):
    all_paths = {}
    for p in iter_session_files(args):
        header = read_header(p)
        if not header:
            continue
        all_paths[p] = header
    ids = {}
    for p in all_paths:
        m = re.search(r"_([0-9a-f-]{36})\.jsonl$", os.path.basename(p))
        if m:
            ids.setdefault(m.group(1), p)
    fixes = {}
    for p, header in all_paths.items():
        ps = header.get("parentSession")
        if not isinstance(ps, str) or os.path.exists(ps):
            continue
        if args.match and args.match not in ps:
            continue
        m = re.search(r"_([0-9a-f-]{36})\.jsonl$", os.path.basename(ps))
        sid = m.group(1) if m else ""
        new = ids.get(sid)
        if new:
            fixes[ps] = new
    if not fixes:
        print("no dangling parentSession references")
        return
    # a fix applies to every session whose header carries the old path
    affected = [p for p, h in all_paths.items()
                if isinstance(h.get("parentSession"), str) and h["parentSession"] in fixes]
    for old, new in fixes.items():
        owners = sum(1 for p in affected if all_paths[p].get("parentSession") == old)
        print(f"{old}\n  -> {new}   ({owners} session(s))")
    if args.dry_run:
        print(f"[dry-run] {len(affected)} session(s) in {len(fixes)} distinct path(s) would be fixed")
        return
    # rewrite only header lines, keep transcript content untouched
    for p in affected:
        tmp = p + ".tmp"
        rewrite_file(p, tmp, parent_map=fixes)
        os.replace(tmp, p)
    print(f"-- {len(affected)} session(s) repointed ({len(fixes)} distinct path(s))")



def prune_index(args):
    path = os.path.join(agent_dir(args), INDEX)
    if not os.path.exists(path):
        return 0
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"index unreadable, skipped: {e}")
        return 0
    entries = data.get("entries") or {}
    dead = [k for k in entries if not os.path.exists(k)]
    for k in dead:
        del entries[k]
    if dead:
        atomic_write_json(path, data)
    return len(dead)


def cmd_prune_index(args):
    print(f"-- pruned {prune_index(args)} dead index entr(ies)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent-dir", default="~/.pi/agent", help="pi agent dir (default ~/.pi/agent)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="list sessions")
    p.add_argument("--cwd")
    p.add_argument("--grep", help="regex against first user message")
    p.add_argument("--since", help="YYYY-MM-DD")
    p.add_argument("--all", action="store_true", help="unfiltered")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("move", help="move sessions into a project dir")
    p.add_argument("--to", required=True, help="target project cwd, e.g. /path/to/project/sub")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("targets", nargs="+", help="session id prefix / filename / path")
    p.set_defaults(func=cmd_move)

    p = sub.add_parser("fix-parents", help="repair dangling parentSession paths")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--match", help="only repair paths containing this substring")
    p.set_defaults(func=cmd_fix_parents)

    p = sub.add_parser("prune-index", help="drop dead paths from pi-web-session-index.json")
    p.set_defaults(func=cmd_prune_index)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
