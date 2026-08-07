#!/usr/bin/env python3
"""
Check the latest JioHotstar version available on APKMirror.

Lightweight version of download_apk.py — only fetches the app page and
extracts the latest version number. Does NOT download the APK.

Uses the same Cloudflare bypass services (trawl + cfbs) as download_apk.py.

Output: prints the latest version string (e.g. "26.07.20.3") to stdout.
        On failure, prints nothing and exits with code 1.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from typing import Optional

# Same config as download_apk.py
APPS = [
    "https://www.apkmirror.com/apk/jiostar-india-private-limited/jiohotstar-4/",
    "https://www.apkmirror.com/apk/jiostar-india-private-limited/jiostar-hotstar/",
    "https://www.apkmirror.com/apk/star-india-private-limited/jiohotstar/",
    "https://www.apkmirror.com/apk/jio/jiohotstar/",
]
TRAWL_URL = os.environ.get("TRAWL_URL", "http://localhost:8191/scrape")
CFBS_URL = os.environ.get("CFBS_URL", "http://localhost:8000")
FALLBACK_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/109.0"


def _trawl_get(url: str) -> Optional[str]:
    try:
        payload = {"url": url, "maxTimeout": 60000, "skipHttp": True}
        req = urllib.request.Request(
            TRAWL_URL,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode())
        if data.get("statusCode") != 200:
            return None
        html = data.get("html", "")
        for marker in ("Attention Required!", "Just a moment...",
                       "Please Wait... | Cloudflare", "Verify you are human"):
            if marker in html:
                return None
        return html
    except Exception:
        return None


def _cfbs_get(url: str) -> Optional[str]:
    try:
        html_url = f"{CFBS_URL}/html?" + urllib.parse.urlencode({"url": url})
        req = urllib.request.Request(html_url, headers={"User-Agent": FALLBACK_UA})
        with urllib.request.urlopen(req, timeout=120) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        for marker in ("Attention Required!", "Just a moment...",
                       "Please Wait... | Cloudflare", "Verify you are human"):
            if marker in html:
                return None
        return html
    except Exception:
        return None


def cf_get(url: str) -> Optional[str]:
    for fn in (_trawl_get, _cfbs_get):
        html = fn(url)
        if html:
            return html
    return None


def find_latest_version(html: str) -> Optional[str]:
    """Extract the latest version from the app page HTML."""
    # Pattern 1: explicit version-release link
    versions = re.findall(
        r'href="(/apk/[^/]+/[^/]+/[^"]+-release/)"',
        html,
    )
    # Filter to JioHotstar (avoid Disney+ Hotstar)
    jio = [v for v in versions if "jiostar-hotstar" in v or "jiohotstar" in v]
    if jio:
        versions = jio
    # Dedupe
    seen = set()
    deduped = []
    for v in versions:
        v = v.split("#")[0]
        if v not in seen and v.endswith("/"):
            seen.add(v)
            deduped.append(v)
    if not deduped:
        return None
    latest_path = deduped[0]
    # Extract version: .../hotstar-26-07-20-3-release/ -> 26.07.20.3
    m = re.search(r"/([^/]+)-release/?$", latest_path)
    if not m:
        return None
    slug = m.group(1)
    ver_match = re.search(r"(\d+(?:-\d+)+)", slug)
    return ver_match.group(1).replace("-", ".") if ver_match else slug


def main() -> int:
    for app_url in APPS:
        html = cf_get(app_url)
        if not html:
            continue
        if "Page Not Found" in html or "<h1>404" in html:
            continue
        if "appRow" not in html and "hotstar" not in html.lower():
            continue
        version = find_latest_version(html)
        if version:
            print(version)
            return 0
    print("ERROR: could not fetch latest version from APKMirror", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
