# Nuvio settings snapshot (read from the box, 2026-11-28)

Nuvio keeps its settings in private app storage (no root = no file export), so these are written down to redo by hand.
Launcher `com.nuvio.tv.launcher` 1.2.4 is the one in daily use (signed in to a Nuvio account; addons sync through it).
The separate app `com.nuvio.tv` 1.1.1 is not signed in and is not used.

| Where | Setting | Value |
|---|---|---|
| Settings > Playback > Player | Default player / engine | Internal / ExoPlayer |
| Settings > Playback > Player | Auto-switch engine on startup error | Off |
| Settings > Playback > Subtitles | Preferred language | English |
| Settings > Playback > Subtitles | Secondary language | Not set |
| Settings > Playback > Subtitles | Auto Sync Subtitles | On |
| Settings > Playback > Subtitles | Strip SDH | Off |
| Settings > Content & Discovery > Addons | Installed addons | see `addons.json` |

## Not possible
"Addon Subtitle Startup = Preferred only" does not exist in launcher 1.2.4 or Nuvio 1.1.1 (checked the app strings and the launcher's settings search).
Closest: Preferred language = English (already set) and "Show Only Preferred Languages" (left Off).

## Key Mapper 4.7.1 (key maps, do not break)
Home (Xiaomi RC Consumer Control, expert) -> Open Nuvio (currently disabled/greyed)
Button 3 -> Open SmartTube; Button 6 -> Open Nuvio; Button 7 -> Open Nuvio.
Needs its accessibility service on (set-home.sh does this). Export from inside Key Mapper (menu > Back up) to keep a copy; not automated.
