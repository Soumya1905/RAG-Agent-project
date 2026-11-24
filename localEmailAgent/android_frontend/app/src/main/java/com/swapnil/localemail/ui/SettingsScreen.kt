package com.swapnil.localemail.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.swapnil.localemail.data.AppSettings

@Composable
fun SettingsScreen(vm: AppViewModel) {
    val saved by vm.settings.collectAsStateWithLifecycle()
    // Editable copy; restarts from the saved values whenever they change.
    var form by remember(saved) { mutableStateOf(saved) }
    var showToken by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<Pair<String, Boolean>?>(null) } // text, isError

    Column(
        modifier = Modifier.verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Settings", style = MaterialTheme.typography.headlineSmall)

        Field("Your name", form.userName) { form = form.copy(userName = it) }
        Field("Tailscale device name", form.deviceName, hint = "Just a label, e.g. soumya-laptop") {
            form = form.copy(deviceName = it)
        }
        Field(
            "Server address", form.serverUrl,
            hint = "The https:// address printed by 'tailscale serve'",
            keyboardType = KeyboardType.Uri,
        ) { form = form.copy(serverUrl = it) }

        OutlinedTextField(
            value = form.token,
            onValueChange = { form = form.copy(token = it) },
            label = { Text("Token") },
            supportingText = { Text("Must match API_TOKEN in the backend's .env file") },
            singleLine = true,
            visualTransformation = if (showToken) VisualTransformation.None else PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            trailingIcon = { TextButton({ showToken = !showToken }) { Text(if (showToken) "Hide" else "Show") } },
            modifier = Modifier.fillMaxWidth(),
        )

        Button(
            onClick = {
                vm.saveSettings(form) { error ->
                    message = if (error == null) "Saved." to false else error to true
                }
            },
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Save") }

        message?.let { (text, isError) ->
            Text(text, color = if (isError) StatusColors.failure() else StatusColors.success())
        }
    }
}

@Composable
private fun Field(
    label: String,
    value: String,
    hint: String? = null,
    keyboardType: KeyboardType = KeyboardType.Text,
    onChange: (String) -> Unit,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        label = { Text(label) },
        supportingText = hint?.let { { Text(it) } },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = keyboardType),
        modifier = Modifier.fillMaxWidth(),
    )
}
