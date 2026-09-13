#!/usr/bin/env python3
"""
Auto-refresh Hotstar session cookies using a real browser.

STRATEGY (discovered 2026-09-13):
  The BFF endpoint POST /api/internal/bff/v2/pages/136/spaces/133/widgets/119
  ?action=switchProfile&position=0&profileType=ADULT
  returns a FRESH 24h JWT in the x-hs-updatedusertoken response header.

  This works because:
  1. We set existing auth cookies (sessionUserUP, userHID, userPID, deviceId) on the browser
  2. Navigate to hotstar.com — the site sets Akamai bot-management cookies (_abck, bm_sz)
  3. Call switchProfile from within the browser context (with all cookies)
  4. Extract the fresh JWT from the response header
  5. Save it back to cookies/sessionUserUP.txt

The device credentials (userHID, userPID, deviceId) don't expire.
Only the JWT expires (every 24 hours). The refresh renews it.
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
    print("=== Hotstar Cookie Auto-Refresh v2 ===", flush=True)

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
            print(f"  JWT still valid for >{REFRESH_THRESHOLD_HOURS} hours — no refresh needed")
            return 0
        if hours_left < 0:
            print(f"  JWT EXPIRED {-hours_left:.1f} hours ago — refresh required")
        else:
            print(f"  JWT expires in {hours_left:.1f}h (< {REFRESH_THRESHOLD_HOURS}h threshold) — refreshing")
    else:
        print("  Could not decode JWT expiry — attempting refresh")

    print("  Launching browser for BFF-based refresh...", flush=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("::error::playwright not installed.")
        print("  Install with: pip install playwright && python3 -m playwright install chromium --with-deps")
        return 1

    HEADLESS = os.environ.get("HEADLESS", "0") == "1"
    UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=HEADLESS,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(
                user_agent=UA,
                viewport={"width": 1920, "height": 1080},
                locale="en-IN",
                timezone_id="Asia/Kolkata",
            )

            # Hide webdriver flag
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )

            # Step 1: Set ALL auth cookies BEFORE navigating
            cookies_to_set = []
            for name, value in [
                ("sessionUserUP", session_token),
                ("userUP", read_cookie("userUP") or session_token),
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

            # Step 2: Navigate to hotstar.com — triggers Akamai cookie generation
            print("  Navigating to hotstar.com...", flush=True)
            page.goto("https://www.hotstar.com/in/home", wait_until="domcontentloaded", timeout=60000)

            # Wait for Akamai to set _abck and bm_sz cookies
            print("  Waiting for Akamai cookies (10s)...", flush=True)
            time.sleep(10)

            # Step 3: Check if we got Akamai cookies
            all_cookies = context.cookies()
            has_abck = any(c["name"] == "_abck" for c in all_cookies)
            print(f"  Akamai _abck cookie present: {has_abck}")

            # Step 4: Call switchProfile via fetch from within the browser context
            # This is the BFF endpoint that returns a fresh JWT in x-hs-updatedusertoken
            print("  Calling switchProfile BFF endpoint...", flush=True)

            refresh_result = page.evaluate("""
                async () => {
                    try {
                        const resp = await fetch(
                            '/api/internal/bff/v2/pages/136/spaces/133/widgets/119?action=switchProfile&position=0&profileType=ADULT',
                            {
                                method: 'POST',
                                credentials: 'include',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-HS-Platform': 'web',
                                    'X-HS-AppVersion': '26.07.20.3',
                                },
                                body: '{}',
                            }
                        );

                        // Extract the fresh token from response headers
                        const newToken = resp.headers.get('x-hs-updatedusertoken');

                        return {
                            status: resp.status,
                            newToken: newToken || null,
                            hasToken: !!newToken,
                        };
                    } catch (e) {
                        return { status: 0, error: e.message, hasToken: false };
                    }
                }
            """)

            print(f"  switchProfile response: status={refresh_result.get('status')}, hasToken={refresh_result.get('hasToken')}")

            new_token = refresh_result.get("newToken")
            if new_token and new_token != session_token:
                if jwt_is_valid(new_token):
                    hours_left = (jwt_exp(new_token) - now) / 3600
                    print(f"  Got NEW JWT! Valid for {hours_left:.1f} hours")
                    write_cookie("sessionUserUP", new_token)
                    # Also update userUP if it exists
                    if (COOKIES_DIR / "userUP.txt").exists():
                        write_cookie("userUP", new_token)
                    print("  Saved refreshed cookies")
                    browser.close()
                    return 0
                else:
                    print("  ::warning::New JWT is expired — not saving")
            elif new_token and new_token == session_token:
                print("  ::warning::Token unchanged after refresh")
            else:
                print("  ::warning::No x-hs-updatedusertoken in response")

            # Fallback: check if page load refreshed the sessionUserUP cookie
            all_cookies = context.cookies()
            for cookie in all_cookies:
                if cookie["name"] == "sessionUserUP" and cookie["value"] != session_token:
                    if jwt_is_valid(cookie["value"]):
                        hours_left = (jwt_exp(cookie["value"]) - now) / 3600
                        print(f"  Page load refreshed JWT (valid for {hours_left:.1f}h)")
                        write_cookie("sessionUserUP", cookie["value"])
                        browser.close()
                        return 0

            print("  ::warning::Cookie refresh failed — build will use existing cookies")
            browser.close()
            return 0

    except Exception as e:
        print(f"  ::warning::Browser refresh error: {type(e).__name__}: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
