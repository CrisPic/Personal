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
./scripts/install-kodi.sh   # downloads the right Kodi for the box, installs it, copies config/kodi/*
./scripts/set-home.sh       # installs Key Mapper, turns on its permission, sets Kodi as home
```

Both can be run again safely. `restore.sh` undoes the most recent run, so run it once to undo `set-home.sh`.
Google TV's own home screen stays installed as a fallback.

### Set up Kodi (once, on the TV, about 10 minutes)

1. **Allow add-ons from outside Kodi's store**: Settings (gear) → System → Add-ons → turn on **Unknown sources**.
2. **Add the skin's source**: Settings → File manager → Add source → type `https://jurialmunkey.github.io/repository.jurialmunkey/` and name it `jurial`.
3. **Install the repository**: Settings → Add-ons → Install from zip file → `jurial` → `repository.jurialmunkey-*.zip`.
4. **Install the skin**: Add-ons → Install from repository → jurialmunkey Alpha Repository → Look and feel → Skin → **Arctic Horizon 2** → Install, and say *Yes* to keep it. It's built for widgets (rows of posters) and still runs on 2 GB of RAM.
5. **Install TMDb Helper**: same repository → Video add-ons → **TMDb Helper**. It provides the poster rows (Trending, Popular, Top rated...).
6. **Install IPTV Simple**: Add-ons → Install from repository → Kodi Add-on repository → PVR clients → **PVR IPTV Simple Client**. We'll give it your channels and guide in step 3.
7. **Build the menu**: Settings → Skin settings → **Customise main menu**. Keep or create these items:
   - **TV** → action *Live TV*, widgets *Channels* and *Recently played channels*.
   - **Movies & Series** → widgets from TMDb Helper (*Trending movies*, *Trending TV shows*, *Popular*). Set the item's own action to the favourite *Movies & Series (Stremio)*.
   - **YouTube** → action: favourite *YouTube (SmartTube)*.
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
