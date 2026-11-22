#!/usr/bin/env python3
"""Test every channel in one or more IPTV playlists and write one clean playlist.

    python3 iptv/check_iptv.py <playlist> [<playlist> ...] [--epg <guide> ...] [--push]

What it does:
  * reads the playlists (files or URLs) and merges them, dropping duplicate stream URLs
  * opens every stream like a player would: for HLS (.m3u8) it follows the
    playlist down to the first video segment and downloads a piece of it
  * when the same channel name appears more than once, keeps the fastest working copy
  * writes  output/channels.m3u     only the channels that answered
            output/guide.xml.gz     (with guides) one small guide with only those channels
            output/report.txt       what failed and why, per group
  * guides: pass --epg (repeatable), or the script uses the guide URLs named in the
    playlists' own headers. Channels are matched by tvg-id, then by name.
  * with --push: copies channels.m3u and guide.xml.gz to the box (Download/tvbox/)

Uses only Python's standard library. Run it again any time to refresh the list.
"""
import argparse
import concurrent.futures as cf
import gzip
import io
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

DEFAULT_UA = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
BOX_DIR = "/sdcard/Download/tvbox"


# ------------------------------------------------------------------ playlist parsing
class Channel:
    def __init__(self, extinf, options, url):
        self.extinf = extinf          # the full #EXTINF line
        self.options = options        # #EXTVLCOPT / #KODIPROP lines that belong to it
        self.url = url
        self.name = extinf.rsplit(",", 1)[-1].strip() if "," in extinf else url
        self.group = attr(extinf, "group-title") or "(no group)"
        self.tvg_id = attr(extinf, "tvg-id")
        self.ok = None
        self.reason = ""
        self.ms = 0
        self.epg_id = ""

    def headers(self):
        h = {"User-Agent": DEFAULT_UA}
        for opt in self.options:
            m = re.match(r"#EXTVLCOPT:http-(user-agent|referrer|referer)=(.*)", opt, re.I)
            if m:
                key = "User-Agent" if m.group(1).lower() == "user-agent" else "Referer"
                h[key] = m.group(2).strip()
        # Kodi style: url|User-Agent=...&Referer=...
        if "|" in self.url:
            for part in self.url.split("|", 1)[1].split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    h[k] = urllib.parse.unquote(v)
        return h

    def stream_url(self):
        return self.url.split("|", 1)[0]


def attr(line, name):
    m = re.search(r'%s="([^"]*)"' % re.escape(name), line)
    return m.group(1).strip() if m else ""


