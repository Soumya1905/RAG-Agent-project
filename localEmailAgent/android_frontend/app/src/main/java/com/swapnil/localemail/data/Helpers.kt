package com.swapnil.localemail.data

/** What the Home screen shows under the Summarize button. */
sealed interface RunState {
    data object Idle : RunState
    data class Processing(val detail: String, val step: Int = 0, val total: Int = 0) : RunState
    data class Done(val detail: String) : RunState
    data class Failed(val detail: String) : RunState
}

/** Maps the server's job JSON to what the UI shows. */
fun Job.toRunState(): RunState = when (status) {
    "done" -> RunState.Done(
        result?.let { "${it.emailCount} emails summarized. Open the Digest tab." } ?: "Finished.",
    )
    "error" -> RunState.Failed(error?.message?.ifBlank { null } ?: "Something went wrong on the server.")
    "queued" -> RunState.Processing("Waiting in the queue…")
    "fetching" -> RunState.Processing("Fetching your emails…")
    else -> if (progress.total > 0) {
        RunState.Processing("Summarizing… ${progress.step} of ${progress.total}", progress.step, progress.total)
    } else {
        RunState.Processing("Summarizing…")
    }
}

/** Returns an error message for a bad server address, or null if it is fine (or empty). */
fun validateServerUrl(url: String): String? {
    val text = url.trim()
    return when {
        text.isEmpty() -> null
        !text.startsWith("https://") -> "The address must start with https:// (the one from tailscale serve)."
        text.removePrefix("https://").isBlank() -> "The address is incomplete."
        text.any { it.isWhitespace() } -> "The address must not contain spaces."
        else -> null
    }
}

/** "Mon, 24 Nov 2026 09:12:00 +0530" -> "Mon, 24 Nov 2026". Other formats are left mostly alone. */
fun shortDate(raw: String): String {
    val match = Regex("""^(?:[A-Za-z]{3},\s*)?\d{1,2}\s+[A-Za-z]{3}\s+\d{4}""").find(raw.trim())
    return match?.value ?: raw.trim().take(16)
}
