#!/usr/bin/env bash
# Drive win_shot.ps1 on a remote Windows host over ssh: upload the script if needed, run it,
# pull the result back, clean up.
#
# Nothing here is machine-specific: the host and paths come from configuration, and every
# file transfer goes over ssh, so this machine needs NO mount of the Windows filesystem.
#
# Usage:
#   winshot.sh list                                    what windows are open (text only)
#   winshot.sh screen                                  virtual desktop, monitors, DPI awareness
#   winshot.sh shot <title-substring> [out.png] [pad]  capture one window
#
# Configuration, first hit per key wins: environment variables, then $WIN_CONFIG, then
# ${XDG_CONFIG_HOME:-~/.config}/pi-desktop-view/config, then ./config next to this script.
# See config.example.
#
# Requirements on the far side: an ssh target that gives you a POSIX-ish shell whose
# filesystem exposes the Windows drive (WSL does; Git Bash or Cygwin would too), with
# PowerShell 5.1+ reachable from it.
#
# Exit codes: 0 ok | 1 configuration, usage, or precondition problem | 2 remote capture failed
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$HERE")"
PS1="$HERE/win_shot.ps1"

usage() {
  sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

# ---- configuration -------------------------------------------------------------------
CONFIG_CANDIDATES=(
  "${WIN_CONFIG:-}"
  "${XDG_CONFIG_HOME:-$HOME/.config}/pi-desktop-view/config"
  "$SKILL_DIR/config"
)
for cfg in "${CONFIG_CANDIDATES[@]}"; do
  [ -n "$cfg" ] && [ -f "$cfg" ] || continue
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|'#'*) continue ;; esac
    key="${line%%=*}"; val="${line#*=}"
    key="${key//[[:space:]]/}"
    [ -n "$key" ] || continue
    val="${val%\"}"; val="${val#\"}"
    if [ -z "${!key:-}" ]; then printf -v "$key" '%s' "$val"; export "${key?}"; fi
  done < "$cfg"
done

WIN_SSH_TARGET="${WIN_SSH_TARGET:-}"
WIN_TMP="${WIN_TMP:-}"
WIN_POWERSHELL="${WIN_POWERSHELL:-/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe}"
WIN_SSH_OPTS="${WIN_SSH_OPTS:--o StrictHostKeyChecking=accept-new -o ConnectTimeout=8}"

die() {  # die [exit-code] message...   (default code 1 = configuration/usage)
  local code=1
  case "${1:-}" in [0-9]|[0-9][0-9]) code="$1"; shift ;; esac
  echo "winshot: $*" >&2
  exit "$code"
}

