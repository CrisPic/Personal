#!/usr/bin/env bash
# Copy the Nuvio setup (addons + collections) onto a box, e.g. the gift box.
#
#   ./restore-nuvio.sh [box-address] [--apply]
#
# Dry run by default. Installs addons from config/nuvio/addons.json into the Nuvio launcher through its
# stremio:// link (same as typing the URL in Settings > Content & Discovery > Addons; already-installed addons are not duplicated),
# and copies collections.json to the box's Download folder.
# Nothing is removed. Needs the Nuvio launcher installed and opened once. Sign in to a Nuvio account on the box
# first if you want addons to sync, or use this script instead.
set -u
. "$(dirname "$0")/lib.sh"

APPLY=0; ADDR=""
for a in "$@"; do case "$a" in --apply) APPLY=1 ;; *) ADDR="$a" ;; esac; done
PKG=com.nuvio.tv.launcher; ACT=$PKG/com.nuvio.tv.MainActivity
JSON="$CONFIG_DIR/nuvio/addons.json"; COLL="$CONFIG_DIR/nuvio/collections.json"

require_adb
connect_box "$ADDR"
is_installed "$PKG" || die "Nuvio launcher ($PKG) is not installed on this box."

URLS="$(python3 -I -c 'import json,sys
for a in json.load(open(sys.argv[1]))["addons"]:
    if not a.get("builtin"): print(a["name"]+"\t"+a["manifest"])' "$JSON")"

printf '%s\n' "$URLS" | while IFS="$(printf '\t')" read -r name url; do
  [ -n "$url" ] || continue
  if [ $APPLY = 1 ]; then
    # single-quote the link: adb shell would otherwise treat the | in Torrentio's URL as a pipe
    sh_box "am start -W -a android.intent.action.VIEW -d 'stremio://${url#https://}' -n $ACT" >/dev/null </dev/null
    ok "Install sent: $name"; sleep 6
  else
    info "would install: $name"
  fi
done

if [ $APPLY = 1 ]; then
  adb -s "$DEVICE" push "$COLL" /sdcard/Download/nuvio-collections.json >/dev/null
  ok "Collections copied to Download/nuvio-collections.json (import: Settings > Content & Discovery > Addons > Collections)"
  info "Check Settings > Content & Discovery > Addons on the TV. Then set Settings > Playback > Subtitles > Preferred language = English (see config/nuvio/settings.md)."
else
  info "Dry run. Add --apply to do it."
fi
