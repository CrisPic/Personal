#!/usr/bin/env bash
# Get Stremio out of its start-up loop without losing add-ons or settings.
#
#   ./stremio-fix.sh [box-address]
#
# Does what you've been doing by hand: force-stops Stremio and its background
# streaming server, clears app caches (not data: add-ons and settings stay),
# then starts Stremio again. Handy for remote help on the gift box too.
set -u
. "$(dirname "$0")/lib.sh"

PKG=com.stremio.one
require_adb
connect_box "${1:-}"
is_installed "$PKG" || die "Stremio ($PKG) is not installed on this box."

before="$(sh_box dumpsys meminfo "$PKG" 2>/dev/null | awk '/TOTAL PSS/{print int($3/1024); exit}')"
sh_box am force-stop "$PKG" >/dev/null && ok "Stremio stopped${before:+ (it was using ${before} MB)}"
sh_box pm trim-caches 999G >/dev/null && ok "Caches cleared (add-ons and settings kept)"
sleep 1
sh_box monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null && ok "Stremio started again: check the TV"