# ---- WIN_TMP comes in one form, the other is derived ----------------------------------
#   Windows form (what PowerShell wants):  C:/Users/you/AppData/Local/Temp
#   Shell form   (what the ssh target's shell wants): /mnt/c/Users/you/AppData/Local/Temp
# The C: -> /mnt/c mapping is the WSL convention. Override WIN_TMP_SHELL if the far side
# mounts drives somewhere else.
to_win_form() {
  case "$1" in
    /mnt/[A-Za-z]/*)
      d="$(printf '%s' "$1" | cut -d/ -f3)"
      printf '%s:%s' "$(printf '%s' "$d" | tr '[:lower:]' '[:upper:]')" "${1#/mnt/$d}" ;;
    [A-Za-z]:[\\/]*) printf '%s' "$1" | tr '\\' '/' ;;
    *) printf '%s' "$1" ;;
  esac
}
to_shell_form() {
  case "$1" in
    /mnt/[A-Za-z]/*) printf '%s' "$1" ;;
    [A-Za-z]:[\\/]*)
      printf '/mnt/%s%s' \
        "$(printf '%s' "$1" | cut -c1 | tr '[:upper:]' '[:lower:]')" \
        "$(printf '%s' "$1" | cut -c3- | tr '\\' '/')" ;;
    *) printf '%s' "$1" ;;
  esac
}

rsh() {   # run a shell command on the far side
  # shellcheck disable=SC2086
  if [ -n "${WIN_SSH_KEY:-}" ]; then
    ssh $WIN_SSH_OPTS -i "$WIN_SSH_KEY" "$WIN_SSH_TARGET" "$@"
  else
    ssh $WIN_SSH_OPTS "$WIN_SSH_TARGET" "$@"
  fi
}

# ---- preconditions --------------------------------------------------------------------
[ -f "$PS1" ]            || die "missing $PS1"
[ -n "$WIN_SSH_TARGET" ] || die "WIN_SSH_TARGET is not set - copy config.example to ~/.config/pi-desktop-view/config and fill it in (see README.md)"
[ -n "$WIN_TMP" ]        || die "WIN_TMP is not set - see config.example"

WIN_TMP_WIN="$(to_win_form "$WIN_TMP")"
WIN_TMP_SHELL="${WIN_TMP_SHELL:-$(to_shell_form "$WIN_TMP")}"
REMOTE_PS1="$WIN_TMP_WIN/win_shot.ps1"
REMOTE_PNG="$WIN_TMP_WIN/winshot.png"
SHELL_PS1="$WIN_TMP_SHELL/win_shot.ps1"
SHELL_PNG="$WIN_TMP_SHELL/winshot.png"

# The far side must actually see that directory. Check it remotely rather than assuming:
# the temp dir is a path on the OTHER machine, and this machine needs no mount at all.
probe() {
  rsh "test -d '$WIN_TMP_SHELL'" >/dev/null 2>&1 || die \
"the ssh target cannot see WIN_TMP_SHELL=$WIN_TMP_SHELL
       (derived from WIN_TMP=$WIN_TMP).
       Check: does 'ssh $WIN_SSH_TARGET ls \"$WIN_TMP_SHELL\"' work?
       If the far side mounts drives somewhere other than /mnt/<letter>, set WIN_TMP_SHELL."
}
probe

ensure_uploaded() {
  local want have
  want="$(md5sum "$PS1" | cut -d' ' -f1)"
  have="$(rsh "md5sum '$SHELL_PS1' 2>/dev/null | cut -d' ' -f1" 2>/dev/null | tr -d '\r\n')"
  if [ "$want" != "$have" ]; then
    cat "$PS1" | rsh "cat > '$SHELL_PS1'" 2>/dev/null || die "upload to $SHELL_PS1 failed"
  fi
}

run_ps() { rsh "'$WIN_POWERSHELL' -NoProfile -ExecutionPolicy Bypass -File '$REMOTE_PS1' $*"; }

case "${1:-}" in ''|-h|--help|help) usage 0 ;; esac
cmd="$1"; shift

case "$cmd" in
  list)
    ensure_uploaded
    run_ps -List
    ;;

  screen)
    ensure_uploaded
    run_ps -Screen
    ;;

  shot)
    sub="${1:-}"; out="${2:-winshot.png}"; pad="${3:-0}"
    [ -n "$sub" ] || usage 1
    case "$pad" in ''|*[!0-9]*) die "pad must be a non-negative integer, got '$pad'" ;; esac
    ensure_uploaded
    rsh "rm -f '$SHELL_PNG'" >/dev/null 2>&1 || true
    out_remote="$(run_ps "-Title '$sub' -Out '$REMOTE_PNG' -Pad $pad")"
    printf '%s\n' "$out_remote"
    case "$out_remote" in
      *"SAVED|"*) ;;
      *) die 2 "remote capture did not report a saved file (see output above)" ;;
    esac
    if ! rsh "cat '$SHELL_PNG'" > "$out" 2>/dev/null || [ ! -s "$out" ]; then
      rm -f "$out"
      die 2 "could not pull $SHELL_PNG (remote said it saved it, so the path mapping is probably off)"
    fi
    echo "wrote $out ($(wc -c < "$out") bytes)"
    rsh "rm -f '$SHELL_PNG'" >/dev/null 2>&1 || true
    ;;

  *) die "unknown command '$cmd' (list | screen | shot)" ;;
esac
