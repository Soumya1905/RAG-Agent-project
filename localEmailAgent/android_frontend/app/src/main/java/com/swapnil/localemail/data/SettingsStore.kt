package com.swapnil.localemail.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "settings")

/** Saves the settings and the last digest on the phone (so the Digest tab survives a restart). */
class SettingsStore(private val context: Context) {
    private object Keys {
        val userName = stringPreferencesKey("user_name")
        val deviceName = stringPreferencesKey("device_name")
        val serverUrl = stringPreferencesKey("server_url")
        val tokenEncrypted = stringPreferencesKey("token_encrypted")
        val lastDigest = stringPreferencesKey("last_digest_json")
    }

    val settings: Flow<AppSettings> = context.dataStore.data.map { p ->
        AppSettings(
            userName = p[Keys.userName].orEmpty(),
            deviceName = p[Keys.deviceName].orEmpty(),
            serverUrl = p[Keys.serverUrl].orEmpty(),
            token = TokenCipher.decrypt(p[Keys.tokenEncrypted].orEmpty()),
        )
    }

    val lastDigest: Flow<DigestResult?> = context.dataStore.data.map { p ->
        p[Keys.lastDigest]?.let { runCatching { AppJson.decodeFromString<DigestResult>(it) }.getOrNull() }
    }

    suspend fun saveSettings(s: AppSettings) {
        context.dataStore.edit { p ->
            p[Keys.userName] = s.userName.trim()
            p[Keys.deviceName] = s.deviceName.trim()
            p[Keys.serverUrl] = s.serverUrl.trim().trimEnd('/')
            p[Keys.tokenEncrypted] = TokenCipher.encrypt(s.token.trim())
        }
    }

    suspend fun saveDigest(result: DigestResult) {
        context.dataStore.edit { it[Keys.lastDigest] = AppJson.encodeToString(DigestResult.serializer(), result) }
    }
}
