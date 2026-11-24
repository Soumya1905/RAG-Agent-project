package com.swapnil.localemail.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.swapnil.localemail.R
import com.swapnil.localemail.data.RunState

@Composable
fun HomeScreen(vm: AppViewModel, onOpenDigest: () -> Unit, onOpenSettings: () -> Unit) {
    val settings by vm.settings.collectAsStateWithLifecycle()
    val connection by vm.connection.collectAsStateWithLifecycle()
    val run by vm.run.collectAsStateWithLifecycle()

    // Re-check the laptop every time the screen comes back (e.g. after switching apps).
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { vm.checkConnection() }

    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        ConnectionBadge(connection, settings.deviceName, onClick = vm::checkConnection)
        Spacer(Modifier.height(32.dp))

        Text(
            stringResource(R.string.app_name),
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
        )
        if (settings.userName.isNotBlank()) {
            Text("Hi, ${settings.userName}", style = MaterialTheme.typography.bodyLarge)
        }
        Spacer(Modifier.height(40.dp))

        Button(
            onClick = vm::summarize,
            enabled = settings.isConfigured && run !is RunState.Processing,
            modifier = Modifier.fillMaxWidth(0.7f).height(56.dp),
        ) {
            Text("Summarize", style = MaterialTheme.typography.titleMedium)
        }
        Spacer(Modifier.height(20.dp))

        if (!settings.isConfigured) {
            TextButton(onClick = onOpenSettings) { Text("Set up the laptop address in Settings") }
        } else {
            RunStatus(run, onOpenDigest)
        }
    }
}

@Composable
private fun ConnectionBadge(connection: Connection, deviceName: String, onClick: () -> Unit) {
    val green = StatusColors.success()
    val red = StatusColors.failure()
    val grey = MaterialTheme.colorScheme.onSurfaceVariant
    Row(
        modifier = Modifier.clickable(onClick = onClick).padding(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        when (connection) {
            Connection.Checking -> CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp)
            Connection.Connected -> Icon(Icons.Filled.CheckCircle, "Connected", tint = green)
            is Connection.Problem -> Icon(Icons.Filled.Warning, "Problem", tint = red)
            Connection.NotConfigured -> Icon(Icons.Filled.Settings, "Not set up", tint = grey)
        }
        Spacer(Modifier.width(8.dp))
        Text(
            text = when (connection) {
                Connection.Checking -> "Checking…"
                Connection.Connected -> if (deviceName.isNotBlank()) "Connected to $deviceName" else "Connected"
                is Connection.Problem -> connection.message
                Connection.NotConfigured -> "Not set up yet"
            },
            style = MaterialTheme.typography.bodyMedium,
            color = when (connection) {
                Connection.Connected -> green
                is Connection.Problem -> red
                else -> grey
            },
        )
    }
}

/** Orange while working (with a progress bar), green when done, red when failed. */
@Composable
private fun RunStatus(run: RunState, onOpenDigest: () -> Unit) {
    when (run) {
        RunState.Idle -> Unit
        is RunState.Processing -> {
            val orange = StatusColors.processing()
            StatusText("In process · ${run.detail}", orange)
            Spacer(Modifier.height(12.dp))
            val modifier = Modifier.fillMaxWidth(0.7f)
            if (run.total > 0) {
                LinearProgressIndicator(
                    progress = { run.step.toFloat() / run.total },
                    modifier = modifier,
                    color = orange,
                )
            } else {
                LinearProgressIndicator(modifier = modifier, color = orange)
            }
        }
        is RunState.Done -> {
            StatusText("Done · ${run.detail}", StatusColors.success())
            TextButton(onClick = onOpenDigest) { Text("View digest") }
        }
        is RunState.Failed -> StatusText("Failed · ${run.detail}", StatusColors.failure())
    }
}

@Composable
private fun StatusText(text: String, color: Color) {
    Text(
        text,
        color = color,
        style = MaterialTheme.typography.bodyLarge,
        fontWeight = FontWeight.Medium,
        textAlign = TextAlign.Center,
    )
}
