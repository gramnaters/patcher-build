#!/usr/bin/env python3
"""
JioHotstar APK downloader — uses the rvb-style Cloudflare bypass services
to fetch the latest JioHotstar APK from APKMirror.

Bypass strategy (same as github.com/nullcpy/rvb):
  Two services run as GitHub Actions `services:` containers:
    - trawl (ghcr.io/germondai/trawl:latest) on :8191  — primary
    - cloudflarebypassforscraping (ghcr.io/sarperavci/...) on :8000  — fallback

  For each APKMirror page we need to scrape, we POST the URL to one of
  the services; they run a real headless browser that solves the
  Cloudflare Turnstile challenge and returns the cleared HTML + cookies
  + User-Agent. We then reuse those cookies to download the final APK
  file via plain curl.

Endpoints (matching rvb's utils.sh):
  trawl:    POST http://localhost:8191/scrape  {url, maxTimeout, skipHttp}
            -> JSON {statusCode, html, cookies[], userAgent}
  cfbs:     GET  http://localhost:8000/html?url=<url>
            -> raw HTML body (200) + X-CF-Bypasser-Cookies/User-Agent headers
            (cookies-as-dict: GET /cookies?url=<url> -> JSON)

Output:
  jiohotstar.apk       — the downloaded APK (or extracted base.apk from a bundle)
  arm64_split.apk      — the arm64 split APK (if a bundle was downloaded)
  version.txt          — the version name (e.g. 26.07.20.3)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile
import shutil
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Default to the same URL rvb uses for JioHotstar. The publisher recently
# renamed from "star-india-private-limited" to "jiostar-india-private-limited".
MOBILE_APPS = [
    "https://www.apkmirror.com/apk/jiostar-india-private-limited/jiohotstar-4/",
    "https://www.apkmirror.com/apk/jiostar-india-private-limited/jiostar-hotstar/",
    "https://www.apkmirror.com/apk/star-india-private-limited/jiohotstar/",
    "https://www.apkmirror.com/apk/jio/jiohotstar/",
]

# Android TV is a SEPARATE APKMirror listing (own version track, universal
# arm64-v8a + x86 arch), but keeps the same package name in.startv.hotstar.
# Current listing: jiostar-india-private-limited/jiohotstar-3 (slug
# "jiohotstar-android-tv-26-08-17-0-release").
TV_APPS = [
    "https://www.apkmirror.com/apk/jiostar-india-private-limited/jiohotstar-3/",
    "https://www.apkmirror.com/apk/jiostar-india-private-limited/hotstar-android-tv/",
    "https://www.apkmirror.com/apk/star-india-private-limited/hotstar-android-tv/",
]

# APP_VARIANT=tv selects the Android TV listing; anything else is mobile.
APP_VARIANT = os.environ.get("APP_VARIANT", "mobile").lower()
APPS = TV_APPS if APP_VARIANT == "tv" else MOBILE_APPS
OUTPUT_APK = os.environ.get("OUTPUT", "jiohotstar.apk")
TARGET_ARCH = os.environ.get("ARCH", "arm64-v8a").lower()
# arm-v7a -> armeabi-v7a (APKMirror naming)
if TARGET_ARCH == "arm-v7a":
    TARGET_ARCH = "armeabi-v7a"

# APKEditor jar used to properly merge split resource tables (resources.arsc)
# across all config splits. Unlike a raw `zip` merge, this produces a single
# APK whose resources.arsc contains the union of ALL split resources — which
# is required or the app crashes with Resources$NotFoundException for IDs that
# live only in a split's table (e.g. density-specific drawables).
APKEDITOR_JAR = os.environ.get("APKEDITOR_JAR", "/usr/local/bin/apkeditor.jar")

TRAWL_URL = os.environ.get("TRAWL_URL", "http://localhost:8191/scrape")
CFBS_URL  = os.environ.get("CFBS_URL",  "http://localhost:8000")

FALLBACK_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/109.0"

# State shared across calls — set by the first successful bypass
CF_COOKIES: str = ""
USER_AGENT: str = FALLBACK_UA


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


def err(msg: str) -> None:
    print(f"::error::{msg}", flush=True)


# ---------------------------------------------------------------------------
# Cloudflare bypass — port of rvb's _cf_get / _trawl_8191_get / _cfb_get
# ---------------------------------------------------------------------------

def _trawl_get(url: str, referer: str = "") -> Optional[str]:
    """Primary: POST to trawl on :8191. Returns HTML or None."""
    payload = {
        "url": url,
        "maxTimeout": 60000,
        "skipHttp": True,
    }
    if referer:
        payload["headers"] = {"Referer": referer}
    try:
        req = urllib.request.Request(
            TRAWL_URL,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        data = json.loads(body)
        if data.get("statusCode") != 200:
            log(f"trawl: statusCode={data.get('statusCode')}")
            return None
        html = data.get("html", "")
        if not html:
            return None
        # Detect challenge pages (same checks as rvb)
        for marker in ("Attention Required!", "Just a moment...",
                       "Please Wait... | Cloudflare", "Verify you are human"):
            if marker in html:
                log(f"trawl: still on challenge page ({marker})")
                return None
        # Save cookies + UA for later APK download
        global CF_COOKIES, USER_AGENT
        cookies = data.get("cookies", []) or []
        CF_COOKIES = "; ".join(f"{c['name']}={c['value']}" for c in cookies
                               if c.get("name") and c.get("value"))
        ua = data.get("userAgent")
        if ua:
            USER_AGENT = ua
        return html
    except Exception as e:
        log(f"trawl: {type(e).__name__}: {e}")
        return None


def _cfbs_get(url: str) -> Optional[str]:
    """Fallback: GET cloudflarebypassforscraping on :8000. Returns HTML or None."""
    try:
        # /cookies first to get cookies + UA as JSON
        cookies_url = f"{CFBS_URL}/cookies?" + urllib.parse.urlencode({"url": url})
        req = urllib.request.Request(cookies_url, headers={"User-Agent": FALLBACK_UA})
        with urllib.request.urlopen(req, timeout=120) as resp:
            cdata = json.loads(resp.read().decode())

        global CF_COOKIES, USER_AGENT
        cookies = cdata.get("cookies", {}) or {}
        CF_COOKIES = "; ".join(f"{k}={v}" for k, v in cookies.items())
        ua = cdata.get("user_agent")
        if ua:
            USER_AGENT = ua

        # /html to get the actual page content
        html_url = f"{CFBS_URL}/html?" + urllib.parse.urlencode({"url": url})
        req = urllib.request.Request(html_url, headers={"User-Agent": FALLBACK_UA})
        with urllib.request.urlopen(req, timeout=120) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        if not html:
            return None
        for marker in ("Attention Required!", "Just a moment...",
                       "Please Wait... | Cloudflare", "Verify you are human"):
            if marker in html:
                log(f"cfbs: still on challenge page ({marker})")
                return None
        return html
    except Exception as e:
        log(f"cfbs: {type(e).__name__}: {e}")
        return None


def cf_get(url: str, referer: str = "") -> Optional[str]:
    """Try trawl first, fall back to cfbs, then direct request. Returns HTML."""
    # Primary: trawl
    html = _trawl_get(url, referer)
    if html:
        return html
    # Fallback: cloudflarebypassforscraping
    html = _cfbs_get(url)
    if html:
        return html
    # Last resort: direct request (will 403 on CF-protected pages, but
    # works for the final CDN download which uses cf_clearance cookies)
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Cookie": CF_COOKIES,
                "Referer": "https://www.apkmirror.com/",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        log(f"direct: {type(e).__name__}: {e}")
        return None


# ---------------------------------------------------------------------------
# APKMirror scraping — port of rvb's dl_apkmirror
# ---------------------------------------------------------------------------

def search_app_page() -> Optional[str]:
    """Fallback: discover the app-listing URL via APKMirror search.

    Returns the first /apk/<publisher>/<app>/ listing URL whose slug matches
    the current variant (mobile -> jiohotstar/hotstar; tv -> android-tv).
    """
    keywords = (
        ["hotstar tv", "jiohotstar tv", "hotstar-android-tv"]
        if APP_VARIANT == "tv"
        else ["jiohotstar", "hotstar"]
    )
    seen = set()
    for kw in keywords:
        url = ("https://www.apkmirror.com/?post_type=app_release"
               "&searchtype=apk&s=" + urllib.parse.quote(kw))
        log(f"  search: {kw}")
        html = cf_get(url)
        if not html:
            continue
        for l in re.findall(r'href="(/apk/[^/]+/[^/]+/)"', html):
            l = l.split("#")[0]
            if l in seen:
                continue
            seen.add(l)
            slug = l.rstrip("/").split("/")[-1]
            if APP_VARIANT == "tv":
                if "tv" in slug or "leanback" in slug:
                    log(f"  found TV listing: {l}")
                    return "https://www.apkmirror.com" + l
            else:
                if "jiohotstar" in slug or "hotstar" in slug:
                    log(f"  found listing: {l}")
                    return "https://www.apkmirror.com" + l
    return None


def find_app_page() -> Tuple[str, str]:
    """Find the JioHotstar app page (try multiple publisher slugs, then search)."""
    candidates = list(APPS)
    # Dynamic search discovery (append, not replace) for robustness
    for app_url in candidates:
        log(f"Trying app page: {app_url}")
        html = cf_get(app_url)
        if not html:
            continue
        if "Page Not Found" in html or "<h1>404" in html:
            log("  404 page, trying next URL")
            continue
        if "appRow" not in html and "jiohotstar" not in html.lower() and "hotstar" not in html.lower():
            log("  no version rows, trying next URL")
            continue
        return app_url, html

    log("Hardcoded URLs failed — searching APKMirror...")
    found = search_app_page()
    if found:
        html = cf_get(found)
        if html and "Page Not Found" not in html and "<h1>404" not in html:
            return found, html

    err("Could not find JioHotstar app page on APKMirror (tried all known URLs + search)")
    sys.exit(1)


def find_latest_version(app_html: str, app_url: str) -> Tuple[str, str]:
    """Find the latest version link on the app page.

    APKMirror lists versions in .appRow blocks. Each row's first <a> inside
    h5 is the version link. Newest is at the top.
    """
    # Pattern 1: explicit version-release link (most reliable)
    # e.g. /apk/jiostar-india-private-limited/jiostar-hotstar/hotstar-26-07-20-3-release/
    # The publisher slug can vary; match any /apk/<publisher>/<app>/<version>-release/
    versions = re.findall(
        r'href="(/apk/[^/]+/[^/]+/[^"]+-release/)"',
        app_html,
    )
    if not versions:
        # Pattern 2: h5 > a links (broader)
        versions = re.findall(
            r'<h5[^>]*>\s*<a[^>]*href="(/apk/[^"]+)"',
            app_html,
        )

    # Filter to the correct app slug (avoid Disney+ Hotstar etc.).
    if APP_VARIANT == "tv":
        tv_versions = [v for v in versions if "android-tv" in v]
        if tv_versions:
            versions = tv_versions
    else:
        jio_versions = [v for v in versions if "jiostar-hotstar" in v or "jiohotstar" in v]
        if jio_versions:
            versions = jio_versions

    # Dedupe (preserve order)
    seen = set()
    deduped = []
    for v in versions:
        # Strip #disqus_thread anchors
        v = v.split("#")[0]
        if v not in seen and v.endswith("/"):
            seen.add(v)
            deduped.append(v)

    if not deduped:
        err("Could not find any version links on app page")
        sys.exit(1)

    latest_path = deduped[0]
    # Extract version name from URL: .../hotstar-26-07-20-3-release/ -> 26.07.20.3
    m = re.search(r"/([^/]+)-release/?$", latest_path)
    if m:
        slug = m.group(1)
        # hotstar-26-07-20-3 -> 26.07.20.3
        ver_match = re.search(r"(\d+(?:-\d+)+)", slug)
        version_name = ver_match.group(1).replace("-", ".") if ver_match else slug
    else:
        version_name = "unknown"

    full_url = urllib.parse.urljoin("https://www.apkmirror.com", latest_path)
    log(f"Latest version: {version_name}")
    log(f"  URL: {full_url}")
    return full_url, version_name


def find_variant_link(version_html: str) -> str:
    """Find the APK download-link for the target arch on the version page.

    APKMirror version pages have a "downloads" section listing variants.
    Each variant row is a <div class="table-row ..."> containing:
      - architecture text (arm64-v8a / armeabi-v7a / x86 / x86_64 / universal)
      - type (APK or BUNDLE)
      - a download link whose URL ends in `-android-apk-download/`

    We prefer the APK for our target arch; fall back to universal/noarch,
    then to the first available APK variant. If only a BUNDLE is available
    (which contains base.apk + arch-specific splits), we take that — the
    process_download() step will extract base.apk + arm64 split.

    For Android TV we want the all-arch variant (arm64-v8a + armeabi-v7a)
    so the single APK installs on any TV CPU.
    """
    target_norm = TARGET_ARCH.replace("-", "").lower()
    prefer_universal = APP_VARIANT == "tv"

    # Collect every variant download link and its position.
    # A variant row's arch text sits in a sibling table-cell just after the
    # download link, so we inspect the HTML window following each link.
    all_dls = [(m.start(), m.group(1)) for m in
               re.finditer(r'href="(/apk/[^"]+-android-apk-download/)"', version_html)]

    # For TV, the release usually has ONE all-arch variant (arm64-v8a +
    # armeabi-v7a combined). If there's a single link, just take it.
    if prefer_universal and len(all_dls) == 1:
        href = all_dls[0][1].split("#")[0]
        full_url = urllib.parse.urljoin("https://www.apkmirror.com", href)
        log("Using single all-arch TV variant")
        return full_url

    universal_apk_link: Optional[str] = None
    universal_bundle_link: Optional[str] = None
    fallback_apk_link: Optional[str] = None

    for pos, href in all_dls:
        href = href.split("#")[0]
        full_url = urllib.parse.urljoin("https://www.apkmirror.com", href)

        # Look at the surrounding HTML to determine arch + type
        window = version_html[pos:pos + 2500]
        text = re.sub(r"<[^>]+>", " ", window)
        text_norm = text.lower().replace("-", "").replace(" ", "")

        is_bundle = "bundle" in text_norm
        has_universal = "universal" in text_norm or "noarch" in text_norm
        has_arm64 = "arm64v8a" in text_norm
        has_armv7 = "armeabiv7a" in text_norm or "armv7a" in text_norm
        all_arch = has_arm64 and has_armv7

        if prefer_universal:
            if has_universal or all_arch:
                if is_bundle:
                    if universal_bundle_link is None:
                        universal_bundle_link = full_url
                else:
                    if universal_apk_link is None:
                        universal_apk_link = full_url
            elif not is_bundle and fallback_apk_link is None:
                fallback_apk_link = full_url
            continue

        # Mobile: exact arch match wins immediately
        if target_norm in text_norm:
            log(f"Found {TARGET_ARCH} variant ({'BUNDLE' if is_bundle else 'APK'})")
            return full_url
        if has_universal:
            if is_bundle:
                if universal_bundle_link is None:
                    universal_bundle_link = full_url
            else:
                if universal_apk_link is None:
                    universal_apk_link = full_url
        elif not is_bundle and fallback_apk_link is None:
            fallback_apk_link = full_url

    if prefer_universal:
        if universal_apk_link:
            log("Using all-arch/universal APK variant (works on any TV)")
            return universal_apk_link
        if universal_bundle_link:
            log("Using all-arch/universal BUNDLE variant (all arches)")
            return universal_bundle_link
        if fallback_apk_link:
            log("Using first available APK variant")
            return fallback_apk_link
        err("No universal or APK variant found for Android TV")
        sys.exit(1)

    # Prefer universal APK > any other APK > universal BUNDLE
    if universal_apk_link:
        log("Using universal APK variant")
        return universal_apk_link
    if fallback_apk_link:
        log("Using first available APK variant")
        return fallback_apk_link
    if universal_bundle_link:
        log("Using universal BUNDLE variant (will extract base.apk + arm64 split)")
        return universal_bundle_link
    err(f"No downloadable APK variant found for arch {TARGET_ARCH}")
    sys.exit(1)


def find_download_button_url(variant_html: str) -> str:
    """Extract the downloadButton href from the variant page.

    APKMirror's variant page (the one whose URL ends in `-android-apk-download/`)
    contains a green download button:
      <a class="... downloadButton ..." href="/apk/.../download/?key=...">
    Following THAT URL gives yet another interstitial page that contains
    <a id="download-link" href="https://downloadr2.apkmirror.com/..."> —
    the actual CDN URL of the APK file.

    This function returns the downloadButton href (step 1 of 2).
    """
    # Pattern 1: <a class="...downloadButton..." href="...">
    m = re.search(
        r'<a[^>]*class="[^"]*downloadButton[^"]*"[^>]*href="([^"]+)"',
        variant_html,
    )
    if not m:
        # Pattern 2: <a id="download-link" href="...">  (already on the final page)
        m = re.search(r'id="download-link"[^>]*href="([^"]+)"', variant_html)
        if m:
            href = m.group(1).replace("&amp;", "&")
            return href if href.startswith("http") else \
                urllib.parse.urljoin("https://www.apkmirror.com", href)
    if not m:
        # Pattern 3: any href containing download.php
        m = re.search(r'href="([^"]*download\.php[^"]*)"', variant_html)
    if not m:
        err("Could not find downloadButton on variant page")
        sys.exit(1)
    href = m.group(1).replace("&amp;", "&")
    if href.startswith("http"):
        return href
    return urllib.parse.urljoin("https://www.apkmirror.com", href)


def resolve_final_download_url(final_interstitial_html: str) -> str:
    """Extract the actual CDN URL from the final interstitial page.

    After clicking the downloadButton, we land on a page with:
      <a id="download-link" href="https://downloadr2.apkmirror.com/...">
    That href is the actual APK file on APKMirror's R2 CDN. We can fetch
    it directly with the cf_clearance cookies.
    """
    # Pattern 1: <a id="download-link" href="...">
    m = re.search(r'id="download-link"[^>]*href="([^"]+)"', final_interstitial_html)
    if not m:
        # Pattern 2: href containing downloadr2.apkmirror.com
        m = re.search(r'href="(https?://[^"]*downloadr2\.apkmirror\.com[^"]*)"',
                      final_interstitial_html)
    if not m:
        # Pattern 3: href containing cloudflarestorage
        m = re.search(r'href="(https?://[^"]*cloudflarestorage[^"]*)"',
                      final_interstitial_html)
    if not m:
        # Pattern 4: any download.php URL
        m = re.search(r'href="([^"]*download\.php[^"]*)"',
                      final_interstitial_html)
    if not m:
        err("Could not resolve final download URL from interstitial page")
        sys.exit(1)
    href = m.group(1).replace("&amp;", "&")
    if href.startswith("http"):
        return href
    return urllib.parse.urljoin("https://www.apkmirror.com", href)


# ---------------------------------------------------------------------------
# APK download + processing (port of rvb's wget + unzip logic)
# ---------------------------------------------------------------------------

def download_apk(url: str, output: str, referer: str) -> None:
    """Download the APK file using curl + the cf_clearance cookies."""
    log(f"Downloading: {url[:80]}...")
    cmd = [
        "curl", "-sS", "-L",
        "--max-time", "600",
        "-H", f"User-Agent: {USER_AGENT}",
        "-H", f"Cookie: {CF_COOKIES}",
        "-H", f"Referer: {referer}",
        "-o", output,
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=605)
    if result.returncode != 0:
        err(f"curl failed: {result.stderr}")
        sys.exit(1)
    size = os.path.getsize(output) if os.path.exists(output) else 0
    if size < 1_000_000:
        err(f"Download too small ({size} bytes)")
        sys.exit(1)
    log(f"Downloaded {size / 1024 / 1024:.1f} MB")


def process_download(downloaded_path: str) -> None:
    """Extract base.apk from APKM bundle and merge ALL splits (resources + libs).

    APKMirror bundles (.apkm) contain:
      - base.apk (code + manifest, but resources.arsc references drawables in splits)
      - split_config.arm64_v8a.apk (native libs)
      - split_config.xxhdpi.apk / xxxhdpi.apk (drawables for specific DPIs)
      - split_config.en.apk (language resources)

    If we only extract base.apk, the app crashes with Resources$NotFoundException
    because drawables referenced in resources.arsc are missing.

    NOTE: each config split carries its OWN resources.arsc. A naive file-level
    `zip` merge alone cannot combine the split resource tables — the resulting
    APK keeps only ONE resources.arsc and loses every resource ID that only
    exists in a split's table (e.g. density-specific drawables). That made the
    app crash with `Resources$NotFoundException` (e.g. resource #0x7f08023c).

    Fix: merge with APKEditor (`java -jar APKEditor.jar m`), which properly
    fuses the split resources.arsc tables into a single complete table, and
    also sanitizes the manifest (removes splitTypes/isSplitRequired/
    com.android.vending.splits meta-data etc.).
    """
    with open(downloaded_path, "rb") as f:
        magic = f.read(4)
    if magic != b"PK\x03\x04":
        shutil.move(downloaded_path, OUTPUT_APK)
        return

    with zipfile.ZipFile(downloaded_path, "r") as z:
        names = z.namelist()
        has_manifest = "AndroidManifest.xml" in names
        has_base_apk = any(n == "base.apk" or n.endswith("/base.apk") for n in names)

    if has_manifest and not has_base_apk:
        log("Standalone APK detected")
        shutil.move(downloaded_path, OUTPUT_APK)
        return

    if not has_base_apk:
        shutil.move(downloaded_path, OUTPUT_APK)
        return

    log("APKM bundle detected — merging via APKEditor")

    # Save the target-arch split (native libs) for later re-injection fallback
    arch_underscore = TARGET_ARCH.replace("-", "_")
    try:
        with zipfile.ZipFile(downloaded_path, "r") as z:
            for name in z.namelist():
                if not name.endswith(".apk"):
                    continue
                if arch_underscore in name:
                    split_data = z.read(name)
                    if len(split_data) > 1_000_000:
                        with open("arm64_split.apk", "wb") as w:
                            w.write(split_data)
                        log(f"Saved target-arch split: arm64_split.apk ({len(split_data) / 1024 / 1024:.1f} MB)")
                        break
    except Exception as e:
        log(f"Warning: could not save target-arch split: {e}")

    if not os.path.exists(APKEDITOR_JAR):
        log("APKEDITOR_JAR not found — falling back to legacy zip merge")
        _legacy_zip_merge(downloaded_path)
        return

    cmd = [
        "java", "-jar", APKEDITOR_JAR, "m",
        "-i", downloaded_path,
        "-o", OUTPUT_APK,
        "-f",
    ]
    log(f"Running APKEditor merge: {' '.join(cmd[:4])} ...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except FileNotFoundError:
        log("java not found — falling back to legacy zip merge")
        _legacy_zip_merge(downloaded_path)
        return
    except subprocess.TimeoutExpired:
        err("APKEditor merge timed out")
        sys.exit(1)

    if result.returncode != 0:
        err("APKEditor merge failed")
        log(result.stdout[-4000:] if result.stdout else "")
        log(result.stderr[-4000:] if result.stderr else "")
        sys.exit(1)

    if not os.path.exists(OUTPUT_APK) or os.path.getsize(OUTPUT_APK) < 5_000_000:
        err("merged APK too small or missing")
        sys.exit(1)

    final_mb = os.path.getsize(OUTPUT_APK) / 1024 / 1024
    log(f"Ready: {OUTPUT_APK} ({final_mb:.1f} MB) — splits merged via APKEditor")
    os.remove(downloaded_path)


def _legacy_zip_merge(downloaded_path: str) -> None:
    """Fallback: naive file-level split merge (does NOT fuse resources.arsc)."""
    log("APKM bundle detected — extracting base.apk + ALL splits (legacy)")

    # Extract ALL files from the bundle
    with zipfile.ZipFile(downloaded_path, "r") as z:
        z.extractall(".")

    # Start with base.apk as the output
    shutil.move("base.apk", OUTPUT_APK)

    # Find ALL split APKs
    split_apks = sorted([f for f in os.listdir(".") if f.startswith("split_config.") and f.endswith(".apk")])
    log(f"Found {len(split_apks)} split APKs: {', '.join(split_apks)}")

    # Save the target-arch split (native libs) for later re-injection
    arch_underscore = TARGET_ARCH.replace("-", "_")
    for split_apk in split_apks:
        if arch_underscore in split_apk and split_apk != "arm64_split.apk":
            shutil.copy(split_apk, "arm64_split.apk")
            log(f"Saved target-arch split: arm64_split.apk")
            break

    # Merge each split into the base APK
    for split_apk in split_apks:
        log(f"Merging {split_apk}...")
        merge_tmp = "split_merge_tmp"
        if os.path.exists(merge_tmp):
            shutil.rmtree(merge_tmp)

        with zipfile.ZipFile(split_apk, "r") as split_zip:
            for name in split_zip.namelist():
                if name == "AndroidManifest.xml":
                    continue  # Keep base.apk's manifest
                split_zip.extract(name, merge_tmp)

        # Add extracted files to the base APK (stored, not compressed)
        for root, dirs, files in os.walk(merge_tmp):
            for fname in files:
                fpath = os.path.join(root, fname)
                arcname = os.path.relpath(fpath, merge_tmp)
                subprocess.run(
                    ["zip", "-0", OUTPUT_APK, arcname],
                    cwd=merge_tmp,
                    capture_output=True,
                )

        shutil.rmtree(merge_tmp, ignore_errors=True)
        os.remove(split_apk)

    os.remove(downloaded_path)

    if not os.path.exists(OUTPUT_APK) or os.path.getsize(OUTPUT_APK) < 5_000_000:
        size = os.path.getsize(OUTPUT_APK) if os.path.exists(OUTPUT_APK) else 0
        err(f"Final APK too small ({size} bytes)")
        sys.exit(1)
    final_mb = os.path.getsize(OUTPUT_APK) / 1024 / 1024
    log(f"Ready: {OUTPUT_APK} ({final_mb:.1f} MB) — all splits merged")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> int:
    print("=== JioHotstar APK downloader (rvb-style CF bypass) ===", flush=True)
    print(f"  Target arch: {TARGET_ARCH}", flush=True)
    print(f"  Output:      {OUTPUT_APK}", flush=True)
    print(f"  Trawl URL:   {TRAWL_URL}", flush=True)
    print(f"  CFBS URL:    {CFBS_URL}", flush=True)

    # Step 1: find the app page
    print("\n--- Step 1: find app page ---", flush=True)
    app_url, app_html = find_app_page()

    # Step 2: find the latest version
    print("\n--- Step 2: find latest version ---", flush=True)
    version_url, version_name = find_latest_version(app_html, app_url)

    # Step 3: get the version page and find the variant for our arch
    print("\n--- Step 3: find variant for target arch ---", flush=True)
    version_html = cf_get(version_url)
    if not version_html:
        err("Could not fetch version page")
        sys.exit(1)
    variant_url = find_variant_link(version_html)
    log(f"Variant URL: {variant_url}")

    # Step 4: get the variant page and extract the downloadButton URL
    print("\n--- Step 4: find download button ---", flush=True)
    variant_html = cf_get(variant_url)
    if not variant_html:
        err("Could not fetch variant page")
        sys.exit(1)
    download_button_url = find_download_button_url(variant_html)
    log(f"Download button URL: {download_button_url[:100]}...")

    # Step 5: follow the download button URL to get the final CDN URL
    print("\n--- Step 5: resolve final CDN URL ---", flush=True)
    final_interstitial_html = cf_get(download_button_url,
                                     referer="https://www.apkmirror.com/")
    if not final_interstitial_html:
        err("Could not fetch final interstitial page")
        sys.exit(1)
    final_url = resolve_final_download_url(final_interstitial_html)
    log(f"Final CDN URL: {final_url[:100]}...")

    # Step 6: download the APK bytes using the cf_clearance cookies
    print("\n--- Step 6: download APK ---", flush=True)
    downloaded_path = "downloaded.bin"
    download_apk(final_url, downloaded_path, referer="https://www.apkmirror.com/")

    # Step 7: process the downloaded file (extract base.apk from bundle if needed)
    print("\n--- Step 7: process downloaded file ---", flush=True)
    process_download(downloaded_path)

    # Write version.txt for later workflow steps
    with open("version.txt", "w") as f:
        f.write(version_name)

    print(f"\n=== SUCCESS ===", flush=True)
    print(f"  Version: {version_name}", flush=True)
    print(f"  APK:     {OUTPUT_APK} ({os.path.getsize(OUTPUT_APK) / 1024 / 1024:.1f} MB)", flush=True)
    if os.path.exists("arm64_split.apk"):
        print(f"  Split:   arm64_split.apk ({os.path.getsize('arm64_split.apk') / 1024 / 1024:.1f} MB)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
