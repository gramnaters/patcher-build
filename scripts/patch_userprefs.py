#!/usr/bin/env python3
"""
Patch UserPreferences.smali to inject cookies for JioHotstar 26.07.20.3

The new JioHotstar auth architecture uses:
  - UserPreferences.getUserTokenValue() → reads "USER_IDENTITY" from DataStore
  - UserPreferences.getMediaTokenValue() → reads "media_token" from DataStore
  - UserPreferences.getHidValue() → reads "HID" from DataStore
  - UserPreferences.getPidValue() → reads "pid" from DataStore

Instead of trying to write to DataStore (complex), we REPLACE these methods
to return our injected values from CookieSeeder static fields.

Usage: python3 patch_userprefs.py <decompiled_dir>
"""
import re
import sys
from pathlib import Path


def patch_method(content: str, method_sig: str, new_body: str) -> str:
    """Replace a method's body while keeping its signature and annotations."""
    # Match from .method line to .end method
    # method_sig is like "getUserTokenValue(LOt/a;)Ljava/lang/Object;"
    pattern = rf'(\.method [^\n]*{re.escape(method_sig)}[\s\S]*?\.end method)'
    match = re.search(pattern, content)
    if not match:
        return content  # Method not found, skip
    return content[:match.start()] + new_body + content[match.end():]


def main():
    if len(sys.argv) < 2:
        print("Usage: patch_userprefs.py <decompiled_dir>")
        sys.exit(1)

    decompiled = Path(sys.argv[1])
    up_path = None
    for smali_dir in sorted(decompiled.glob("smali*")):
        candidate = smali_dir / "com/hotstar/identitylib/identitydata/preference/UserPreferences.smali"
        if candidate.exists():
            up_path = candidate
            break

    if not up_path:
        print("::error::UserPreferences.smali not found")
        sys.exit(1)

    print(f"Patching: {up_path}")
    content = up_path.read_text(encoding="utf-8")

    if "CookieSeeder" in content:
        print("  Already patched — skipping")
        return

    new_get_user_token_value = '''.method public final getUserTokenValue(LOt/a;)Ljava/lang/Object;
    .locals 1
    .param p1    # LOt/a;
        .annotation build Lorg/jetbrains/annotations/NotNull;
        .end annotation
    .end param
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "(",
            "LOt/a<",
            "-",
            "Ljava/lang/String;",
            ">;)",
            "Ljava/lang/Object;"
        }
    .end annotation
    .annotation build Lorg/jetbrains/annotations/Nullable;
    .end annotation

    # PATCH: return injected user token from CookieSeeder
    invoke-static {}, Lcom/hotstar/patch/CookieSeeder;->getInjectedUserToken()Ljava/lang/String;
    move-result-object v0
    return-object v0
.end method'''

    new_get_media_token_value = '''.method public final getMediaTokenValue(LOt/a;)Ljava/lang/Object;
    .locals 1
    .param p1    # LOt/a;
        .annotation build Lorg/jetbrains/annotations/NotNull;
        .end annotation
    .end param
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "(",
            "LOt/a<",
            "-",
            "Ljava/lang/String;",
            ">;)",
            "Ljava/lang/Object;"
        }
    .end annotation
    .annotation build Lorg/jetbrains/annotations/Nullable;
    .end annotation

    # PATCH: return injected media token from CookieSeeder
    invoke-static {}, Lcom/hotstar/patch/CookieSeeder;->getInjectedMediaToken()Ljava/lang/String;
    move-result-object v0
    return-object v0
.end method'''

    new_get_hid_value = '''.method public final getHidValue(LOt/a;)Ljava/lang/Object;
    .locals 1
    .param p1    # LOt/a;
        .annotation build Lorg/jetbrains/annotations/NotNull;
        .end annotation
    .end param
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "(",
            "LOt/a<",
            "-",
            "Ljava/lang/String;",
            ">;)",
            "Ljava/lang/Object;"
        }
    .end annotation
    .annotation build Lorg/jetbrains/annotations/Nullable;
    .end annotation

    # PATCH: return injected HID from CookieSeeder
    invoke-static {}, Lcom/hotstar/patch/CookieSeeder;->getInjectedHid()Ljava/lang/String;
    move-result-object v0
    return-object v0
.end method'''

    new_get_pid_value = '''.method public final getPidValue(LOt/a;)Ljava/lang/Object;
    .locals 1
    .param p1    # LOt/a;
        .annotation build Lorg/jetbrains/annotations/NotNull;
        .end annotation
    .end param
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "(",
            "LOt/a<",
            "-",
            "Ljava/lang/String;",
            ">;)",
            "Ljava/lang/Object;"
        }
    .end annotation
    .annotation build Lorg/jetbrains/annotations/Nullable;
    .end annotation

    # PATCH: return injected PID from CookieSeeder
    invoke-static {}, Lcom/hotstar/patch/CookieSeeder;->getInjectedPid()Ljava/lang/String;
    move-result-object v0
    return-object v0
.end method'''

    content = patch_method(content, "getUserTokenValue", new_get_user_token_value)
    content = patch_method(content, "getMediaTokenValue", new_get_media_token_value)
    content = patch_method(content, "getHidValue", new_get_hid_value)
    content = patch_method(content, "getPidValue", new_get_pid_value)

    up_path.write_text(content, encoding="utf-8")
    print("  Patched getUserTokenValue, getMediaTokenValue, getHidValue, getPidValue")


if __name__ == "__main__":
    main()
