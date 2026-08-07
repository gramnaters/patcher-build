#!/usr/bin/env python3
"""
Update README.md with the latest build version + release URL.

Usage:
    python3 scripts/update_readme.py <NEXT_VER_CODE> <APK_VERSION> <GITHUB_REPOSITORY>

Updates the placeholder `<!-- LATEST_BUILD -->` block in README.md with
the new build info. The block is delimited by:
    <!-- LATEST_BUILD_START -->
    ...
    <!-- LATEST_BUILD_END -->

If the markers aren't present, the script is a no-op.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "Usage: update_readme.py <NEXT_VER_CODE> <APK_VERSION> <GITHUB_REPOSITORY>",
            file=sys.stderr,
        )
        return 1

    next_ver_code = sys.argv[1]
    apk_version = sys.argv[2]
    repo = sys.argv[3]
    server = "https://github.com"

    readme = Path("README.md")
    if not readme.exists():
        print("README.md not found", file=sys.stderr)
        return 1

    content = readme.read_text(encoding="utf-8")

    # Pattern: between START and END markers
    pattern = re.compile(
        r"<!-- LATEST_BUILD_START -->[\s\S]*?<!-- LATEST_BUILD_END -->",
        re.MULTILINE,
    )
    if not pattern.search(content):
        print("LATEST_BUILD markers not found in README.md — skipping", file=sys.stderr)
        return 0

    new_block = f"""<!-- LATEST_BUILD_START -->
| Build | Version | APK | Date |
|-------|---------|-----|------|
| `{next_ver_code}` | `{apk_version}` | [Download]({server}/{repo}/releases/download/{next_ver_code}/JioHotstar-Premium-v{apk_version}-arm64.apk) | [Release]({server}/{repo}/releases/tag/{next_ver_code}) |
<!-- LATEST_BUILD_END -->"""

    new_content = pattern.sub(new_block, content)
    readme.write_text(new_content, encoding="utf-8")
    print(f"Updated README.md: build {next_ver_code}, version {apk_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
