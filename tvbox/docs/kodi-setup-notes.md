# Kodi setup over adb: what worked

Recorded while setting up Cristian's box on 2026-11-22: Xiaomi TV Box S 3rd Gen, Android 14, Kodi 21.3, Arctic Horizon 2 0.8.30.
These notes are the basis for scripting the gift box.

## Basics

- **JSON-RPC:** run `adb forward tcp:9090 tcp:9090`, then send raw JSON over TCP to 127.0.0.1:9090. No auth is needed.
- **Screen:** `adb exec-out screencap -p > s.png`
- **Keys:** `adb shell input keyevent DPAD_UP|DOWN|LEFT|RIGHT|CENTER|BACK`
- **Kodi's settings folder:** adb shell can **read** `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/userdata/addon_data` but **not write** it (permission denied on Android 14). So settings have to go through Kodi's own screens.
- **Typing into any Kodi keyboard:** `Input.SendText {"text":"...","done":false}` replaces the field's text, and `"done":true` also confirms it. Much easier than `adb shell input text`.

## Checks (JSON-RPC)

- `Settings.GetSettingValue {"setting":"lookandfeel.skin"}` returns `skin.arctic.horizon.2`.
- `Addons.GetAddonDetails {"addonid":"pvr.iptvsimple","properties":["enabled","version"]}`
- `Settings.GetSettingValue {"setting":"lookandfeel.startupwindow"}` returns `10000` (Home), which is correct.
- `PVR.GetChannels {"channelgroupid":"alltv","limits":{"end":3}}` reports the total channel count after setup and a restart.

## Main menu (Skin settings > Menus > Customise home menu)

Open it with `GUI.ActivateWindow {"window":"skinsettings"}`, then RIGHT RIGHT, CENTER.

**Moving around the editor:**
- UP/DOWN moves between items.
- LEFT cycles the row buttons: X (delete), + (add), up, down.
- RIGHT ×4 from the row goes into the right panel. Its rows are Disable, Choose item, Action, Label, Icon, Submenu, Widgets...

**Editing an item:**
- **Action:** CENTER on Action → "Choose item for menu" → Custom item (8 × DOWN, CENTER) → `Input.SendText` the action → CENTER (Done).
- **Label:** DOWN to Label, CENTER, then `Input.SendText {"text":"<label>","done":true}`.

**Final items:**

| Item | Action | Widgets |
| --- | --- | --- |
| TV | `ActivateWindow(TVChannels)` | Default Widgets → Live TV → All channels (`pvr://channels/tv/*`) and Last played (`pvr://channels/tv/*?view=lastplayed`). The 3rd default widget is set to Disable. |
| Movies & Series | `StartAndroidActivity(com.stremio.one)` | TMDb Helper Trending movies, Trending TV, Popular (`plugin://plugin.video.themoviedb.helper/?info=trending_week&tmdb_type=movie\|tv`, `info=popular`) |
| YouTube | `StartAndroidActivity(org.smarttube.stable)` | none |

- Music, Videos and the empty `<None>` items were deleted.
- The skin's own "Live TV" item only appears once PVR has channels. It's set to Disable.
- All of this is saved to `addon_data/script.skinshortcuts/skin.arctic.horizon.2-mainmenu.DATA.xml`, plus the `-tv` and `-movies-series` widget files. For the gift box it may be faster to copy these DATA.xml files in through Kodi's file manager, since adb can't write there.

## IPTV Simple Client

1. `GUI.ActivateWindow {"window":"addonbrowser","parameters":["addons://user/kodi.pvrclient/"]}`, then RIGHT, CENTER (PVR clients).
2. `Input.ContextMenu` on IPTV Simple Client → Settings (DOWN DOWN CENTER) → edit "Migrated Add-on Config" (CENTER).
3. **General tab:** RIGHT, then DOWN DOWN to Location. CENTER toggles Remote to Local path. DOWN, CENTER opens the file browser:
   - External storage: DOWN, CENTER
   - Download: 7 × DOWN, CENTER (Kodi sorts case-insensitively)
   - tvbox: DOWN DOWN, CENTER
   - channels.m3u: DOWN, CENTER
4. **EPG tab:** LEFT, DOWN DOWN, RIGHT. Location CENTER (switches to Local path), DOWN CENTER, browse the same way, then guide.xml.gz (DOWN DOWN CENTER).
5. RIGHT RIGHT to OK, CENTER.

The result in `instance-settings-1.xml`: `m3uPathType 0`, `m3uPath /storage/emulated/0/Download/tvbox/channels.m3u`, `epgPathType 0`, `epgPath /storage/emulated/0/Download/tvbox/guide.xml.gz`.

**Restarting Kodi:** `Application.Quit`, then `adb shell am start -n org.xbmc.kodi/.Splash`. The first restart after adding channels hung on "Initialising Skin" (window 11198) for over 3 minutes; `GUI.ActivateWindow {"window":"home"}` freed it. The second restart reached Home by itself in about 10 s.

## Refreshing the guide after pushing a new guide.xml.gz

1. **Restart Kodi:** `Application.Quit`, then `adb shell monkey -p org.xbmc.kodi -c android.intent.category.LAUNCHER 1`.
   - IPTV Simple re-reads the file on start (its log says "Loaded '131' EPG channels").
   - Kodi's own guide database only refreshes every `epg.epgupdate` = 120 min, so most channels stay empty until then.
2. **Force the refresh:** `GUI.ActivateWindow {"window":"pvrsettings"}`, RIGHT, DOWN DOWN (Guide), RIGHT, DOWN (Clear data), CENTER, LEFT (Yes), CENTER.
   - Use the Clear data under *Guide*, which clears only the cached guide. The one under *General* wipes all PVR data.
   - Channels showing a programme went from 12 to 129 within seconds.
3. **Check:** `PVR.GetChannels {"channelgroupid":"alltv","properties":["broadcastnow"]}` and count the entries that have `broadcastnow`.

**Guides used (no login):** `https://epg.it999.ru/epg.xml.gz`, `https://iptvx.one/epg/epg_lite.xml.gz` and `https://epgshare01.online/epgshare01/epg_ripper_viva-russia.ru.xml.gz`. They matched 131 of 292 channels.
