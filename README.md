# JioHotstar Premium AutoBuild

Automated JioHotstar patcher — builds a ready-to-install premium APK with cookie injection. No root required. Scheduled builds every 6 hours.

<!-- LATEST_BUILD_START -->
| Build | Version | APK | Date |
|-------|---------|-----|------|
| `260110` | `26.08.31.3` | [Download](https://github.com/gramnaters/patcher-build/releases/download/260110/JioHotstar-Premium-v26.08.31.3-arm64.apk) | [Release](https://github.com/gramnaters/patcher-build/releases/tag/260110) |
<!-- LATEST_BUILD_END -->

> **Android TV?** See [JioHotstar (Android TV)](#-android-tv) — a separate build with its own releases and tags.

## 📲 Install via Obtainium (recommended)

Install [Obtainium](https://obtainium.imranr.dev/) from F-Droid or GitHub, then add this app:

[![Add to Obtainium](https://raw.githubusercontent.com/ImranR98/Obtainium/refs/heads/main/assets/graphics/badge_obtainium.png)](https://apps.obtainium.imranr.dev/redirect?r=obtainium%3A%2F%2Fapp%2F%7B%22id%22%3A%22in.startv.hotstar%22%2C%22name%22%3A%22JioHotstar%20Premium%22%2C%22author%22%3A%22gramnaters%22%2C%22url%22%3A%22https%3A%2F%2Fgithub.com%2Fgramnaters%2Fpatcher-build%22%2C%22additionalSettings%22%3A%22%7B%5C%22includePrereleases%5C%22%3Afalse%2C%5C%22fallbackToOlderReleases%5C%22%3Atrue%2C%5C%22filterReleaseTitlesByRegEx%5C%22%3A%5C%22%5C%22%2C%5C%22filterReleaseNotesByRegEx%5C%22%3A%5C%22%5C%22%2C%5C%22verifyLatestTag%5C%22%3Afalse%2C%5C%22sortMethodChoice%5C%22%3A%5C%22date%5C%22%2C%5C%22useLatestAssetDateAsReleaseDate%5C%22%3Afalse%2C%5C%22releaseTitleAsVersion%5C%22%3Afalse%2C%5C%22trackOnly%5C%22%3Afalse%2C%5C%22versionExtractionRegEx%5C%22%3A%5C%22%5C%22%2C%5C%22matchGroupToUse%5C%22%3A%5C%22%5C%22%2C%5C%22versionDetection%5C%22%3Atrue%2C%5C%22releaseDateAsVersion%5C%22%3Afalse%2C%5C%22useVersionCodeAsOSVersion%5C%22%3Afalse%2C%5C%22apkFilterRegEx%5C%22%3A%5C%22JioHotstar-Premium%5C%22%2C%5C%22invertAPKFilter%5C%22%3Afalse%2C%5C%22autoApkFilterByArch%5C%22%3Atrue%2C%5C%22appName%5C%22%3A%5C%22%5C%22%2C%5C%22appAuthor%5C%22%3A%5C%22%5C%22%2C%5C%22shizukuPretendToBeGooglePlay%5C%22%3Afalse%2C%5C%22allowInsecure%5C%22%3Afalse%2C%5C%22exemptFromBackgroundUpdates%5C%22%3Afalse%2C%5C%22skipUpdateNotifications%5C%22%3Afalse%2C%5C%22about%5C%22%3A%5C%22Automated%20JioHotstar%20premium%20build%20with%20cookie%20injection.%20Updated%20every%206%20hours.%5C%22%2C%5C%22refreshBeforeDownload%5C%22%3Afalse%2C%5C%22includeZips%5C%22%3Afalse%2C%5C%22zippedApkFilterRegEx%5C%22%3A%5C%22%5C%22%7D%22%7D)
> If the button doesn't work, download [`obtainium-config.json`](https://github.com/gramnaters/patcher-build/blob/main/obtainium-config.json) and import it manually via **Obtainium → Import/Export → Import**.

After importing, Obtainium will:

- Detect new builds automatically (every 6 hours when CI runs)
- Download the latest `JioHotstar-Premium-*.apk` asset
- Notify you when an update is available
- Install it with a single tap (root or Shizuku recommended for silent installs)

## 📦 Manual download

Browse all releases: **[github.com/gramnaters/patcher-build/releases](https://github.com/gramnaters/patcher-build/releases)**

Each release contains a single APK:

- Filename: `JioHotstar-Premium-v<version>-arm64.apk`
- Architecture: `arm64-v8a`
- Size: ~75 MB
- Signed with a self-signed certificate

## 📺 Android TV

A separate Android TV build (`in.startv.hotstar`, leanback variant) is published
under its own `tv<build>` tags and releases, updated on its own schedule:

- Filename: `JioHotstar-TV-v<version>-universal.apk` (works on any TV — arm64-v8a, armeabi-v7a, x86)
- Workflows: `ci-tv.yml` (checker) → `build-tv.yml` (build + release)

## ⚙️ How it works

```
1. CI runs every 6 hours (ci.yml)
2. Check APKMirror for latest JioHotstar version (scripts/check_update.py)
3. If new version → trigger build.yml
4. Download APK via Cloudflare bypass services (scripts/download_apk.py)
5. Decompile with apktool
6. Inject cookie seeder smali patches (patches/)
7. Patch auth interceptor (IdentityRepository)
8. Recompile + sign with self-signed keystore
9. Publish as GitHub Release with sequential build number
10. Cleanup old releases + workflow runs (cleanup.yml)
```

## 🔧 Build schedule

| Workflow      | Schedule                      | Purpose                                                   |
| ------------- | ----------------------------- | --------------------------------------------------------- |
| `ci.yml`      | Every 6 hours (`0 */6 * * *`) | Check for new mobile versions on APKMirror                |
| `build.yml`   | Triggered by CI               | Build + publish new mobile release                        |
| `ci-tv.yml`   | Manual only                   | Check for new Android TV versions (manual trigger)        |
| `build-tv.yml`| Manual only                   | Build + publish Android TV release                        |
| `refresh-cookies.yml` | Every 12 hours       | Refresh cookies; rebuild mobile if JWT near expiry        |
| `cleanup.yml` | After each build              | Keep latest 5 releases, delete workflow runs >3 days old  |

You can trigger builds manually via the **Actions** tab → **CI** / **CI TV** → **Run workflow**.

## 🍪 Updating cookies

Cookies are bundled into the APK at build time under `assets/cookies/`. To update them:

1. Open `cookies/` in your fork
2. Edit each file:
  - `sessionUserUP.txt` — JWT user token (from `Authorization: Bearer` header on hotstar.com)
  - `userHID.txt` — Hardware ID (e.g. `acn|282893298745332`)
  - `userPID.txt` — Platform ID (32-char hex)
  - `deviceId.txt` — Device ID (e.g. `921e4d-5b3a38-767889-e36ac`)
  - `media_token.txt` — Media token (optional)
3. Commit to `main` — a new build will trigger automatically

> Cookies can be exported from a browser session logged into hotstar.com using DevTools → Application → Cookies.

## 📁 Repository structure

```
.
├── .github/
│   └── workflows/
│       ├── build.yml         # Main build + release workflow
│       ├── ci.yml            # Scheduled update checker (every 6h)
│       └── cleanup.yml       # Old release + run cleanup
├── cookies/                  # Hotstar auth cookies (txt files)
├── patches/                  # Smali patches
│   ├── CookieFileReader.smali
│   └── cookie-seeder.smali
├── scripts/
│   ├── download_apk.py       # APKMirror downloader (CF bypass)
│   ├── check_update.py       # Lightweight version check
│   ├── patch_userprefs.py    # Auth token injection patch
│   ├── generate_release_notes.py
│   └── update_readme.py
├── obtainium-config.json     # Obtainium import config
└── README.md
```

## ⚠️ Disclaimer

This is an unofficial modification of JioHotstar for personal and educational use only. The maintainers are not affiliated with JioStar, Disney, or any related entity. Use at your own risk and in compliance with applicable terms of service.
