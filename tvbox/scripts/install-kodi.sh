#!/usr/bin/env bash
# Step 2a: install Kodi on the box and give it a starting setup.
#
#   ./install-kodi.sh [box-address]
#
# Downloads the latest stable Kodi for the box's processor from mirrors.kodi.tv,
# installs it, starts it once so it creates its folders, then copies in the
# files from config/kodi/ (favourites that open SmartTube, Stremio, etc.).
# Safe to run again: it updates Kodi and re-copies the files, keeping your settings.
set -u
. "$(dirname "$0")/lib.sh"

KODI_PKG=org.xbmc.kodi
MIRROR=https://mirrors.kodi.tv/releases/android
CACHE_DIR="$TVBOX_DIR/.downloads"

require_adb
connect_box "${1:-}"

# ---------------------------------------------------------------- pick the right build
ABIS="$(sh_box getprop ro.product.cpu.abilist)"
case "$ABIS" in
  *arm64-v8a*) ARCH=arm64-v8a ;;
  *armeabi-v7a*) ARCH=arm ;;
  *) die "Unexpected processor type: $ABIS" ;;
esac
info "Processor: $ABIS -> using Kodi build '$ARCH'"

APK_NAME="$(curl -fsSL "$MIRROR/$ARCH/" | grep -oE 'kodi-[0-9]+\.[0-9]+(\.[0-9]+)?-[A-Za-z]+-[a-z0-9-]+\.apk' \
  | grep -v dbg | sort -u | sort -t- -k2,2V | tail -1)"
[ -n "$APK_NAME" ] || die "Could not find a Kodi download at $MIRROR/$ARCH/ (check the Mac's internet connection)."
info "Latest stable Kodi: $APK_NAME"

INSTALLED="$(sh_box dumpsys package $KODI_PKG | awk -F= '/versionName/{print $2; exit}')"
[ -n "$INSTALLED" ] && info "Installed now: Kodi $INSTALLED"

mkdir -p "$CACHE_DIR"
if [ ! -s "$CACHE_DIR/$APK_NAME" ]; then
  info "Downloading..."
  curl -fL --progress-bar -o "$CACHE_DIR/$APK_NAME.part" "$MIRROR/$ARCH/$APK_NAME" \
    && mv "$CACHE_DIR/$APK_NAME.part" "$CACHE_DIR/$APK_NAME" || die "Download failed."
fi

info "Installing (takes a minute)..."
out="$(adb -s "$DEVICE" install -r "$CACHE_DIR/$APK_NAME" 2>&1 | tr -d '\r' | tail -1)"
case "$out" in *Success*) ok "Kodi installed" ;; *) die "Install failed: $out" ;; esac

# ---------------------------------------------------------------- first start
KODI_HOME=/sdcard/Android/data/$KODI_PKG/files/.kodi
USERDATA=$KODI_HOME/userdata
has_userdata() { sh_box ls "$USERDATA/guisettings.xml" | grep -q "^/.*guisettings.xml$"; }
if ! has_userdata; then
  info "Starting Kodi once so it creates its folders (watch the TV)..."
  sh_box monkey -p $KODI_PKG -c android.intent.category.LAUNCHER 1 >/dev/null
  i=0
  until has_userdata; do
    i=$((i+1)); [ $i -gt 60 ] && die "Kodi did not finish its first start. Open Kodi on the TV once, wait for its home screen, then run this again."
    sleep 2
  done
  sleep 3
fi
sh_box am force-stop $KODI_PKG >/dev/null

# ---------------------------------------------------------------- copy config
info "Copying Kodi settings from config/kodi/ ..."
for f in "$CONFIG_DIR"/kodi/*.xml; do
  [ -e "$f" ] || continue
  adb -s "$DEVICE" push "$f" "$USERDATA/$(basename "$f")" >/dev/null && ok "  $(basename "$f")"
done

ok "Kodi is ready. Open it on the TV and follow 'Step 2: set up Kodi' in the README."
