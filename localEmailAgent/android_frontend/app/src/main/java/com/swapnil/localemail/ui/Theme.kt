package com.swapnil.localemail.ui

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

@Composable
fun EmailAssistantTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    val colors = when {
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            if (dark) dynamicDarkColorScheme(LocalContext.current) else dynamicLightColorScheme(LocalContext.current)
        dark -> darkColorScheme()
        else -> lightColorScheme()
    }
    MaterialTheme(colorScheme = colors, content = content)
}

/** Status colours, fixed so "orange = working, green = done, red = failed" never changes with the theme. */
object StatusColors {
    @Composable
    fun processing() = if (isSystemInDarkTheme()) Color(0xFFFFB74D) else Color(0xFFE65100)

    @Composable
    fun success() = if (isSystemInDarkTheme()) Color(0xFF81C784) else Color(0xFF2E7D32)

    @Composable
    fun failure() = if (isSystemInDarkTheme()) Color(0xFFEF9A9A) else Color(0xFFC62828)
}
