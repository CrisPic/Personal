#!/usr/bin/env bash
# Step 2b: make Kodi the home screen and get the remote buttons ready for remapping.
#
#   ./set-home.sh [box-address]
#
# 1. Installs Key Mapper (free, open source) from its GitHub releases.
# 2. Turns on Key Mapper's accessibility service, which it needs to catch remote buttons.
# 3. Sets Kodi as the default home app, if the system allows it.
# Every change is logged so restore.sh can undo it. Google TV's own home is NOT turned off.
set -u
. "$(dirname "$0")/lib.sh"

KODI_PKG=org.xbmc.kodi
KM_PKG=io.github.sds100.keymapper
KM_RELEASES=https://api.github.com/repos/keymapperorg/KeyMapper/releases/latest
CACHE_DIR="$TVBOX_DIR/.downloads"

require_adb
connect_box "${1:-}"
is_installed "$KODI_PKG" || die "Kodi is not installed yet. Run ./scripts/install-kodi.sh first."

SERIAL="$(sh_box getprop ro.serialno)"; [ -n "$SERIAL" ] || SERIAL="${DEVICE%%:*}"
BACKUP_DIR="$BACKUP_ROOT/$SERIAL/$(date +%Y%m%d-%H%M%S)-home"
CHANGES="$BACKUP_DIR/changes.log"
mkdir -p "$BACKUP_DIR"; : > "$CHANGES"

# ---------------------------------------------------------------- Key Mapper
if is_installed "$KM_PKG"; then
  ok "Key Mapper already installed"
else
  info "Finding the latest Key Mapper release..."
  url="$(curl -fsSL "$KM_RELEASES" | grep -oE '"browser_download_url": *"[^"]+\.apk"' | sed 's/.*"\(http[^"]*\)"/\1/' \
    | grep -vi debug | awk '/foss/{print; f=1; exit} {a[NR]=$0} END{if(!f) print a[1]}')"
  [ -n "$url" ] || die "Could not find a Key Mapper APK at $KM_RELEASES"
  mkdir -p "$CACHE_DIR"; apk="$CACHE_DIR/$(basename "$url")"
  [ -s "$apk" ] || curl -fL --progress-bar -o "$apk" "$url" || die "Download failed: $url"
  out="$(adb -s "$DEVICE" install -r "$apk" 2>&1 | tr -d '\r' | tail -1)"
  case "$out" in *Success*) ok "Key Mapper installed ($(basename "$apk"))" ;; *) die "Install failed: $out" ;; esac
  echo "installed $KM_PKG -" >> "$CHANGES"
fi

# Find Key Mapper's accessibility service name instead of guessing it.
SERVICE="$(sh_box dumpsys package "$KM_PKG" | grep -oE "$KM_PKG/[A-Za-z0-9_.]*AccessibilityService" | head -1)"
[ -n "$SERVICE" ] || die "Could not find Key Mapper's accessibility service. Open Key Mapper once on the TV and run this again."

OLD_LIST="$(sh_box settings get secure enabled_accessibility_services)"
case ":$OLD_LIST:" in
  *":$SERVICE:"*) ok "Key Mapper accessibility already on" ;;
  *)
    if [ "$OLD_LIST" = "null" ] || [ -z "$OLD_LIST" ]; then NEW_LIST="$SERVICE"; else NEW_LIST="$OLD_LIST:$SERVICE"; fi
    sh_box settings put secure enabled_accessibility_services "$NEW_LIST" >/dev/null
    echo "setting secure/enabled_accessibility_services $OLD_LIST" >> "$CHANGES"
    old_on="$(sh_box settings get secure accessibility_enabled)"
    sh_box settings put secure accessibility_enabled 1 >/dev/null
    echo "setting secure/accessibility_enabled $old_on" >> "$CHANGES"
    ok "Key Mapper accessibility turned on"
    ;;
esac
# Keep Key Mapper running in the background so buttons always work.
sh_box cmd deviceidle whitelist +"$KM_PKG" >/dev/null 2>&1 && ok "Key Mapper excluded from battery/memory saving"

# ---------------------------------------------------------------- Kodi as home
HOME_QUERY="-a android.intent.action.MAIN -c android.intent.category.HOME"
OLD_HOME="$(sh_box cmd package resolve-activity --brief $HOME_QUERY | tail -1)"
KODI_HOME_ACT="$(sh_box cmd package query-activities --brief $HOME_QUERY | grep "^ *$KODI_PKG/" | head -1 | tr -d ' ')"
if [ -n "$KODI_HOME_ACT" ]; then
  if sh_box cmd package set-home-activity --user 0 "$KODI_HOME_ACT" | grep -qi success; then
    echo "home - $OLD_HOME" >> "$CHANGES"
    ok "Kodi is now the default home app (was: $OLD_HOME)"
  else
    warn "The system refused to change the home app. Key Mapper will handle the Home button instead."
  fi
else
  info "Kodi doesn't register as a home app on this box: Key Mapper will open Kodi when you press Home."
fi

# ---------------------------------------------------------------- report
info ""
info "Apps the remote buttons will open:"
for p in org.smarttube.stable org.smarttube.beta com.teamsmart.videomanager.tv com.liskovsoft.smarttubetv.beta com.stremio.one $KODI_PKG; do
  is_installed "$p" && info "  ✓ $p"
done
info ""
ok "Done. $(wc -l < "$CHANGES" | tr -d ' ') changes saved in $CHANGES"
info "Next: open Key Mapper on the TV and set up the buttons (README, 'Remote buttons')."
info "To undo:  ./scripts/restore.sh $DEVICE \"$BACKUP_DIR\""
