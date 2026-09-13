#!/usr/bin/env python3
"""
Patch UserPreferences.smali to inject cookies for JioHotstar.

The JioHotstar auth getters are Kotlin suspend functions whose real
descriptor carries an obfuscated continuation type, e.g.
  .method public final getUserTokenValue(LAu/a;)Ljava/lang/Object;
We preserve the ORIGINAL method signature/descriptor and only swap the
body so every existing call site keeps resolving, then return our
 injected values from CookieSeeder static fields.

v6: Adds JWT expiry check — returns null if token expired, letting
the app's native login screen appear instead of looping errors.

Usage: python3 patch_userprefs.py <decompiled_dir>
"""
import re
import sys
from pathlib import Path


def patch_method(content: str, method_name: str, getter: str) -> str:
    """Replace a suspend getter's body, keeping its original descriptor."""
    pattern = re.compile(
        r"(\.method [^\n]*"
        + re.escape(method_name)
        + r"\(L[^)]*;\)Ljava/lang/Object;[\s\S]*?\.end method)"
    )
    match = pattern.search(content)
    if not match:
        return content  # Method not found, skip

    block = match.group(1)
    sig_line = block.splitlines()[0]
    param_match = re.search(r"\(([^)]*)\)", sig_line)
    param_desc = param_match.group(1) if param_match else ""
    generic_desc = param_desc.rstrip(";") + "<"

    new_body = f"""{sig_line}
    .locals 1
    .param p1    # {param_desc}
        .annotation build Lorg/jetbrains/annotations/NotNull;
        .end annotation
    .end param
    .annotation system Ldalvik/annotation/Signature;
        value = {{
            "(",
            "{generic_desc}",
            "-",
            "Ljava/lang/String;",
            ">;)",
            "Ljava/lang/Object;"
        }}
    .end annotation

    .annotation build Lorg/jetbrains/annotations/Nullable;
    .end annotation

    # PATCH v6: Check JWT expiry — return null if expired (graceful login screen)
    invoke-static {{}}, Lcom/hotstar/patch/CookieSeeder;->isTokenValid()Z
    move-result v0
    if-eqz v0, :return_null

    # Token valid — return injected value
    invoke-static {{}}, Lcom/hotstar/patch/CookieSeeder;->{getter}()Ljava/lang/String;
    move-result-object v0
    return-object v0

    :return_null
    const/4 v0, 0x0
    return-object v0
.end method"""
    return content[: match.start()] + new_body + content[match.end() :]


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

    patch_map = {
        "getUserTokenValue": "getInjectedUserToken",
        "getMediaTokenValue": "getInjectedMediaToken",
        "getHidValue": "getInjectedHid",
        "getPidValue": "getInjectedPid",
    }
    for method, getter in patch_map.items():
        before = content
        content = patch_method(content, method, getter)
        if content != before:
            print(f"  Patched {method}")

    up_path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()