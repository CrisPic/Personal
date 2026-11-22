# TV box setup (Xiaomi TV Box S 3rd Gen)

Scripts and notes to make a Xiaomi TV Box S (3rd Gen, Google TV, Android 14) fast, clean and easy to use, and to copy the same setup onto a second box (the Christmas gift).
Everything runs from a Mac over ADB. Nothing needs root, and every change can be undone.

## The plan

1. **Clean up and speed up the box**: `scripts/cleanup.sh` (done)
2. **New home screen**: Kodi with pages for TV, Movies & Series and YouTube, plus remote buttons (`scripts/install-kodi.sh`, `scripts/set-home.sh`)
3. **Fix the content sources**: Stremio stability and subtitles, IPTV channel testing with a TV guide
4. **Gift box**: one script to copy the setup, remote help over Tailscale, a short guide for the recipient

---

## Step 1: clean up and speed up

### One-time setup

**On the Mac** (Terminal):

```sh
# Homebrew, if you don't have it: https://brew.sh
brew install android-platform-tools
git clone https://github.com/CrisPic/Personal.git
cd Personal/tvbox
```

**On the box**:

1. Settings → Device Preferences → About → click **Build** 7 times until it says you are a developer.
2. Settings → Device Preferences → **Developer options** → turn on **USB debugging** (on some firmware there is also **Network debugging**: turn it on too).
3. Settings → Network & Internet → your Wi-Fi → note the **IP address** (for example `192.168.1.50`).

**Wireless debugging (Android 11 and newer)**: if Developer options has **Wireless debugging**, use it instead:

1. Turn on **Wireless debugging** and open it.
2. Choose **Pair device with pairing code**, then on the Mac run `adb pair <ip>:<pairing port>` and type the 6-digit code. You only do this once per Mac.
3. Go back to the main Wireless debugging screen and use the IP and port under **IP address & port** with the scripts, e.g. `./scripts/cleanup.sh 192.168.0.168:37245`. This port is different from the pairing port and can change after a restart.

If adb is already connected to just one box, you can also leave the address out: `./scripts/cleanup.sh`.

The first time you connect, the TV shows **"Allow USB debugging?"**. Tick *Always allow from this computer* and press OK.

### Run it

```sh
# 1. Dry run: shows the box's health and what would change. Changes nothing.
./scripts/cleanup.sh 192.168.1.50

# 2. Make the changes
./scripts/cleanup.sh 192.168.1.50 --apply

# 3. Restart the box
adb -s 192.168.1.50:5555 reboot
```

Extra options (add them after `--apply`):

| Option | What it does |
| --- | --- |
| `--optional` | Asks one by one about apps some people still use: official YouTube, Netflix, Prime Video, Chromecast, Google voice search |
| `--dns` | Turns on ad and tracker blocking for the whole box with AdGuard DNS. Needs Android 9 or later; on older firmware the script tells you and you set it on the router instead |

### What it changes

- **Turns off bloat and tracking apps** listed in [`config/packages-safe.txt`](config/packages-safe.txt): feedback and crash reporting, sponsored home screen rows, Ambient mode, Play Games, Play Movies, YouTube Music, sync services, printing, screensavers. Nothing needed for the remote, Wi-Fi, Bluetooth, the Play Store or video playback.
- **Optional apps** in [`config/packages-optional.txt`](config/packages-optional.txt), only with `--optional`, one question each.
- **Lists other Xiaomi apps** it finds without touching them. Never turn off `com.mi.bluetooth` (the remote), `com.xiaomi.tvqs.*` (quick settings panel), `mitv.service`, `com.android.mitv.framework.rro` or `com.xiaomi.mitv.updateservice` (firmware updates).
- **Halves menu animations** (1x to 0.5x): menus feel quicker.
- **Clears app caches**: frees storage; apps keep their data and logins.
- Prints **storage and RAM** before and after, and the apps using the most memory.

The stock home screen is left alone on purpose. It gets replaced in step 2.

Edit the two package lists to add or remove apps. Lines are `package   # description`.

### Undo

```sh
./scripts/restore.sh 192.168.1.50
```

Every run with `--apply` saves a backup in `backups/<box serial>/<date>/` (not uploaded to GitHub). `restore.sh` undoes the latest run on that box; pass a backup folder as the second argument to undo an older one.

### If something goes wrong

