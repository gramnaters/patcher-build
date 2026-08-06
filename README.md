# JioHotstar Premium AutoBuild

Automated JioHotstar patcher — builds a ready-to-install premium APK with cookie injection. No root required.

## What's New

- **Auto-downloads latest APK from APKMirror** — no more manual `apk_url.txt`
- Scrapes APKMirror for the latest JioHotstar version automatically
- Handles XAPK/APKS bundles (extracts base.apk + arm64 split)
- Runs every 6 hours via GitHub Actions

## Usage

1. **Fork** this repository
2. **Add your cookies** to `cookies/`:
   - `sessionUserUP.txt` — JWT user token
   - `userHID.txt` — Hardware ID
   - `userPID.txt` — Platform ID
   - `deviceId.txt` — Device ID
   - `media_token.txt` — Media token (optional)
3. **Push to `main`** — build runs automatically
4. **Download** the APK from GitHub Releases

> Cookies can be exported from a browser session logged into hotstar.com

## How It Works

```
1. Scrape APKMirror for latest JioHotstar version
2. Download the APK (handle XAPK bundles)
3. Decompile with apktool
4. Inject cookie seeder smali patches
5. Patch auth interceptor (IdentityRepository)
6. Recompile + sign
7. Publish as GitHub Release
```

## Files

```
cookies/          — Your Hotstar cookies (txt files)
patches/          — Smali patches (CookieSeeder, CookieFileReader)
scripts/          — APK downloader (APKMirror scraper)
.github/workflows/ — CI build pipeline
```
