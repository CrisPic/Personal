# Live TV for Nuvio TV Launcher

- `my-channels.m3u`: the 129 Moldova/Russia channels Cristian picked on 2026-11-28 from the 275 that passed `iptv/check_iptv.py` (tested from home in Italy). Guide links are in the header (`url-tvg`), and each channel's `tvg-id` matches those guides.
- Add it in the launcher: Settings → Live TV → Add M3U Playlist, address
  `raw.githubusercontent.com/CrisPic/Personal/main/tvbox/livetv/my-channels.m3u` (HTTPS on).
  If the guide doesn't fill, add EPG sources `http://epg.it999.ru/epg.xml.gz` and `https://iptvx.one/epg/epg_lite.xml.gz`.
- Refresh: re-run the checker, then rebuild this file from the picks.

`../config/nuvio-collections.json` is the "Streaming services" collection (Netflix, Prime Video, Disney+, Apple TV+, NOW, Paramount+; TMDB, region IT). Put it in the box's Download folder and use Settings → Collections → Import.
