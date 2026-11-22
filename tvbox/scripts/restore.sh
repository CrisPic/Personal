#!/usr/bin/env bash
# Undo what cleanup.sh changed.
#
#   ./restore.sh <box-ip>                 undo the most recent cleanup run on this box
#   ./restore.sh <box-ip> <backup-folder> undo a specific run
set -u
. "$(dirname "$0")/lib.sh"

require_adb
connect_box "${1:-}"

SERIAL="$(sh_box getprop ro.serialno)"; [ -n "$SERIAL" ] || SERIAL="${DEVICE%%:*}"
BACKUP_DIR="${2:-}"
if [ -z "$BACKUP_DIR" ]; then
  BACKUP_DIR="$(ls -d "$BACKUP_ROOT/$SERIAL"/*/ 2>/dev/null | sort | tail -1)"
fi
CHANGES="${BACKUP_DIR%/}/changes.log"
[ -f "$CHANGES" ] || die "No cleanup backup found for this box (looked in $BACKUP_ROOT/$SERIAL)."
info "Undoing changes from $CHANGES"

# Undo in reverse order.
tail -r "$CHANGES" 2>/dev/null > /tmp/tvbox-restore.$$ || tac "$CHANGES" > /tmp/tvbox-restore.$$
while read -r type name old; do
  case "$type" in
    pkg)
      if [ "$old" = "uninstall" ]; then
        sh_box cmd package install-existing "$name" | grep -q -i "installed" \
          || sh_box pm install-existing "$name" >/dev/null
      else
        sh_box pm enable "$name" >/dev/null
      fi
      is_disabled "$name" && warn "still off: $name" || ok "turned back on  $name"
      ;;
    setting)
      ns="${name%%/*}"; key="${name#*/}"
      if [ "$old" = "null" ] || [ -z "$old" ]; then
        sh_box settings delete "$ns" "$key" >/dev/null
      else
        sh_box settings put "$ns" "$key" "$old" >/dev/null
      fi
      ok "$key restored to $old"
      ;;
  esac
done < /tmp/tvbox-restore.$$
rm -f /tmp/tvbox-restore.$$
mv "$CHANGES" "$CHANGES.undone"
ok "Restore finished. Restart the box:  adb -s $DEVICE reboot"
