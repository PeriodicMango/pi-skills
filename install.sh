#!/usr/bin/env bash
# Install a skill from this repo into a pi agent skills directory.
#
#   ./install.sh --list
#   ./install.sh <skill> [--dest DIR] [--link] [--force]
#
# Default dest: ~/.pi/agent/skills   (override with --dest or PI_SKILLS_DEST)
# Copy is the default so the install survives the repo moving or being deleted;
# --link symlinks instead, for developing a skill in place.

set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
home="${HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
dest="${PI_SKILLS_DEST:-$home/.pi/agent/skills}"
skill=""
mode="copy"
force=0

usage() {
  sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

list_skills() {
  for d in "$repo_dir"/*/; do
    name="$(basename "$d")"
    [ -f "$d/SKILL.md" ] || continue
    desc="$(sed -n 's/^description: //p' "$d/SKILL.md" | head -1 | cut -c1-100)"
    printf '  %-24s %s\n' "$name" "$desc"
  done
}

while [ $# -gt 0 ]; do
  case "$1" in
    --list|-l)   list_skills; exit 0 ;;
    --link)      mode="link"; shift ;;
    --force|-f)  force=1; shift ;;
    --dest)      dest="${2:?--dest needs a directory}"; shift 2 ;;
    -h|--help)   usage 0 ;;
    -*)          echo "unknown option: $1" >&2; usage 1 ;;
    *)           skill="$1"; shift ;;
  esac
done

if [ -z "$skill" ]; then
  echo "which skill?" >&2
  list_skills >&2
  exit 1
fi

src="$repo_dir/$skill"
if [ ! -f "$src/SKILL.md" ]; then
  echo "no such skill: $skill" >&2
  list_skills >&2
  exit 1
fi

mkdir -p "$dest"
target="$dest/$skill"

if [ -e "$target" ] || [ -L "$target" ]; then
  if [ "$force" -ne 1 ]; then
    echo "already installed: $target (use --force to replace)" >&2
    exit 1
  fi
  rm -rf "$target"
fi

if [ "$mode" = "link" ]; then
  ln -s "$src" "$target"
  echo "linked $target -> $src"
else
  cp -r "$src" "$target"
  echo "copied $target"
fi

# script bits, when present
if [ -d "$target/scripts" ]; then
  find "$target/scripts" -type f \( -name '*.sh' -o -name '*.py' \) -exec chmod +x {} + 2>/dev/null || true
fi

echo "done. pi loads skills at the start of a session — start a new one (or restart the TUI)."
