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

# Serials of devices adb is connected to and authorised on.
connected_devices() { adb devices 2>/dev/null | tr -d '\r' | awk 'NR>1 && $2=="device"{print $1}'; }

# connect_box [ip[:port]]  -> sets DEVICE (serial used for every adb call)
# With no argument, uses the only box adb is already connected to.
connect_box() {
  local target="$1" out state found count
  if [ -z "$target" ]; then
    count="$(connected_devices | wc -l | tr -d ' ')"
    [ "$count" = 1 ] || die "Give the box address, e.g.  $0 192.168.1.50:37245
  (adb is connected to $count devices right now; see: adb devices)"
    target="$(connected_devices)"
  else
    case "$target" in *:*) ;; *) target="$target:5555" ;; esac
    info "Connecting to $target ..."
    out="$(adb connect "$target" 2>&1 | tr -d '\r')"
    state="$(adb -s "$target" get-state 2>/dev/null | tr -d '\r')"
    if [ "$state" != "device" ]; then
      # Wireless debugging may already have connected the box under another name
      # (e.g. adb-XXXX._adb-tls-connect._tcp). Use it if it's the only box connected.
      found="$(connected_devices | grep -F "${target%%:*}" | head -1)"
      [ -n "$found" ] || { [ "$(connected_devices | wc -l | tr -d ' ')" = 1 ] && found="$(connected_devices)"; }
      if [ -n "$found" ]; then
        warn "Using the box adb is already connected to: $found"
        target="$found"
      else
        die "Could not connect to $target.
  adb said: ${out:-nothing}
  - Wireless debugging: use the IP and port on the MAIN Wireless debugging screen,
    not the port on the 'Pair device with pairing code' screen. Pair once first with:  adb pair <ip:pairing-port>
  - Is the box on and on the same Wi-Fi as this Mac?
  - Look at the TV: you may need to accept the 'Allow debugging?' prompt, then run this again."
      fi
    fi
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
