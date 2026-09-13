.class public Lcom/hotstar/patch/CookieSeeder;
.super Ljava/lang/Object;

# JioHotstar Auth Injection v6.0 — with graceful expiry handling
#
# ARCHITECTURE:
# - CookieSeeder reads sessionUserUP, userUP, device creds from assets/cookies/
# - On each launch: checks if cached JWT is expired
# - If expired: clears static fields → app shows login screen (graceful)
# - isTokenValid() checks expiry on every call (for mid-session expiry)
# - Patched UserPreferences methods return static values only when valid
#
# FIELDS: injected credentials
.field private static injectedUserToken:Ljava/lang/String;
.field private static injectedUserUP:Ljava/lang/String;
.field private static injectedHid:Ljava/lang/String;
.field private static injectedPid:Ljava/lang/String;
.field private static injectedDeviceId:Ljava/lang/String;

# Static getters
.method public static getInjectedUserToken()Ljava/lang/String;
    .registers 1
    sget-object v0, Lcom/hotstar/patch/CookieSeeder;->injectedUserToken:Ljava/lang/String;
    return-object v0
.end method

.method public static getInjectedUserUP()Ljava/lang/String;
    .registers 1
    sget-object v0, Lcom/hotstar/patch/CookieSeeder;->injectedUserUP:Ljava/lang/String;
    return-object v0
.end method

.method public static getInjectedMediaToken()Ljava/lang/String;
    .registers 1
    sget-object v0, Lcom/hotstar/patch/CookieSeeder;->injectedUserToken:Ljava/lang/String;
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

.method public static getInjectedDeviceId()Ljava/lang/String;
    .registers 1
    sget-object v0, Lcom/hotstar/patch/CookieSeeder;->injectedDeviceId:Ljava/lang/String;
    return-object v0
.end method

# Returns true if the current injected token is not expired
# Called by patched UserPreferences getters on every API call
.method public static isTokenValid()Z
    .registers 7
    sget-object v0, Lcom/hotstar/patch/CookieSeeder;->injectedUserToken:Ljava/lang/String;
    if-eqz v0, :return_false

    invoke-virtual {v0}, Ljava/lang/String;->length()I
    move-result v1
    if-lez v1, :return_false

    # check_jwt: token is non-null and non-empty, check JWT exp
    invoke-static {v0}, Lcom/hotstar/patch/CookieSeeder;->jwtExp(Ljava/lang/String;)J
    move-result-wide v2

    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J
    move-result-wide v4
    const-wide/16 v6, 0x3e8
    div-long/2addr v4, v6

    # v2 = exp (seconds), v4 = now (seconds)
    # v2 - v4 = remaining seconds
    sub-long/2addr v2, v4

    # If remaining > 300 (5 min), token is valid
    const-wide/16 v4, 0x12c
    cmp-long v0, v2, v4
    if-lez v0, :return_false

    :return_true
    const/4 v0, 0x1
    return v0

    :return_false
    const/4 v0, 0x0
    return v0
.end method

# Clear all injected tokens (for graceful logout on expiry)
.method public static clearAll()V
    .registers 2
    const-string v0, "HotstarPatch"
    const-string v1, "Clearing all injected tokens (expired)"
    invoke-static {v0, v1}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I

    const-string v0, ""
    sput-object v0, Lcom/hotstar/patch/CookieSeeder;->injectedUserToken:Ljava/lang/String;
    sput-object v0, Lcom/hotstar/patch/CookieSeeder;->injectedUserUP:Ljava/lang/String;
    sput-object v0, Lcom/hotstar/patch/CookieSeeder;->injectedHid:Ljava/lang/String;
    sput-object v0, Lcom/hotstar/patch/CookieSeeder;->injectedPid:Ljava/lang/String;
    sput-object v0, Lcom/hotstar/patch/CookieSeeder;->injectedDeviceId:Ljava/lang/String;
    return-void
.end method

