.class public Lcom/hotstar/patch/CookieSeeder;
.super Ljava/lang/Object;

# JioHotstar Auth Injection v4.0
#
# ARCHITECTURE (for JioHotstar 26.07.20.3+):
# - App uses UserPreferences class for token storage
# - UserPreferences.getUserTokenValue() reads "USER_IDENTITY" from DataStore
# - UserPreferences.getMediaTokenValue() reads "media_token" from DataStore
# - UserPreferences.getHidValue() reads "HID" from DataStore
# - UserPreferences.getPidValue() reads "pid" from DataStore
# - These methods are PATCHED to call CookieSeeder getters directly
#
# STRATEGY:
# 1. CookieSeeder reads tokens/HID/PID from assets/cookies/ at startup
# 2. Stores them in STATIC fields on this class
# 3. Patched UserPreferences methods return these static values
# 4. Every API request gets the injected token via the auth interceptor

# Static fields: injected credentials
.field private static injectedUserToken:Ljava/lang/String;
.field private static injectedMediaToken:Ljava/lang/String;
.field private static injectedHid:Ljava/lang/String;
.field private static injectedPid:Ljava/lang/String;

# Static getters called from patched UserPreferences methods
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

.method public static getInjectedHid()Ljava/lang/String;
    .registers 1
    sget-object v0, Lcom/hotstar/patch/CookieSeeder;->injectedHid:Ljava/lang/String;
    return-object v0
.end method

.method public static getInjectedPid()Ljava/lang/String;
    .registers 1
    sget-object v0, Lcom/hotstar/patch/CookieSeeder;->injectedPid:Ljava/lang/String;
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

    const-string v6, "cached_hid"
    invoke-interface {v4, v6, v3}, Landroid/content/SharedPreferences;->getString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7
    if-eqz v7, :skip_hid_restore
    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedHid:Ljava/lang/String;
    :skip_hid_restore

    const-string v6, "cached_pid"
    invoke-interface {v4, v6, v3}, Landroid/content/SharedPreferences;->getString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7
    if-eqz v7, :skip_pid_restore
    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedPid:Ljava/lang/String;
    :skip_pid_restore

    const-string v3, "Already seeded, restored static fields from prefs"
    invoke-static {v0, v3}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I
    return-void

    :do_seed
    const-string v3, "Seeding auth tokens for JioHotstar..."
    invoke-static {v0, v3}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    # === Read and cache user token (sessionUserUP = USER_IDENTITY) ===
    const-string v6, "cookies/sessionUserUP.txt"
    invoke-static {v13, v6}, Lcom/hotstar/patch/CookieFileReader;->readAsset(Landroid/content/Context;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7

    if-eqz v7, :skip_user_token
    invoke-virtual {v7}, Ljava/lang/String;->length()I
    move-result v8
    if-lez v8, :skip_user_token

    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedUserToken:Ljava/lang/String;

    invoke-interface {v4}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v8
    const-string v9, "cached_user_token"
    invoke-interface {v8, v9, v7}, Landroid/content/SharedPreferences$Editor;->putString(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;
    invoke-interface {v8}, Landroid/content/SharedPreferences$Editor;->apply()V

    const-string v8, "Cached user token"
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

    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedMediaToken:Ljava/lang/String;

    invoke-interface {v4}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v8
    const-string v9, "cached_media_token"
    invoke-interface {v8, v9, v7}, Landroid/content/SharedPreferences$Editor;->putString(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;
    invoke-interface {v8}, Landroid/content/SharedPreferences$Editor;->apply()V

    const-string v8, "Cached media token"
    invoke-static {v0, v8}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    :skip_media_token

    # === Read and cache HID ===
    const-string v6, "cookies/userHID.txt"
    invoke-static {v13, v6}, Lcom/hotstar/patch/CookieFileReader;->readAsset(Landroid/content/Context;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7

    if-eqz v7, :skip_hid
    invoke-virtual {v7}, Ljava/lang/String;->length()I
    move-result v8
    if-lez v8, :skip_hid

    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedHid:Ljava/lang/String;

    invoke-interface {v4}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v8
    const-string v9, "cached_hid"
    invoke-interface {v8, v9, v7}, Landroid/content/SharedPreferences$Editor;->putString(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;
    invoke-interface {v8}, Landroid/content/SharedPreferences$Editor;->apply()V

    const-string v8, "Cached HID"
    invoke-static {v0, v8}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    :skip_hid

    # === Read and cache PID ===
    const-string v6, "cookies/userPID.txt"
    invoke-static {v13, v6}, Lcom/hotstar/patch/CookieFileReader;->readAsset(Landroid/content/Context;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7

    if-eqz v7, :skip_pid
    invoke-virtual {v7}, Ljava/lang/String;->length()I
    move-result v8
    if-lez v8, :skip_pid

    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedPid:Ljava/lang/String;

    invoke-interface {v4}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v8
    const-string v9, "cached_pid"
    invoke-interface {v8, v9, v7}, Landroid/content/SharedPreferences$Editor;->putString(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;
    invoke-interface {v8}, Landroid/content/SharedPreferences$Editor;->apply()V

    const-string v8, "Cached PID"
    invoke-static {v0, v8}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    :skip_pid

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
