package com.swapnil.localemail.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.swapnil.localemail.data.ApiClient
import com.swapnil.localemail.data.ApiException
import com.swapnil.localemail.data.AppSettings
import com.swapnil.localemail.data.RunState
import com.swapnil.localemail.data.SettingsStore
import com.swapnil.localemail.data.toRunState
import com.swapnil.localemail.data.validateServerUrl
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/** How far back each Summarize looks. The server caps the number of emails it fetches. */
const val SUMMARY_HOURS = 12

private const val POLL_INTERVAL_MS = 2_000L
private const val MAX_POLL_FAILURES = 5 // in a row, before giving up
private const val MAX_WAIT_MS = 30 * 60 * 1000L

sealed interface Connection {
    data object NotConfigured : Connection
    data object Checking : Connection
    data object Connected : Connection
    data class Problem(val message: String) : Connection
}

class AppViewModel(app: Application) : AndroidViewModel(app) {
    private val store = SettingsStore(app)
    private val api = ApiClient()

    val settings: StateFlow<AppSettings> =
        store.settings.stateIn(viewModelScope, SharingStarted.Eagerly, AppSettings())
    val digest = store.lastDigest.stateIn(viewModelScope, SharingStarted.Eagerly, null)

    private val _connection = MutableStateFlow<Connection>(Connection.Checking)
    val connection: StateFlow<Connection> = _connection.asStateFlow()

    private val _run = MutableStateFlow<RunState>(RunState.Idle)
    val run: StateFlow<RunState> = _run.asStateFlow()

    private var summarizeJob: Job? = null

    /** Asks the server's /health whether Ollama and Gmail are ready. */
    fun checkConnection() {
        viewModelScope.launch {
            val s = store.settings.first()
            if (!s.isConfigured) {
                _connection.value = Connection.NotConfigured
                return@launch
            }
            _connection.value = Connection.Checking
            _connection.value = try {
                val health = api.health(s.serverUrl)
                when {
                    health.ok -> Connection.Connected
                    !health.ollama.reachable -> Connection.Problem("Laptop reached, but Ollama is not running.")
                    !health.ollama.modelInstalled -> Connection.Problem("Ollama is missing the model. ${health.ollama.detail}")
                    !health.gmail.signedIn -> Connection.Problem("Laptop reached, but Gmail is not signed in.")
                    else -> Connection.Problem("The server says it is not ready.")
                }
            } catch (e: ApiException) {
                Connection.Problem(e.message ?: "Can't reach the laptop.")
            }
        }
    }

    /** Starts a summary job on the server and follows it until it finishes. */
    fun summarize() {
        if (summarizeJob?.isActive == true) return
        summarizeJob = viewModelScope.launch {
            _run.value = RunState.Processing("Starting…")
            try {
                val s = store.settings.first()
                val jobId = api.startSummary(s.serverUrl, s.token, SUMMARY_HOURS)
                _run.value = poll(s, jobId)
            } catch (e: ApiException) {
                _run.value = RunState.Failed(e.message ?: "Something went wrong.")
            }
        }
    }

    private suspend fun poll(s: AppSettings, jobId: String): RunState {
        val giveUpAt = System.currentTimeMillis() + MAX_WAIT_MS
        var failures = 0
        while (System.currentTimeMillis() < giveUpAt) {
            delay(POLL_INTERVAL_MS)
            val job = try {
                api.getJob(s.serverUrl, s.token, jobId).also { failures = 0 }
            } catch (e: ApiException) {
                if (!e.retryable || ++failures >= MAX_POLL_FAILURES) {
                    return RunState.Failed(e.message ?: "Lost contact with the laptop.")
                }
                continue
            }
            val state = job.toRunState()
            if (state is RunState.Done) job.result?.let { store.saveDigest(it) }
            if (state !is RunState.Processing) return state
            _run.value = state
        }
        return RunState.Failed("Timed out waiting for the summary.")
    }

    /** Returns an error message to show, or null when saved. */
    fun saveSettings(new: AppSettings, onResult: (String?) -> Unit) {
        val error = validateServerUrl(new.serverUrl)
        if (error != null) {
            onResult(error)
            return
        }
        viewModelScope.launch {
            store.saveSettings(new)
            onResult(null)
            checkConnection()
        }
    }
}
