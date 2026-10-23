#!/usr/bin/env bash
# Install skills from this repo into a pi agent skills directory.
#
#   ./install.sh --list                 list available skills
#   ./install.sh <skill> [<skill>...]   install one or more named skills
#   ./install.sh --all                  install every skill in the repo
#
# Options:
#   --dest DIR   install somewhere other than ~/.pi/agent/skills
#                (or set PI_SKILLS_DEST)
#   --link       symlink instead of copy, for developing a skill in place
#   --force, -f  replace an already-installed skill
#
# Copy is the default so the install survives the repo moving or being deleted.

set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
home="${HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
dest="${PI_SKILLS_DEST:-$home/.pi/agent/skills}"
mode="copy"
force=0
all=0
skills=()

usage() {
  sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

available() {
  for d in "$repo_dir"/*/; do
    [ -f "$d/SKILL.md" ] && basename "$d"
  done
}

list_skills() {
  while IFS= read -r name; do
    desc="$(sed -n 's/^description: //p' "$repo_dir/$name/SKILL.md" | head -1 \
            | sed 's/^"//; s/"$//' | cut -c1-100)"
    printf '  %-24s %s\n' "$name" "$desc"
  done < <(available)
}

while [ $# -gt 0 ]; do
  case "$1" in
    --list|-l)   list_skills; exit 0 ;;
    --all|-a)    all=1; shift ;;
    --link)      mode="link"; shift ;;
    --force|-f)  force=1; shift ;;
    --dest)      dest="${2:?--dest needs a directory}"; shift 2 ;;
    -h|--help)   usage 0 ;;
    -*)          echo "unknown option: $1" >&2; usage 1 ;;
    *)           skills+=("$1"); shift ;;
  esac
done

if [ "$all" -eq 1 ] && [ "${#skills[@]}" -gt 0 ]; then
  echo "--all and explicit skill names are mutually exclusive" >&2
  exit 1
fi

if [ "$all" -eq 1 ]; then
  while IFS= read -r name; do skills+=("$name"); done < <(available)
fi

if [ "${#skills[@]}" -eq 0 ]; then
  echo "which skill? (or --all)" >&2
  list_skills >&2
  exit 1
fi

# validate every name before touching anything
for name in "${skills[@]}"; do
  if [ ! -f "$repo_dir/$name/SKILL.md" ]; then
    echo "no such skill: $name" >&2
    list_skills >&2
    exit 1
  fi
done

# check collisions before copying a batch
if [ "$force" -ne 1 ]; then
  clashes=()
  for name in "${skills[@]}"; do
    [ -e "$dest/$name" ] || [ -L "$dest/$name" ] && clashes+=("$name")
  done
  if [ "${#clashes[@]}" -gt 0 ]; then
    echo "already installed: ${clashes[*]} (use --force to replace)" >&2
    exit 1
  fi
fi

mkdir -p "$dest"
for name in "${skills[@]}"; do
  target="$dest/$name"
  if [ -e "$target" ] || [ -L "$target" ]; then
    rm -rf "$target"
  fi
  if [ "$mode" = "link" ]; then
    ln -s "$repo_dir/$name" "$target"
    echo "linked $target -> $repo_dir/$name"
  else
    cp -r "$repo_dir/$name" "$target"
    echo "copied $target"
  fi
  # script bits, when present
  if [ -d "$target/scripts" ]; then
    find "$target/scripts" -type f \( -name '*.sh' -o -name '*.py' \) -exec chmod +x {} + 2>/dev/null || true
  fi
done

echo "done (${#skills[@]} skill(s)). pi loads skills at the start of a session — start a new one."