- **"adb not found"**: run `brew install android-platform-tools`.
- **"Could not connect"**: with Wireless debugging, make sure you used the port from the main screen, not the pairing port. Otherwise check the box is on the same Wi-Fi, that USB debugging is on, and look at the TV for the *Allow debugging* prompt. Then run the command again.
- **An app you need stopped working**: run `restore.sh`, or turn on just that one app with `adb -s <ip>:5555 shell pm enable <package>`.

---

## Step 2: Kodi home screen and remote buttons

How it fits together:

- **Kodi** is the home screen, with one page each for TV, Movies & Series, and YouTube.
- **Live TV** plays inside Kodi with a TV guide (the IPTV Simple add-on, set up in step 3).
- **Movies & Series** shows rows of posters in Kodi. Picking one opens **Stremio** (with Torrentio), which does the playing.
- **YouTube** opens SmartTube.
- **Key Mapper** makes the remote's Home, YouTube, Netflix, Prime Video and TV+ buttons open the right place.

### Run the scripts

```sh
./scripts/install-kodi.sh   # downloads the right Kodi for the box, installs it, copies config/kodi/* (optional; Android 14 blocks this)
./scripts/set-home.sh       # installs Key Mapper, turns on its permission, sets Kodi as home
```

Both can be run again safely. `restore.sh` undoes the most recent run, so run it once to undo `set-home.sh`.
Google TV's own home screen stays installed as a fallback.

### Set up Kodi (once, on the TV, about 10 minutes)

