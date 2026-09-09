#!/usr/bin/env python3
"""
Generate structured release notes (markdown) for the current build.

Reads environment variables (set by the workflow):
  NEXT_VER_CODE   — sequential build number (e.g. "260001")
  APK_VERSION     — JioHotstar version name (e.g. "26.07.20.3")
  APK_VERSION_CODE— JioHotstar version code from AndroidManifest
  FINAL_NAME      — final APK filename (e.g. "JioHotstar-Premium-v26.07.20.3-arm64.apk")
  ARCH            — target architecture (e.g. "arm64-v8a")

Output: writes markdown to stdout, suitable for `gh release create --notes-file -`.
"""
from __future__ import annotations

import os
import sys
import urllib.parse
from datetime import datetime, timezone


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default) or default


def main() -> int:
    next_ver_code = env("NEXT_VER_CODE")
    apk_version = env("APK_VERSION", "unknown")
    apk_vcode = env("APK_VERSION_CODE", "unknown")
    final_name = env("FINAL_NAME", "JioHotstar-Premium.apk")
    arch = env("ARCH", "arm64-v8a")
    variant = env("APP_VARIANT", "mobile").lower()
    repo = os.environ.get("GITHUB_REPOSITORY", "gramnaters/patcher-build")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    is_tv = variant == "tv"
    app_label = "JioHotstar TV" if is_tv else "JioHotstar Premium"
    pkg = "in.startv.hotstar (Android TV)" if is_tv else "in.startv.hotstar"

    # Build download URL for the asset
    asset_url = f"{server}/{repo}/releases/download/{next_ver_code}/{urllib.parse.quote(final_name)}"

    # Source APKMirror URL
    if is_tv:
        apkmirror_url = "https://www.apkmirror.com/apk/jiostar-india-private-limited/jiohotstar-3/"
    else:
        apkmirror_url = "https://www.apkmirror.com/apk/jiostar-india-private-limited/jiostar-hotstar/"

    lines = [
        f"## {app_label} v{apk_version}",
        "",
        f"**Build**: `{next_ver_code}`  •  **Built**: {now}",
        "",
        "---",
        "",
        "### 📦 Download",
        "",
        f"[**{final_name}**]({asset_url})",
        "",
        f"Architecture: `{arch}`  •  Package: `{pkg}`  •  Version code: `{apk_vcode}`",
        "",
    ]

    # Obtainium install instructions only make sense for mobile (Obtainium
    # is a phone app; Android TV is typically sideloaded manually).
    if not is_tv:
        lines += [
            "### 🔄 Install via Obtanium",
            "",
            "Add this repo to [Obtainium](https://obtainium.imranr.dev/) for auto-updates:",
            "```",
            f"{server}/{repo}",
            "```",
            "Or import the [Obtainium config JSON]("
            f"{server}/{repo}/raw/main/obtainium-config.json) directly.",
            "",
        ]

    lines += [
        "### 📋 Details",
        "",
        f"- **JioHotstar version**: `{apk_version}`",
        f"- **Variant**: `{'Android TV' if is_tv else 'Mobile'}`",
        f"- **Source**: [APKMirror]({apkmirror_url})",
        f"- **Patches**: cookie injection (CookieSeeder + IdentityRepository)",
        f"- **Architecture**: `{arch}`",
        f"- **Build number**: `{next_ver_code}`",
        "",
        "### ⚙️ What's patched",
        "",
        "- Premium cookie injection at app startup (`CookieSeeder.seedIfNeeded`)",
        "- IdentityRepository token fallback (auto-fills user token + media token when missing)",
        "- Removed split-APK requirement (single universal APK)",
        "- Native libs extracted into base APK (no split needed)",
        "",
        "### 🍪 Cookies",
        "",
        "Cookies are bundled inside the APK under `assets/cookies/`. Update them by",
        "editing the files in `cookies/` and pushing to `main` — a new build will",
        "be triggered automatically.",
        "",
        "### ⚠️ Disclaimer",
        "",
        "This is an unofficial modification of JioHotstar for personal use only. ",
        "Use at your own risk. The maintainers are not affiliated with JioStar or Disney.",
        "",
        f"---",
        f"<sub>Built with [gramnaters/patcher-build]({server}/{repo})</sub>",
    ]

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
