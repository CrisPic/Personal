#!/usr/bin/env bash
# Shared helpers for the TV box scripts. Written for macOS bash 3.2 (no bash 4 features).

TVBOX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="$TVBOX_DIR/config"
BACKUP_ROOT="$TVBOX_DIR/backups"

if [ -t 1 ]; then
  C_RED=$'\033[31m'; C_GRN=$'\033[32m'; C_YEL=$'\033[33m'; C_DIM=$'\033[2m'; C_OFF=$'\033[0m'
else
  C_RED=""; C_GRN=""; C_YEL=""; C_DIM=""; C_OFF=""
fi

info() { printf '%s\n' "$*"; }
ok()   { printf '%s✓%s %s\n' "$C_GRN" "$C_OFF" "$*"; }
warn() { printf '%s!%s %s\n' "$C_YEL" "$C_OFF" "$*"; }
die()  { printf '%s✗ %s%s\n' "$C_RED" "$*" "$C_OFF" >&2; exit 1; }

require_adb() {
  command -v adb >/dev/null 2>&1 || die "adb not found. Install it with:  brew install android-platform-tools"
}

# connect_box <ip[:port]>  -> sets DEVICE (serial used for every adb call)
connect_box() {
  local target="$1"
  [ -n "$target" ] || die "Give the box IP address, e.g.  $0 192.168.1.50"
  case "$target" in *:*) ;; *) target="$target:5555" ;; esac
  info "Connecting to $target ..."
  adb connect "$target" >/dev/null 2>&1
  local state
  state="$(adb -s "$target" get-state 2>/dev/null)"
  if [ "$state" != "device" ]; then
    die "Could not connect to $target (state: ${state:-none}).
  - Is the box on and on the same Wi-Fi as this Mac?
  - Is 'USB debugging' / 'Network debugging' on in Developer options?
  - Look at the TV: you may need to accept the 'Allow debugging?' prompt, then run this again."
  fi
  DEVICE="$target"
  ok "Connected: $(sh_box getprop ro.product.model) (Android $(sh_box getprop ro.build.version.release))"
}

# Run a shell command on the box, stripping the CR that old adb versions add.
sh_box() { adb -s "$DEVICE" shell "$@" 2>&1 | tr -d '\r'; }

is_installed() { sh_box pm list packages "$1" | grep -qx "package:$1"; }

is_disabled() { sh_box pm list packages -d "$1" | grep -qx "package:$1"; }

# Print "package" lines from a list file, ignoring comments and blanks.
read_list() { sed -e 's/#.*//' -e 's/[[:space:]]*$//' -e '/^[[:space:]]*$/d' "$1"; }

# Print the comment of a package in a list file.
describe() { grep -E "^$1[[:space:]]" "$2" | sed -e 's/^[^#]*#[[:space:]]*//' | head -1; }

ask() { # ask "question"  -> returns 0 for yes
  local reply
  printf '%s [y/N] ' "$1"
  read -r reply </dev/tty
  case "$reply" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}