**Tip: type from the Mac.** When a Kodi text field has its on-screen keyboard open, run `adb shell input text '<text>'` on the Mac and the text appears in the field. For example: `adb shell input text 'https://jurialmunkey.github.io/repository.jurialmunkey/'`. (On the remote, `:` and `/` are under the keyboard's **Symbols** button.)

1. **Allow add-ons from outside Kodi's store**: Settings (gear) → System → Add-ons → turn on **Unknown sources**.
2. **Add the skin's source**: Settings → File manager → Add source → type `https://jurialmunkey.github.io/repository.jurialmunkey/` and name it `jurial`.
3. **Install the repository**: Settings → Add-ons → Install from zip file → `jurial` → `repository.jurialmunkey-*.zip`.
4. **Install the skin**: Add-ons → Install from repository → jurialmunkey Alpha Repository → Look and feel → Skin → **Arctic Horizon 2** → Install, and say *Yes* to keep it. It's built for widgets (rows of posters) and still runs on 2 GB of RAM.
5. **TMDb Helper** (the poster rows: Trending, Popular, Top rated...) is installed automatically with Arctic Horizon 2. Nothing to do. Don't try to replace it with a newer version: the skin depends on the one it installs.
6. **Turn on IPTV Simple** (it comes built into Kodi on Android, switched off): Settings → Add-ons → **My add-ons** → PVR clients → **IPTV Simple Client** → Enable. If you can't find it, use Add-ons → Search → `iptv`. It warns that it isn't set up yet: that's expected, the channels and guide come in step 3.
7. **Build the menu**: Settings → Skin settings → **Customise main menu**. Keep or create these items:
   - **TV** → action *Live TV*, widgets *Channels* and *Recently played channels*.
   - **Movies & Series** → widgets from TMDb Helper (*Trending movies*, *Trending TV shows*, *Popular*). Set the item's own action to **Programs → Android apps → Stremio**.
   - **YouTube** → action: **Programs → Android apps → SmartTube**.
   - Remove the menu items you don't use (Music, Pictures, Games...).

If Arctic Horizon 2 ever feels slow, switch back to Kodi's built-in Estuary skin: Settings → Interface → Skin.

### Remote buttons (Key Mapper)

Open **Key Mapper** on the TV. For each row below, tap **+** → **Record trigger** → press the button on the remote → **Actions** → **Launch app** → pick the app → save.

| Remote button | Opens |
| --- | --- |
| Home | Kodi |
| YouTube | SmartTube |
| Netflix | Stremio (Movies & Series) |
| Prime Video | Stremio (Movies & Series) |
| Xiaomi TV+ | Kodi (TV page) |

Notes:
- On Xiaomi remotes the Home button may arrive as **All apps**. Record whatever Key Mapper shows.
- If a button still opens its original app (Netflix, Prime, TV+), turn that app off with `./scripts/cleanup.sh --apply --optional` and try again. Some buttons are handled before Key Mapper sees them while their app is installed.
- Back up your key maps from Key Mapper's menu (*Back up*). The gift box gets the same file in step 4.

---

## Step 3: fix the content sources

### Live TV: test the channels and add a guide

`iptv/check_iptv.py` tests every channel the way a player would. For HLS streams it follows the playlist down to an actual video segment. It writes a clean playlist that has only working channels in it. Python 3 comes with the Mac's developer tools; if `python3` is missing, run `brew install python`.

```sh
# Moldova + Russia from Free-TV and iptv-org, with guides; copy the result to the box
python3 iptv/check_iptv.py \
  'https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_moldova.m3u8' \
  'https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_russia.m3u8' \
  'https://iptv-org.github.io/iptv/countries/md.m3u' \
  'https://iptv-org.github.io/iptv/countries/ru.m3u' \
  --epg 'https://epgshare01.online/epgshare01/epg_ripper_MD1.xml.gz' \
  --epg 'https://epgshare01.online/epgshare01/epg_ripper_RU1.xml.gz' \
  --push
```

- Give it any number of playlists (URLs or files). They're merged, and duplicate links are dropped.
- iptv-org has one playlist per country: `https://iptv-org.github.io/iptv/countries/<code>.m3u` (`it`, `ro`, `de`, `es`, ...). The full list (`index.m3u`) has over 10,000 channels and takes a long time to test, so use the countries you watch.
- When a channel name appears in several lists, only the fastest working copy is kept (`--keep-copies` keeps them all).
- `--group News --group Sport` keeps only those groups.
- **Guide:** pass one or more `--epg` guides (repeat the option). Without `--epg`, it uses any guide named in the playlists' own headers. Channels are matched to the guide by `tvg-id`, then by name. It then writes **one small guide** with only your channels, which is much lighter for Kodi on a 2 GB box than a full country guide.
- Output goes to `iptv/output/`:
  - `channels.m3u`: working channels only, sorted by group.
  - `guide.xml.gz`: the small guide.
  - `report.txt`: dead channels and why, slow channels, channels with no guide, totals per group.
- `--push` copies the playlist and the guide to the box's `Download/tvbox/` folder.
- `#EXTVLCOPT` user-agent/referrer lines and `|User-Agent=` URLs are kept, and used while testing.
- Run it again whenever channels stop working. Free channels change often.

**Point Kodi at it (once):**

1. Let Kodi read the Download folder: `adb shell pm grant org.xbmc.kodi android.permission.READ_EXTERNAL_STORAGE`
2. In Kodi: Settings → Add-ons → My add-ons → PVR clients → IPTV Simple Client → **Configure**:
   - *General* → Location **Local path** → `/storage/emulated/0/Download/tvbox/channels.m3u`
   - *EPG* → Location **Local path** → `/storage/emulated/0/Download/tvbox/guide.xml.gz`
3. Restart Kodi. Channels and the guide appear under **TV**.

### Stremio

- **Start-up loop:** run `./scripts/stremio-fix.sh`. It force-stops Stremio and its streaming server, clears caches (your add-ons and settings stay), and starts it again. It works from a distance too, once step 4 is done.
- **Slow torrent streams:** open `https://torrentio.strem.fun/configure` on the Mac or a phone and set:
  - **Sorting:** *By seeders*. More seeders means faster start and fewer stalls.
  - **Exclude qualities:** *4K*, *Remux*, *HDR/DV*, *3D*, *CAM/Screener*. Huge 4K files stream badly on a 2 GB box, and CAM copies are poor.
  - **Max results per quality:** *3*.
  - Then **Install**, or copy the link and paste it into Stremio's add-on search on the box (send it from the Mac with `adb shell input text '<link>'`).
- **Streaming cache:** in Stremio → Settings → Streaming, set **Caching** to *5 GB*. The box has more than 20 GB free, and a bigger cache helps when the connection dips.
- **Subtitles out of sync:** subtitles only match a specific release of the film.
  - Install the **OpenSubtitles v3** add-on from Stremio's add-on catalogue.
  - In the player, choose subtitles whose name matches the stream's release name (for example both say *YTS* or *WEB-DL*). Those are timed for that exact file.
  - If none match, use the subtitle **delay** setting in the player (± in 0.25 s steps), or pick a different stream with the same release name as a good subtitle.
