#!/usr/bin/env python3
"""
Auto-refresh Hotstar session cookies using a real browser.

Strategy:
  1. Read current cookies from cookies/ directory
  2. Check if the JWT (sessionUserUP) is close to expiry (< 6 hours)
  3. If yes, launch a stealth Chromium browser:
     a. Set all auth cookies on hotstar.com
     b. Navigate to https://www.hotstar.com/in
     c. Wait for Akamai to clear and page to fully load
     d. Try calling the refresh API from within the browser context
     e. Check all cookies for a refreshed sessionUserUP
  4. If a new JWT is obtained, save it back to cookies/sessionUserUP.txt
  5. If refresh fails, print a warning but don't fail the build

The device credentials (userHID, userPID, deviceId) don't expire.
Only the JWT expires (every 24 hours). As long as the device credentials
are valid, the refresh should work.

This script is designed to run in GitHub Actions with:
  - Playwright + Chromium installed
  - Xvfb for headful browser mode (more reliable for Akamai bypass)
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path

COOKIES_DIR = Path(os.environ.get("COOKIES_DIR", "cookies"))
REFRESH_THRESHOLD_HOURS = 6  # Refresh if JWT expires within this many hours


def read_cookie(name: str) -> str:
    p = COOKIES_DIR / f"{name}.txt"
    if p.exists():
        return p.read_text().strip()
    return ""


def write_cookie(name: str, value: str) -> None:
    p = COOKIES_DIR / f"{name}.txt"
    p.write_text(value)


def jwt_exp(jwt: str) -> int:
    """Extract exp timestamp from JWT."""
    try:
        payload_b64 = jwt.split('.')[1]
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get('exp', 0)
    except Exception:
        return 0


def jwt_is_valid(jwt: str) -> bool:
    """Check if JWT is still valid (not expired)."""
    exp = jwt_exp(jwt)
    return exp > int(time.time())


def main() -> int:
    print("=== Hotstar Cookie Auto-Refresh ===", flush=True)

    session_token = read_cookie("sessionUserUP")
    user_hid = read_cookie("userHID")
    user_pid = read_cookie("userPID")
    device_id = read_cookie("deviceId")

    if not session_token:
        print("::error::No sessionUserUP found in cookies/")
        return 1
    if not device_id:
        print("::error::No deviceId found in cookies/")
        return 1

    # Check current JWT expiry
    exp = jwt_exp(session_token)
    now = int(time.time())
    if exp > 0:
        hours_left = (exp - now) / 3600
        print(f"  Current JWT expires in {hours_left:.1f} hours")
        if hours_left > REFRESH_THRESHOLD_HOURS:
            print(f"  ✓ JWT still valid for >{REFRESH_THRESHOLD_HOURS} hours — no refresh needed")
            return 0
        if hours_left < 0:
            print(f"  ⚠ JWT EXPIRED {-hours_left:.1f} hours ago — refresh required")
        else:
            print(f"  ⚠ JWT expires in {hours_left:.1f}h (< {REFRESH_THRESHOLD_HOURS}h threshold) — refreshing")
    else:
        print("  Could not decode JWT expiry — attempting refresh")

    # Check if device credentials are present
    if not user_hid or not user_pid:
        print("::warning::Missing userHID or userPID — cannot refresh without device credentials")
        return 0

    print("  Launching browser to refresh cookies...", flush=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("::error::playwright not installed.")
        print("  Install with: pip install playwright && npx playwright install chromium --with-deps")
        return 1

    HEADLESS = os.environ.get("HEADLESS", "0") == "1"
    UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--window-size=1920,1080",
            ],
        )
        context = browser.new_context(
            user_agent=UA,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="Asia/Kolkata",
            java_script_enabled=True,
        )

        # Hide webdriver flag + fake Chrome runtime
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            "window.chrome = { runtime: {} };"
        )

        # Set ALL auth cookies on hotstar.com BEFORE navigating
        cookies_to_set = []
        for name, value in [
            ("sessionUserUP", session_token),
            ("userUP", session_token),
            ("userHID", user_hid),
            ("userPID", user_pid),
            ("deviceId", device_id),
            ("SELECTED__LANGUAGE", "eng"),
            ("x-hs-setproxystate-ud", "loc"),
        ]:
            if value:
                cookies_to_set.append({
                    "name": name,
                    "value": value,
                    "domain": ".hotstar.com",
                    "path": "/",
                    "secure": True,
                    "httpOnly": False,
                    "sameSite": "None",
                })
        context.add_cookies(cookies_to_set)

        page = context.new_page()
        try:
            print("  Navigating to https://www.hotstar.com/in ...", flush=True)
            page.goto("https://www.hotstar.com/in", wait_until="domcontentloaded", timeout=60000)

            # Wait for Akamai to clear and page to fully load
            print("  Waiting for page to load (15s)...", flush=True)
            time.sleep(15)

            # Try to call the refresh API from within the browser context
            # The browser has _abck cookie from Akamai, so this should work
            print("  Calling refresh API from browser context...", flush=True)
            refresh_result = page.evaluate("""
                async () => {
                    const urls = [
                        '/um/v1/users/refresh-token',
                        '/um/v1/users/refresh',
                    ];
                    for (const url of urls) {
                        try {
                            const resp = await fetch(url, {
                                method: 'POST',
                                credentials: 'include',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-HS-Platform': 'web',
                                    'X-HS-AppVersion': '26.07.20.3',
                                },
                                body: '{}',
                            });
                            if (resp.status === 200) {
                                const text = await resp.text();
                                try {
                                    const json = JSON.parse(text);
                                    return { ok: true, url, json };
                                } catch {
                                    return { ok: true, url, text: text.substring(0, 500) };
                                }
                            }
                        } catch (e) {
                            // Try next URL
                        }
                    }
                    return { ok: false };
                }
            """)

            if refresh_result.get("ok"):
                print("  ✓ Refresh API returned 200!", flush=True)
                json_data = refresh_result.get("json")
                if isinstance(json_data, dict):
                    # Look for new token in response
                    new_token = (
                        json_data.get("token")
                        or json_data.get("sessionUserUP")
                        or json_data.get("access_token")
                        or json_data.get("userUP")
                    )
                    if new_token and new_token != session_token:
                        if jwt_is_valid(new_token):
                            hours_left = (jwt_exp(new_token) - now) / 3600
                            print(f"  ✓ Got new JWT (valid for {hours_left:.1f} hours)")
                            write_cookie("sessionUserUP", new_token)
                            # Also update userUP if present
                            user_up = json_data.get("userUP", new_token)
                            write_cookie("userUP", user_up)
                            print("  ✓ Saved refreshed cookies")
                            browser.close()
                            return 0
                        else:
                            print("  ::warning::New JWT is expired — not saving")
                    else:
                        print(f"  ::warning::No new token in response: {json.dumps(json_data)[:200]}")
                else:
                    print(f"  ::warning::Non-JSON response: {refresh_result.get('text', '')[:200]}")
            else:
                print("  ::warning::Refresh API did not return 200 — trying cookie-based refresh")

            # If the API didn't work, check if the page load itself refreshed the cookie
            # (Hotstar's JavaScript might have set a new sessionUserUP via Set-Cookie)
            all_cookies = context.cookies()
            new_session = None
            for cookie in all_cookies:
                if cookie["name"] == "sessionUserUP":
                    new_session = cookie["value"]
                    break

            if new_session and new_session != session_token:
                if jwt_is_valid(new_session):
                    hours_left = (jwt_exp(new_session) - now) / 3600
                    print(f"  ✓ Page load refreshed JWT (valid for {hours_left:.1f} hours)")
                    write_cookie("sessionUserUP", new_session)
                    print("  ✓ Saved refreshed cookies")
                    browser.close()
                    return 0
                else:
                    print("  ::warning::Refreshed JWT from page is expired")
            elif new_session == session_token:
                print("  ::warning::JWT unchanged after page load")
                if jwt_is_valid(session_token):
                    hours_left = (exp - now) / 3600
                    print(f"  Current JWT still valid for {hours_left:.1f} hours — using as-is")
                    browser.close()
                    return 0
            else:
                print("  ::warning::No sessionUserUP cookie found in browser after navigation")

            print("  ::warning::Cookie refresh failed — build will use existing cookies")
            browser.close()
            return 0  # Don't fail the build

        except Exception as e:
            print(f"  ::warning::Browser error: {type(e).__name__}: {e}")
            try:
                page.screenshot(path="/tmp/refresh-failure.png")
                print("  Screenshot: /tmp/refresh-failure.png")
            except:
                pass
            browser.close()
            return 0  # Don't fail the build


if __name__ == "__main__":
    sys.exit(main())
