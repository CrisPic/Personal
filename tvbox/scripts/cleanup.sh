#!/usr/bin/env bash
# Step 1: debloat and speed up a Xiaomi Mi Box 3 (or any Android TV box) over ADB.
#
#   ./cleanup.sh <box-ip>                 dry run: shows what would change, changes nothing
#   ./cleanup.sh <box-ip> --apply         makes the changes
#   ./cleanup.sh <box-ip> --apply --optional   also asks about optional apps (YouTube, Netflix, voice...)
#   ./cleanup.sh <box-ip> --apply --dns   also turns on ad/tracker-blocking DNS (Android 9+ only)
#
# Every change is written to backups/<box>/<date>/ so restore.sh can undo it.
set -u
. "$(dirname "$0")/lib.sh"

APPLY=0; OPTIONAL=0; DNS=0; TARGET=""
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --optional) OPTIONAL=1 ;;
    --dns) DNS=1 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    -*) die "Unknown option: $arg" ;;
    *) TARGET="$arg" ;;
  esac
done

require_adb
connect_box "$TARGET"

SDK="$(sh_box getprop ro.build.version.sdk)"
SERIAL="$(sh_box getprop ro.serialno)"; [ -n "$SERIAL" ] || SERIAL="${DEVICE%%:*}"
BACKUP_DIR="$BACKUP_ROOT/$SERIAL/$(date +%Y%m%d-%H%M%S)"
CHANGES="$BACKUP_DIR/changes.log"   # one line per change: <type> <name> <old value / method>

if [ "$APPLY" = 1 ]; then
  mkdir -p "$BACKUP_DIR"
  sh_box pm list packages    | sort > "$BACKUP_DIR/packages-all.txt"
  sh_box pm list packages -d | sort > "$BACKUP_DIR/packages-disabled-before.txt"
  : > "$CHANGES"
  ok "Backup folder: $BACKUP_DIR"
else
  warn "DRY RUN: nothing will be changed. Add --apply to make the changes."
fi

# ---------------------------------------------------------------- health report
info ""
info "== Box health before =="
sh_box df -h /data | tail -1 | awk '{print "Storage free: " $4 " of " $2}'
sh_box cat /proc/meminfo | awk '/MemTotal/{t=$2} /MemAvailable/{a=$2} END{printf "RAM free: %d MB of %d MB\n", a/1024, t/1024}'
info "Biggest memory users right now:"
sh_box dumpsys meminfo 2>/dev/null | awk '/Total PSS by process/{f=1;next} f&&/^$/{exit} f{print "  " $0}' | head -8

# ---------------------------------------------------------------- packages
turn_off() { # turn_off <package> <description>
  local pkg="$1" desc="$2" out
  if [ "$APPLY" = 0 ]; then info "  would turn off  $pkg  ${C_DIM}($desc)${C_OFF}"; return; fi
  out="$(sh_box pm disable-user --user 0 "$pkg")"
  if printf '%s' "$out" | grep -q "new state: disabled"; then
    echo "pkg $pkg disable" >> "$CHANGES"; ok "turned off  $pkg"
    return
  fi
  # Some system apps refuse to be disabled: hide them for user 0 instead (still reversible).
  out="$(sh_box pm uninstall -k --user 0 "$pkg")"
  if printf '%s' "$out" | grep -q "Success"; then
    echo "pkg $pkg uninstall" >> "$CHANGES"; ok "removed for this user  $pkg"
  else
    warn "could not turn off $pkg: $out"
  fi
}

process_list() { # process_list <file> <interactive 0/1>
  local file="$1" interactive="$2" pkg desc
  for pkg in $(read_list "$file"); do
    is_installed "$pkg" || continue
    if is_disabled "$pkg"; then info "  ${C_DIM}already off  $pkg${C_OFF}"; continue; fi
    desc="$(describe "$pkg" "$file")"
    if [ "$interactive" = 1 ] && [ "$APPLY" = 1 ]; then
      ask "Turn off $pkg ($desc)?" || continue
    fi
    turn_off "$pkg" "$desc"
  done
}

info ""
info "== Bloat and tracking apps =="
process_list "$CONFIG_DIR/packages-safe.txt" 0

if [ "$OPTIONAL" = 1 ]; then
  info ""
  info "== Optional apps =="
  process_list "$CONFIG_DIR/packages-optional.txt" 1
fi

info ""
info "== Vendor apps found (not touched, listed so you can review them) =="
sh_box pm list packages | sed 's/^package://' | grep -Ei 'xiaomi|mitv|miui|com\.mi\.' | sort | sed 's/^/  /'

# ---------------------------------------------------------------- settings
set_setting() { # set_setting <namespace> <key> <value>
  local ns="$1" key="$2" val="$3" old
  old="$(sh_box settings get "$ns" "$key")"
  if [ "$old" = "$val" ]; then info "  ${C_DIM}already set  $key = $val${C_OFF}"; return; fi
  if [ "$APPLY" = 0 ]; then info "  would set  $key: $old -> $val"; return; fi
  sh_box settings put "$ns" "$key" "$val" >/dev/null
  echo "setting $ns/$key $old" >> "$CHANGES"; ok "$key: $old -> $val"
}

info ""
info "== Faster menus =="
set_setting global window_animation_scale 0.5
set_setting global transition_animation_scale 0.5
set_setting global animator_duration_scale 0.5

if [ "$DNS" = 1 ]; then
  info ""
  info "== Ad and tracker blocking DNS =="
  if [ "${SDK:-0}" -ge 28 ]; then
    set_setting global private_dns_mode hostname
    set_setting global private_dns_specifier dns.adguard-dns.com
  else
    warn "Android SDK $SDK is older than Android 9: Private DNS is not available. Set DNS on the router instead."
  fi
fi

# ---------------------------------------------------------------- caches
info ""
info "== Clear app caches =="
if [ "$APPLY" = 1 ]; then
  sh_box pm trim-caches 999G >/dev/null && ok "app caches cleared (apps keep their data and logins)"
else
  info "  would clear all app caches"
fi

info ""
if [ "$APPLY" = 1 ]; then
  sh_box df -h /data | tail -1 | awk '{print "Storage free now: " $4 " of " $2}'
  ok "Done. $(wc -l < "$CHANGES" | tr -d ' ') changes saved in $CHANGES"
  info "Restart the box to free all memory:  adb -s $DEVICE reboot"
  info "To undo everything:  ./scripts/restore.sh $DEVICE"
else
  info "Dry run finished. Run again with --apply to make these changes."
fi
