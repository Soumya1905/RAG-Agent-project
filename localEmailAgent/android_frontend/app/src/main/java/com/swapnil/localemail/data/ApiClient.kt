package com.swapnil.localemail.data

import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * An error whose message is safe to show to the user as-is.
 * [retryable] is true for network trouble, which may pass; false for answers like "wrong token".
 */
class ApiException(message: String, val retryable: Boolean = false) : Exception(message)

class ApiClient(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build(),
) {
    /** GET /health. Open on the server, so no token is sent. */
    suspend fun health(baseUrl: String): Health =
        AppJson.decodeFromString(execute(Request.Builder().url(url(baseUrl, "/health")).build()))

    /** POST /summarize for the last [hours] hours. Returns the job id. */
    suspend fun startSummary(baseUrl: String, token: String, hours: Int): String {
        val body = """{"hours": $hours}""".toRequestBody("application/json".toMediaType())
        val request = authorized(Request.Builder().url(url(baseUrl, "/summarize")).post(body), token)
        return AppJson.decodeFromString<StartResponse>(execute(request)).jobId
    }

    /** GET /summarize/{id}: status, progress and (when done) the digest. */
    suspend fun getJob(baseUrl: String, token: String, jobId: String): Job {
        val request = authorized(Request.Builder().url(url(baseUrl, "/summarize/$jobId")), token)
        return AppJson.decodeFromString(execute(request))
    }

    private fun authorized(builder: Request.Builder, token: String): Request =
        (if (token.isNotBlank()) builder.header("Authorization", "Bearer $token") else builder).build()

    private fun url(baseUrl: String, path: String): String = baseUrl.trim().trimEnd('/') + path

    private suspend fun execute(request: Request): String = withContext(Dispatchers.IO) {
        try {
            client.newCall(request).execute().use { response ->
                val text = response.body.string()
                when {
                    response.isSuccessful -> text
                    response.code == 401 -> throw ApiException("The server rejected the token. Check it in Settings.")
                    response.code == 404 -> throw ApiException("The server doesn't know this job (it may have restarted).")
                    else -> throw ApiException("The server returned an error (${response.code}).")
                }
            }
        } catch (e: ApiException) {
            throw e
        } catch (e: IOException) {
            throw ApiException("Can't reach the laptop. Is Tailscale connected and the laptop awake?", retryable = true)
        } catch (e: IllegalArgumentException) { // bad URL text, or unreadable JSON
            throw ApiException("The server address or the server's reply is not valid.")
        } catch (e: kotlinx.serialization.SerializationException) {
            throw ApiException("The server's reply was not in the expected format.")
        }
    }
}