def read_source(src, timeout=30):
    if re.match(r"https?://", src):
        req = urllib.request.Request(src, headers={"User-Agent": DEFAULT_UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
    else:
        with open(src, "rb") as f:
            data = f.read()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


def parse_m3u(text):
    header, channels, extinf, options = "#EXTM3U", [], None, []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTM3U"):
            header = line
        elif line.startswith("#EXTINF"):
            extinf, options = line, []
        elif line.startswith("#"):
            if extinf is not None:
                options.append(line)
        elif extinf is not None:
            channels.append(Channel(extinf, options, line))
            extinf, options = None, []
    return header, channels


# ------------------------------------------------------------------ stream checking
def fetch(url, headers, timeout, limit):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read(limit)
        return r.geturl(), (r.headers.get("Content-Type") or "").lower(), body


def first_uri(base, text):
    """First non-comment line of an HLS playlist, made absolute."""
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return urllib.parse.urljoin(base, line)
    return None


def check(ch, timeout):
    start = time.time()
    url, headers = ch.stream_url(), ch.headers()
    try:
        for _ in range(4):  # master playlist -> media playlist -> segment
            final, ctype, body = fetch(url, headers, timeout, 256 * 1024)
            if not body:
                raise ValueError("empty response")
            head = body[:7]
            if head == b"#EXTM3U" or "mpegurl" in ctype:
                nxt = first_uri(final, body.decode("utf-8", "replace"))
                if not nxt:
                    raise ValueError("HLS playlist has no entries")
                url = nxt
                continue
            if b"<html" in body[:512].lower():
                raise ValueError("got a web page, not video")
            ch.ok, ch.ms = True, int((time.time() - start) * 1000)
            return ch
        raise ValueError("too many nested playlists")
    except urllib.error.HTTPError as e:
        ch.reason = "HTTP %d" % e.code
    except urllib.error.URLError as e:
        ch.reason = "unreachable (%s)" % getattr(e, "reason", e)
    except (TimeoutError, OSError) as e:
        ch.reason = "timeout" if "timed out" in str(e) else str(e)[:80]
    except ValueError as e:
        ch.reason = str(e)
    ch.ok = False
    return ch


# ------------------------------------------------------------------ guide (EPG)
def norm(name):
    """Channel name reduced for matching: 'Rai 1 HD (1080p)' -> 'rai1'."""
    n = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", name.lower())
    n = re.sub(r"\b(hd|fhd|uhd|sd|4k|hevc|h265|backup|\d{3,4}p)\b", " ", n)
    return re.sub(r"[^a-z0-9]", "", n)


def epg_channels(data):
    """{channel id: [normalised display names]} from XMLTV bytes."""
    chans = {}
    for _, el in ET.iterparse(io.BytesIO(data), events=("end",)):
        if el.tag == "channel" and el.get("id"):
            chans[el.get("id")] = [norm(d.text or "") for d in el.findall("display-name")]
            el.clear()
        elif el.tag == "programme":
            el.clear()
    return chans


def match_guides(good, guides):
    """Set c.epg_id on working channels found in a guide. Returns {guide index: set(ids)}."""
    by_id, by_name = {}, {}
    for gi, (_, chans) in enumerate(guides):
        for cid, names in chans.items():
            by_id.setdefault(cid, gi)
            by_name.setdefault(norm(cid.split(".")[0]), (gi, cid))
            for n in names:
                if n:
                    by_name.setdefault(n, (gi, cid))
    used = {}
    for c in good:
        hit = (by_id[c.tvg_id], c.tvg_id) if c.tvg_id in by_id else by_name.get(norm(c.name))
        if hit:
            c.epg_id = hit[1]
            used.setdefault(hit[0], set()).add(hit[1])
    return used


def write_guide(path, guides, used):
    """One XMLTV file with only the channels we kept (much smaller for a 2 GB box)."""
    with gzip.open(path, "wb") as out:
        out.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<tv generator-info-name="tvbox check_iptv">\n')
        written = set()
        for gi, (data, _) in enumerate(guides):
            ids = used.get(gi, set()) - written
            if not ids:
                continue
            for _, el in ET.iterparse(io.BytesIO(data), events=("end",)):
                if (el.tag == "channel" and el.get("id") in ids) or \
                   (el.tag == "programme" and el.get("channel") in ids):
                    out.write(ET.tostring(el, encoding="utf-8"))
                    out.write(b"\n")
                if el.tag in ("channel", "programme"):
                    el.clear()
            written |= ids
        out.write(b"</tv>\n")


# ------------------------------------------------------------------ main
def with_tvg_id(extinf, new_id):
    if 'tvg-id="' in extinf:
        return re.sub(r'tvg-id="[^"]*"', 'tvg-id="%s"' % new_id, extinf, count=1)
    return extinf.replace("#EXTINF:-1", '#EXTINF:-1 tvg-id="%s"' % new_id, 1)


def main():
    ap = argparse.ArgumentParser(description="Test IPTV playlists and keep only working channels.")
    ap.add_argument("playlists", nargs="+", help="M3U files or URLs (merged together)")
    ap.add_argument("--epg", action="append", default=[], help="XMLTV guide URL or file (.xml/.gz); repeat for several")
    ap.add_argument("--timeout", type=float, default=8, help="seconds per request (default 8)")
    ap.add_argument("--workers", type=int, default=24, help="channels tested at once (default 24)")
    ap.add_argument("--slow", type=int, default=4000, help="mark channels slower than this many ms (default 4000)")
    ap.add_argument("--group", action="append", default=[], help="only keep these group-titles (repeatable, case-insensitive)")
    ap.add_argument("--keep-copies", action="store_true", help="keep every working copy of a channel, not just the fastest")
    ap.add_argument("--push", action="store_true", help="copy the results to the box with adb")
    a = ap.parse_args()

    channels, header_epgs = [], []
    for src in a.playlists:
        print("Reading %s" % src)
        header, chs = parse_m3u(read_source(src).decode("utf-8", "replace"))
        for key in ("x-tvg-url", "url-tvg"):
            for u in attr(header, key).split(","):
                if u.strip() and u.strip() not in header_epgs:
                    header_epgs.append(u.strip())
        channels += chs
    if a.group:
        wanted = {g.lower() for g in a.group}
        channels = [c for c in channels if any(w in c.group.lower() for w in wanted)]

    seen, unique = set(), []
    for ch in channels:
        if ch.stream_url() not in seen:
            seen.add(ch.stream_url())
            unique.append(ch)
    dupes = len(channels) - len(unique)
    print("Channels: %d (%d duplicate links removed). Testing..." % (len(unique), dupes))

    done = 0
    with cf.ThreadPoolExecutor(max_workers=a.workers) as pool:
        for _ in pool.map(lambda c: check(c, a.timeout), unique):
            done += 1
            if done % 50 == 0 or done == len(unique):
                print("  %d/%d tested" % (done, len(unique)), flush=True)

    good = [c for c in unique if c.ok]
    bad = [c for c in unique if not c.ok]
    copies = 0
    if not a.keep_copies:
        best = {}
        for c in good:
            k = norm(c.name) or c.stream_url()
            if k not in best or c.ms < best[k].ms:
                best[k] = c
        copies = len(good) - len(best)
        good = list(best.values())
    slow = [c for c in good if c.ms > a.slow]

    os.makedirs(OUT_DIR, exist_ok=True)
    guide_path = os.path.join(OUT_DIR, "guide.xml.gz")
    epg_sources = a.epg or header_epgs
    guides, no_guide = [], []
    for src in epg_sources:
        print("Reading guide %s" % src)
        try:
            data = read_source(src, timeout=180)
            guides.append((data, epg_channels(data)))
        except Exception as e:  # noqa: BLE001 - a broken guide shouldn't stop the run
            print("  could not read it: %s" % e)
    if guides:
        used = match_guides(good, guides)
        no_guide = [c for c in good if not c.epg_id]
        write_guide(guide_path, guides, used)
    elif os.path.exists(guide_path):
        os.remove(guide_path)

    out_m3u = os.path.join(OUT_DIR, "channels.m3u")
    with open(out_m3u, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for c in sorted(good, key=lambda c: (c.group.lower(), c.name.lower())):
            f.write((with_tvg_id(c.extinf, c.epg_id) if c.epg_id else c.extinf) + "\n")
            for o in c.options:
                f.write(o + "\n")
            f.write(c.url + "\n")

    lines = ["IPTV check  %s" % time.strftime("%Y-%m-%d %H:%M"),
             "Sources: %s" % ", ".join(a.playlists),
             "Kept: %d   Dead: %d   Duplicate links: %d   Extra copies dropped: %d   Slow (>%d ms): %d"
             % (len(good), len(bad), dupes, copies, a.slow, len(slow))]
    if guides:
        lines.append("Guide: %d of %d kept channels have a guide" % (len(good) - len(no_guide), len(good)))
    elif epg_sources:
        lines.append("Guide: none could be read")
    else:
        lines.append("Guide: none given (use --epg)")
    lines.append("\nPer group (working / total):")
    groups = {}
    for c in unique:
        g = groups.setdefault(c.group, [0, 0])
        g[1] += 1
        g[0] += 1 if c.ok else 0
    for name in sorted(groups, key=str.lower):
        lines.append("  %-40s %4d / %d" % (name[:40], groups[name][0], groups[name][1]))
    lines.append("\nDead channels:")
    lines += ["  %-45s %-25s %s" % (c.name[:45], c.group[:25], c.reason) for c in sorted(bad, key=lambda c: c.name.lower())]
    if slow:
        lines.append("\nSlow channels (kept, may buffer):")
        lines += ["  %-45s %5d ms" % (c.name[:45], c.ms) for c in sorted(slow, key=lambda c: -c.ms)]
    if no_guide:
        lines.append("\nKept channels with no guide:")
        lines += ["  %-45s tvg-id=%s" % (c.name[:45], c.tvg_id or "-") for c in sorted(no_guide, key=lambda c: c.name.lower())]
    report = os.path.join(OUT_DIR, "report.txt")
    with open(report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("\n" + "\n".join(lines[:4]))
    print("\nPlaylist: %s" % out_m3u)
    if guides:
        print("Guide:    %s" % guide_path)
    print("Report:   %s" % report)

    if a.push:
        if not shutil.which("adb"):
            sys.exit("adb not found: brew install android-platform-tools")
        devs = [l.split()[0] for l in subprocess.run(["adb", "devices"], capture_output=True, text=True).stdout.splitlines()[1:]
                if l.strip().endswith("device")]
        if len(devs) != 1:
            sys.exit("--push needs exactly one connected box (found %d). Connect with: adb connect <ip:port>" % len(devs))
        subprocess.run(["adb", "-s", devs[0], "shell", "mkdir", "-p", BOX_DIR], check=True)
        for f in [out_m3u] + ([guide_path] if guides else []):
            subprocess.run(["adb", "-s", devs[0], "push", f, BOX_DIR + "/"], check=True, capture_output=True)
            print("Copied to the box: %s/%s" % (BOX_DIR, os.path.basename(f)))


if __name__ == "__main__":
    main()
