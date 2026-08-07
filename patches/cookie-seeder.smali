.class public Lcom/hotstar/patch/CookieSeeder;
.super Ljava/lang/Object;

# JioHotstar Auth Injection v3.0
#
# ARCHITECTURE (learned from full auth chain analysis):
# - App does NOT use android.webkit.CookieManager for API calls
# - App does NOT use cookie names like "sessionUserUP" (that's web-only)
# - App uses HTTP headers: X-Hs-UserToken, x-hs-mediatoken
# - Auth interceptor Lwe/I reads tokens from identityLibrary.i() and .d()
# - identityLibrary = LDf/d (IdentityRepository)
#   - field 'a' = user token (memory cache) -> DataStore key "USER_IDENTITY"
#   - field 'g' = media token (memory cache) -> DataStore key "media_token"
# - LDf/d.i() checks field 'a' first, falls back to DataStore
#
# STRATEGY:
# 1. CookieSeeder reads tokens from assets at startup
# 2. Stores them in STATIC fields on this class
# 3. LDf/d.i() and d() are patched to check our static fields first
# 4. If found -> store in memory cache (field a/g) -> return token
# 5. This ensures every API request gets our injected token
#
# CRITICAL: In static methods, p0=v0 (parameter alias).
# Save p0 to v13 immediately to avoid register corruption.

# Static fields: token cache for LDf/d to read
.field private static injectedUserToken:Ljava/lang/String;
.field private static injectedMediaToken:Ljava/lang/String;

# Static getters called from patched LDf/d methods
.method public static getInjectedUserToken()Ljava/lang/String;
    .registers 1
    sget-object v0, Lcom/hotstar/patch/CookieSeeder;->injectedUserToken:Ljava/lang/String;
    return-object v0
.end method

.method public static getInjectedMediaToken()Ljava/lang/String;
    .registers 1
    sget-object v0, Lcom/hotstar/patch/CookieSeeder;->injectedMediaToken:Ljava/lang/String;
    return-object v0
.end method

.method public constructor <init>()V
    .registers 1
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method public static seedIfNeeded(Landroid/content/Context;)V
    .registers 14
    .param p0, "context"  # Landroid/content/Context;

    # Save context to v13 (p0=v0 alias would be corrupted)
    move-object v13, p0

    const-string v0, "HotstarPatch"
    const-string v1, "hotstar_patch_prefs"
    const-string v2, "is_seeded"

    # Check if already seeded
    const/4 v3, 0x0
    invoke-virtual {v13, v1, v3}, Landroid/content/Context;->getSharedPreferences(Ljava/lang/String;I)Landroid/content/SharedPreferences;
    move-result-object v4

    invoke-interface {v4, v2, v3}, Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z
    move-result v5
    if-eqz v5, :do_seed

    # Already seeded - restore static fields from prefs (survives process restart)
    const-string v6, "cached_user_token"
    invoke-interface {v4, v6, v3}, Landroid/content/SharedPreferences;->getString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7
    if-eqz v7, :skip_user_restore
    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedUserToken:Ljava/lang/String;
    :skip_user_restore

    const-string v6, "cached_media_token"
    invoke-interface {v4, v6, v3}, Landroid/content/SharedPreferences;->getString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7
    if-eqz v7, :skip_media_restore
    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedMediaToken:Ljava/lang/String;
    :skip_media_restore

    const-string v3, "Already seeded, restored static fields from prefs"
    invoke-static {v0, v3}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I
    return-void

    :do_seed
    const-string v3, "Seeding auth tokens for JioHotstar..."
    invoke-static {v0, v3}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    # === PRIMARY: Read and cache user token (sessionUserUP = USER_IDENTITY) ===
    const-string v6, "cookies/sessionUserUP.txt"
    invoke-static {v13, v6}, Lcom/hotstar/patch/CookieFileReader;->readAsset(Landroid/content/Context;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7

    if-eqz v7, :skip_user_token
    invoke-virtual {v7}, Ljava/lang/String;->length()I
    move-result v8
    if-lez v8, :skip_user_token

    # Store in STATIC field for LDf/d.i() to read
    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedUserToken:Ljava/lang/String;

    # Also persist in SharedPreferences (survives process restart)
    invoke-interface {v4}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v8
    const-string v9, "cached_user_token"
    invoke-interface {v8, v9, v7}, Landroid/content/SharedPreferences$Editor;->putString(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;
    invoke-interface {v8}, Landroid/content/SharedPreferences$Editor;->apply()V

    const-string v8, "Cached user token for LDf/d injection"
    invoke-static {v0, v8}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    :skip_user_token

    # === Read and cache media token ===
    const-string v6, "cookies/media_token.txt"
    invoke-static {v13, v6}, Lcom/hotstar/patch/CookieFileReader;->readAsset(Landroid/content/Context;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7

    if-eqz v7, :skip_media_token
    invoke-virtual {v7}, Ljava/lang/String;->length()I
    move-result v8
    if-lez v8, :skip_media_token

    # Store in STATIC field for LDf/d.d() to read
    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedMediaToken:Ljava/lang/String;

    # Also persist in SharedPreferences
    invoke-interface {v4}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v8
    const-string v9, "cached_media_token"
    invoke-interface {v8, v9, v7}, Landroid/content/SharedPreferences$Editor;->putString(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;
    invoke-interface {v8}, Landroid/content/SharedPreferences$Editor;->apply()V

    const-string v8, "Cached media token for LDf/d injection"
    invoke-static {v0, v8}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    :skip_media_token

    # === Write device_id to StarApp SharedPreferences ===
    const-string v6, "cookies/deviceId.txt"
    invoke-static {v13, v6}, Lcom/hotstar/patch/CookieFileReader;->readAsset(Landroid/content/Context;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7

    if-eqz v7, :skip_prefs
    invoke-virtual {v7}, Ljava/lang/String;->length()I
    move-result v8
    if-lez v8, :skip_prefs

    const-string v8, "StarApp"
    const/4 v3, 0x0
    invoke-virtual {v13, v8, v3}, Landroid/content/Context;->getSharedPreferences(Ljava/lang/String;I)Landroid/content/SharedPreferences;
    move-result-object v6

    invoke-interface {v6}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v8

    const-string v9, "guid"
    invoke-interface {v8, v9, v7}, Landroid/content/SharedPreferences$Editor;->putString(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;

    invoke-interface {v8}, Landroid/content/SharedPreferences$Editor;->apply()V

    const-string v8, "Seeded device_id into StarApp prefs"
    invoke-static {v0, v8}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    :skip_prefs

    # Mark as seeded
    invoke-interface {v4}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v6
    const/4 v7, 0x1
    invoke-interface {v6, v2, v7}, Landroid/content/SharedPreferences$Editor;->putBoolean(Ljava/lang/String;Z)Landroid/content/SharedPreferences$Editor;
    invoke-interface {v6}, Landroid/content/SharedPreferences$Editor;->apply()V

    const-string v6, "Auth token seeding complete"
    invoke-static {v0, v6}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    return-void
.end method