.method public constructor <init>()V
    .registers 1
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

# Decode JWT exp field (returns seconds since epoch, or 0 on error)
.method private static jwtExp(Ljava/lang/String;)J
    .registers 10
    :try_start
    const-wide/16 v0, 0x0

    # Split on "."
    const-string v2, "\\."
    invoke-virtual {p0, v2}, Ljava/lang/String;->split(Ljava/lang/String;)[Ljava/lang/String;
    move-result-object v3

    array-length v4, v3
    const/4 v5, 0x2
    if-ge v4, v5, :return_zero

    # Get payload part [1]
    const/4 v4, 0x1
    aget-object v3, v3, v4

    # Base64URL decode
    invoke-static {v3}, Lcom/hotstar/patch/CookieFileReader;->base64UrlDecode(Ljava/lang/String;)[B
    move-result-object v4

    if-eqz v4, :return_zero

    # Parse as string
    new-instance v5, Ljava/lang/String;
    invoke-direct {v5, v4}, Ljava/lang/String;-><init>([B)V

    # Find "exp": pattern — crude but reliable for JWT
    const-string v6, "\"exp\":"
    invoke-virtual {v5, v6}, Ljava/lang/String;->indexOf(Ljava/lang/String;)I
    move-result v7

    if-gez v7, :return_zero

    invoke-virtual {v6}, Ljava/lang/String;->length()I
    move-result v8
    add-int/2addr v7, v8

    # Skip whitespace
    :skip_ws
    invoke-virtual {v5}, Ljava/lang/String;->length()I
    move-result v8
    if-ge v7, v8, :parse_num
    invoke-virtual {v5, v7}, Ljava/lang/String;->charAt(I)C
    move-result v8
    const/16 v9, 0x20
    if-eq v8, v9, :parse_num
    add-int/lit8 v7, v7, 0x1
    goto :skip_ws

    :parse_num
    # Extract digits
    new-instance v2, Ljava/lang/StringBuilder;
    invoke-direct {v2}, Ljava/lang/StringBuilder;-><init>()V

    :digit_loop
    invoke-virtual {v5}, Ljava/lang/String;->length()I
    move-result v8
    if-ge v7, v8, :convert_num
    invoke-virtual {v5, v7}, Ljava/lang/String;->charAt(I)C
    move-result v8
    const/16 v9, 0x30
    if-lt v8, v9, :convert_num
    const/16 v9, 0x39
    if-gt v8, v9, :convert_num
    int-to-char v8, v8
    invoke-virtual {v2, v8}, Ljava/lang/StringBuilder;->append(C)Ljava/lang/StringBuilder;
    add-int/lit8 v7, v7, 0x1
    goto :digit_loop

    :convert_num
    invoke-virtual {v2}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v2
    invoke-virtual {v2}, Ljava/lang/String;->length()I
    move-result v8
    if-lez v8, :return_zero
    invoke-static {v2}, Ljava/lang/Long;->parseLong(Ljava/lang/String;)J
    move-result-wide v0
    return-wide v0

    :return_zero
    const-wide/16 v0, 0x0
    return-wide v0
    :try_end
    .catch Ljava/lang/Exception; {:try_start .. :try_end} :catch_all
    :catch_all
    const-wide/16 v0, 0x0
    return-wide v0
.end method

.method public static seedIfNeeded(Landroid/content/Context;)V
    .registers 15
    .param p0, "context"  # Landroid/content/Context;

    move-object v13, p0

    const-string v0, "HotstarPatch"
    const-string v1, "hotstar_patch_prefs"

    # Open prefs
    const/4 v3, 0x0
    invoke-virtual {v13, v1, v3}, Landroid/content/Context;->getSharedPreferences(Ljava/lang/String;I)Landroid/content/SharedPreferences;
    move-result-object v4

    # Check if we need to seed (always re-check JWT validity)
    const-string v2, "cached_user_token"
    invoke-interface {v4, v2, v3}, Landroid/content/SharedPreferences;->getString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7

    if-eqz v7, :do_seed

    # Have cached token — check if it's expired
    invoke-static {v7}, Lcom/hotstar/patch/CookieSeeder;->jwtExp(Ljava/lang/String;)J
    move-result-wide v8

    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J
    move-result-wide v10
    const-wide/16 v12, 0x3e8
    div-long/2addr v10, v12

    # Check: exp - now (in seconds)
    sub-long/2addr v8, v10

    # If exp > now + 300 (5 min buffer), token is still good — restore from prefs
    const-wide/16 v12, 0x12c
    cmp-long v2, v8, v12
    if-lez v2, :restore_from_prefs

    # Token expired — clear prefs cache and try re-seeding from assets
    const-string v2, "Cached token EXPIRED, clearing and re-seeding from assets"
    invoke-static {v0, v2}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I

    invoke-interface {v4}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v6
    invoke-interface {v6}, Landroid/content/SharedPreferences$Editor;->clear()Landroid/content/SharedPreferences$Editor;
    invoke-interface {v6}, Landroid/content/SharedPreferences$Editor;->apply()V
    goto :do_seed

    :restore_from_prefs
    # Restore all static fields from prefs (token is still valid)
    const-string v6, "cached_user_token"
    invoke-interface {v4, v6, v3}, Landroid/content/SharedPreferences;->getString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7
    if-eqz v7, :skip_r_user
    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedUserToken:Ljava/lang/String;
    :skip_r_user

    const-string v6, "cached_user_up"
    invoke-interface {v4, v6, v3}, Landroid/content/SharedPreferences;->getString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7
    if-eqz v7, :skip_r_up
    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedUserUP:Ljava/lang/String;
    :skip_r_up

    const-string v6, "cached_hid"
    invoke-interface {v4, v6, v3}, Landroid/content/SharedPreferences;->getString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7
    if-eqz v7, :skip_r_hid
    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedHid:Ljava/lang/String;
    :skip_r_hid

    const-string v6, "cached_pid"
    invoke-interface {v4, v6, v3}, Landroid/content/SharedPreferences;->getString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7
    if-eqz v7, :skip_r_pid
    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedPid:Ljava/lang/String;
    :skip_r_pid

    const-string v6, "cached_device_id"
    invoke-interface {v4, v6, v3}, Landroid/content/SharedPreferences;->getString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7
    if-eqz v7, :skip_r_did
    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedDeviceId:Ljava/lang/String;
    :skip_r_did

    const-string v2, "All fields restored from prefs"
    invoke-static {v0, v2}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I
    return-void

    :do_seed
    const-string v2, "Seeding auth tokens for JioHotstar..."
    invoke-static {v0, v2}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    # === Read sessionUserUP ===
    const-string v6, "cookies/sessionUserUP.txt"
    invoke-static {v13, v6}, Lcom/hotstar/patch/CookieFileReader;->readAsset(Landroid/content/Context;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7

    if-eqz v7, :skip_user_token
    invoke-virtual {v7}, Ljava/lang/String;->length()I
    move-result v8
    if-lez v8, :skip_user_token

    # token is non-empty, check expiry
    :check_token_expiry
    # Check if asset token is also expired
    invoke-static {v7}, Lcom/hotstar/patch/CookieSeeder;->jwtExp(Ljava/lang/String;)J
    move-result-wide v8
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J
    move-result-wide v10
    const-wide/16 v12, 0x3e8
    div-long/2addr v10, v12
    sub-long/2addr v8, v10
    const-wide/16 v10, 0x12c
    cmp-long v2, v8, v10
    if-lez v2, :asset_token_valid

    # Asset token also expired — don't seed, let app show login
    const-string v2, "Asset token ALSO expired — app will show login screen"
    invoke-static {v0, v2}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I
    goto :skip_user_token

    :asset_token_valid
    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedUserToken:Ljava/lang/String;

    invoke-interface {v4}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v8
    const-string v9, "cached_user_token"
    invoke-interface {v8, v9, v7}, Landroid/content/SharedPreferences$Editor;->putString(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;
    invoke-interface {v8}, Landroid/content/SharedPreferences$Editor;->apply()V
    :skip_user_token

    # === Read userUP ===
    const-string v6, "cookies/userUP.txt"
    invoke-static {v13, v6}, Lcom/hotstar/patch/CookieFileReader;->readAsset(Landroid/content/Context;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7

    if-eqz v7, :skip_user_up
    invoke-virtual {v7}, Ljava/lang/String;->length()I
    move-result v8
    if-lez v8, :skip_user_up

    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedUserUP:Ljava/lang/String;

    invoke-interface {v4}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v8
    const-string v9, "cached_user_up"
    invoke-interface {v8, v9, v7}, Landroid/content/SharedPreferences$Editor;->putString(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;
    invoke-interface {v8}, Landroid/content/SharedPreferences$Editor;->apply()V
    :skip_user_up

    # === Read HID ===
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
    :skip_hid

    # === Read PID ===
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
    :skip_pid

    # === Read deviceId ===
    const-string v6, "cookies/deviceId.txt"
    invoke-static {v13, v6}, Lcom/hotstar/patch/CookieFileReader;->readAsset(Landroid/content/Context;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v7

    if-eqz v7, :skip_did
    invoke-virtual {v7}, Ljava/lang/String;->length()I
    move-result v8
    if-lez v8, :skip_did

    sput-object v7, Lcom/hotstar/patch/CookieSeeder;->injectedDeviceId:Ljava/lang/String;

    invoke-interface {v4}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v8
    const-string v9, "cached_device_id"
    invoke-interface {v8, v9, v7}, Landroid/content/SharedPreferences$Editor;->putString(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;
    invoke-interface {v8}, Landroid/content/SharedPreferences$Editor;->apply()V
    :skip_did

    # === Write device_id to StarApp SharedPreferences ===
    invoke-static {v13, v4}, Lcom/hotstar/patch/CookieSeeder;->seedStarAppPrefs(Landroid/content/Context;Landroid/content/SharedPreferences;)V

    # Mark as seeded
    invoke-interface {v4}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v6
    const/4 v7, 0x1
    const-string v8, "is_seeded"
    invoke-interface {v6, v8, v7}, Landroid/content/SharedPreferences$Editor;->putBoolean(Ljava/lang/String;Z)Landroid/content/SharedPreferences$Editor;
    invoke-interface {v6}, Landroid/content/SharedPreferences$Editor;->apply()V

    const-string v2, "Auth token seeding complete"
    invoke-static {v0, v2}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    return-void
.end method

# Write deviceId into StarApp prefs (used by the app's native device registration)
.method private static seedStarAppPrefs(Landroid/content/Context;Landroid/content/SharedPreferences;)V
    .registers 6
    sget-object v0, Lcom/hotstar/patch/CookieSeeder;->injectedDeviceId:Ljava/lang/String;
    if-eqz v0, :end
    invoke-virtual {v0}, Ljava/lang/String;->length()I
    move-result v1
    if-lez v1, :end

    const-string v1, "StarApp"
    const/4 v2, 0x0
    invoke-virtual {p0, v1, v2}, Landroid/content/Context;->getSharedPreferences(Ljava/lang/String;I)Landroid/content/SharedPreferences;
    move-result-object v1

    invoke-interface {v1}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v2
    const-string v3, "guid"
    invoke-interface {v2, v3, v0}, Landroid/content/SharedPreferences$Editor;->putString(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;
    invoke-interface {v2}, Landroid/content/SharedPreferences$Editor;->apply()V

    const-string v2, "HotstarPatch"
    const-string v3, "Seeded device_id into StarApp prefs"
    invoke-static {v2, v3}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    :end
    return-void
.end method
