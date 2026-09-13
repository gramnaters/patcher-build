.class public Lcom/hotstar/patch/CookieFileReader;
.super Ljava/lang/Object;

# Reads text files from APK assets directory.
# Also provides base64URL decode helper for JWT parsing.

.method public constructor <init>()V
    .registers 1
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method public static readAsset(Landroid/content/Context;Ljava/lang/String;)Ljava/lang/String;
    .registers 7
    .param p0, "context"    # Landroid/content/Context;
    .param p1, "filename"   # Ljava/lang/String;

    move-object v5, p0
    move-object v6, p1

    const/4 v0, 0x0

    :try_start_0
    invoke-virtual {v5}, Landroid/content/Context;->getAssets()Landroid/content/res/AssetManager;
    move-result-object v1

    invoke-virtual {v1, v6}, Landroid/content/res/AssetManager;->open(Ljava/lang/String;)Ljava/io/InputStream;
    move-result-object v1

    new-instance v2, Ljava/io/BufferedReader;
    new-instance v3, Ljava/io/InputStreamReader;
    invoke-direct {v3, v1}, Ljava/io/InputStreamReader;-><init>(Ljava/io/InputStream;)V
    invoke-direct {v2, v3}, Ljava/io/BufferedReader;-><init>(Ljava/io/Reader;)V

    new-instance v1, Ljava/lang/StringBuilder;
    invoke-direct {v1}, Ljava/lang/StringBuilder;-><init>()V

    :goto_0
    invoke-virtual {v2}, Ljava/io/BufferedReader;->readLine()Ljava/lang/String;
    move-result-object v3

    if-eqz v3, :cond_0

    invoke-virtual {v1, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    goto :goto_0

    :cond_0
    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v0

    invoke-virtual {v2}, Ljava/io/BufferedReader;->close()V
    :try_end_0
    .catch Ljava/lang/Exception; {:try_start_0 .. :try_end_0} :catch_0

    return-object v0

    :catch_0
    move-exception v1

    const-string v2, "HotstarPatch"
    const-string v3, "Failed to read asset"
    invoke-static {v2, v3}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;)I

    return-object v0
.end method

# Base64URL decode: replaces - with + and _ with /, then uses standard Base64
.method public static base64UrlDecode(Ljava/lang/String;)[B
    .registers 5
    :try_start
    invoke-virtual {p0}, Ljava/lang/String;->length()I
    move-result v0

    # Add padding
    rem-int/lit8 v1, v0, 0x4
    rsub-int/lit8 v1, v1, 0x4
    rem-int/lit8 v1, v1, 0x4

    new-instance v2, Ljava/lang/StringBuilder;
    invoke-direct {v2, p0}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    const/4 v3, 0x0
    :pad_loop
    if-lt v3, v1, :done_pad
    const/16 v4, 0x3d
    invoke-virtual {v2, v4}, Ljava/lang/StringBuilder;->append(C)Ljava/lang/StringBuilder;
    add-int/lit8 v3, v3, 0x1
    goto :pad_loop

    :done_pad
    invoke-virtual {v2}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v0

    # Replace URL-safe chars with standard Base64
    const-string v1, "-"
    const-string v2, "+"
    invoke-virtual {v0, v1, v2}, Ljava/lang/String;->replace(Ljava/lang/CharSequence;Ljava/lang/CharSequence;)Ljava/lang/String;
    move-result-object v0

    const-string v1, "_"
    const-string v2, "/"
    invoke-virtual {v0, v1, v2}, Ljava/lang/String;->replace(Ljava/lang/CharSequence;Ljava/lang/CharSequence;)Ljava/lang/String;
    move-result-object v0

    invoke-static {v0}, Landroid/util/Base64;->decode(Ljava/lang/String;)[B
    move-result-object v0
    return-object v0
    :try_end
    .catch Ljava/lang/Exception; {:try_start .. :try_end} :catch_all

    :catch_all
    const/4 v0, 0x0
    return-object v0
.end method
