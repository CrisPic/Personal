#!/usr/bin/env python3
"""Test every channel in an IPTV playlist and write a clean playlist with only working ones.

    python3 iptv/check_iptv.py <playlist.m3u or URL> [--epg <xmltv URL>] [--push]

What it does:
  * reads the playlist (file or URL), drops duplicate stream URLs
  * opens every stream like a player would: for HLS (.m3u8) it follows the
    playlist down to the first video segment and downloads a piece of it
  * writes  output/channels.m3u     only the channels that answered
            output/report.txt       what failed and why, per group
  * with --epg: downloads the TV guide (XMLTV, .xml or .xml.gz) and reports which
    working channels have no guide; adds the guide URL to the playlist header
  * with --push: copies channels.m3u to the box (Download/tvbox/) over adb

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
BOX_PATH = "/sdcard/Download/tvbox/channels.m3u"


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
def epg_channel_ids(url):
    data = read_source(url, timeout=120)
    ids = set()
    for _, el in ET.iterparse(io.BytesIO(data), events=("start",)):
        if el.tag == "channel" and el.get("id"):
            ids.add(el.get("id"))
        elif el.tag == "programme":
            break  # channels come first in XMLTV
    return ids


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="Test an IPTV playlist and keep only working channels.")
    ap.add_argument("playlist", help="M3U file or URL")
    ap.add_argument("--epg", help="XMLTV guide URL (.xml or .xml.gz) to check guide coverage")
    ap.add_argument("--timeout", type=float, default=8, help="seconds per request (default 8)")
    ap.add_argument("--workers", type=int, default=24, help="channels tested at once (default 24)")
    ap.add_argument("--slow", type=int, default=4000, help="mark channels slower than this many ms (default 4000)")
    ap.add_argument("--push", action="store_true", help="copy the result to the box with adb")
    a = ap.parse_args()

    header, channels = parse_m3u(read_source(a.playlist).decode("utf-8", "replace"))
    seen, unique = set(), []
    for ch in channels:
        if ch.stream_url() not in seen:
            seen.add(ch.stream_url())
            unique.append(ch)
    dupes = len(channels) - len(unique)
    print("Playlist: %d channels (%d duplicates removed). Testing..." % (len(unique), dupes))

    done = 0
    with cf.ThreadPoolExecutor(max_workers=a.workers) as pool:
        for _ in pool.map(lambda c: check(c, a.timeout), unique):
            done += 1
            if done % 25 == 0 or done == len(unique):
                print("  %d/%d tested" % (done, len(unique)), flush=True)

    good = [c for c in unique if c.ok]
    bad = [c for c in unique if not c.ok]
    slow = [c for c in good if c.ms > a.slow]

    no_guide, epg_ids = [], None
    if a.epg:
        print("Reading TV guide...")
        try:
            epg_ids = epg_channel_ids(a.epg)
            no_guide = [c for c in good if not c.tvg_id or c.tvg_id not in epg_ids]
        except Exception as e:  # noqa: BLE001 - report and continue without the guide check
            print("  could not read the guide: %s" % e)

    os.makedirs(OUT_DIR, exist_ok=True)
    out_m3u = os.path.join(OUT_DIR, "channels.m3u")
    hdr = header
    if a.epg and "x-tvg-url" not in hdr:
        hdr = '%s x-tvg-url="%s"' % (hdr, a.epg)
    with open(out_m3u, "w", encoding="utf-8") as f:
        f.write(hdr + "\n")
        for c in sorted(good, key=lambda c: (c.group.lower(), c.name.lower())):
            f.write(c.extinf + "\n")
            for o in c.options:
                f.write(o + "\n")
            f.write(c.url + "\n")

    lines = ["IPTV check  %s" % time.strftime("%Y-%m-%d %H:%M"),
             "Source: %s" % a.playlist,
             "Working: %d   Dead: %d   Duplicates removed: %d   Slow (>%d ms): %d"
             % (len(good), len(bad), dupes, a.slow, len(slow))]
    if epg_ids is not None:
        lines.append("Guide: %d of %d working channels have a guide" % (len(good) - len(no_guide), len(good)))
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
        lines.append("\nWorking channels with no guide (tvg-id missing or not in the guide):")
        lines += ["  %-45s tvg-id=%s" % (c.name[:45], c.tvg_id or "-") for c in sorted(no_guide, key=lambda c: c.name.lower())]
    with open(os.path.join(OUT_DIR, "report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("\n" + "\n".join(lines[:4]))
    print("\nClean playlist: %s\nFull report:    %s" % (out_m3u, os.path.join(OUT_DIR, "report.txt")))

    if a.push:
        if not shutil.which("adb"):
            sys.exit("adb not found: brew install android-platform-tools")
        devs = [l.split()[0] for l in subprocess.run(["adb", "devices"], capture_output=True, text=True).stdout.splitlines()[1:]
                if l.strip().endswith("device")]
        if len(devs) != 1:
            sys.exit("--push needs exactly one connected box (found %d). Connect with: adb connect <ip:port>" % len(devs))
        subprocess.run(["adb", "-s", devs[0], "shell", "mkdir", "-p", os.path.dirname(BOX_PATH)], check=True)
        subprocess.run(["adb", "-s", devs[0], "push", out_m3u, BOX_PATH], check=True, capture_output=True)
        print("Copied to the box: %s" % BOX_PATH)


if __name__ == "__main__":
    main()
