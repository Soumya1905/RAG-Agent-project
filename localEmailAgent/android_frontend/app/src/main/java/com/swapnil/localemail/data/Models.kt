package com.swapnil.localemail.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/** Mirrors the backend's JSON. Field names match backend/app/schemas.py and app/jobs.py. */

@Serializable
data class Health(
    val ok: Boolean = false,
    val ollama: OllamaHealth = OllamaHealth(),
    val gmail: GmailHealth = GmailHealth(),
)

@Serializable
data class OllamaHealth(
    val model: String = "",
    val reachable: Boolean = false,
    @SerialName("model_installed") val modelInstalled: Boolean = false,
    val detail: String = "",
)

@Serializable
data class GmailHealth(
    @SerialName("credentials_file") val credentialsFile: Boolean = false,
    @SerialName("signed_in") val signedIn: Boolean = false,
)

@Serializable
data class StartResponse(
    @SerialName("job_id") val jobId: String,
    val status: String = "",
)

@Serializable
data class Progress(
    val step: Int = 0,
    val total: Int = 0,
    val stage: String = "",
)

/** One email in the digest. Sender, subject and date come from Gmail; the rest from the model. */
@Serializable
data class EmailItem(
    val id: String,
    val sender: String,
    val subject: String,
    val date: String = "",
    val summary: String,
    @SerialName("needs_action") val needsAction: Boolean = false,
    val deadline: String? = null,
    val priority: String = "normal", // "high" or "normal"
    val summarized: Boolean = true,
) {
    val isHigh: Boolean get() = priority == "high"
}

@Serializable
data class DigestResult(
    val items: List<EmailItem> = emptyList(),
    val digest: String = "",
    @SerialName("email_count") val emailCount: Int = 0,
    @SerialName("chunk_count") val chunkCount: Int = 0,
    @SerialName("model_calls") val modelCalls: Int = 0,
    val truncated: Boolean = false,
    @SerialName("elapsed_seconds") val elapsedSeconds: Int = 0,
)

@Serializable
data class JobError(
    val kind: String = "",
    val message: String = "",
)

@Serializable
data class Job(
    val id: String,
    val status: String, // queued | fetching | summarizing | done | error
    val progress: Progress = Progress(),
    val result: DigestResult? = null,
    val error: JobError? = null,
)

/** What the user types in Settings. The token is stored encrypted; see SettingsStore. */
data class AppSettings(
    val userName: String = "",
    val deviceName: String = "",
    val serverUrl: String = "",
    val token: String = "",
) {
    val isConfigured: Boolean get() = serverUrl.isNotBlank()
}

val AppJson = Json {
    ignoreUnknownKeys = true // the server may add fields later
    coerceInputValues = true
}
