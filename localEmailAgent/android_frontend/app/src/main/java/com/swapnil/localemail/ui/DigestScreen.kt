package com.swapnil.localemail.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.swapnil.localemail.data.EmailItem
import com.swapnil.localemail.data.shortDate

@Composable
fun DigestScreen(vm: AppViewModel) {
    val digest by vm.digest.collectAsStateWithLifecycle()
    val result = digest

    if (result == null || result.items.isEmpty()) {
        Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
            Text(
                "No digest yet.\nTap Summarize on the Home tab.",
                textAlign = TextAlign.Center,
                style = MaterialTheme.typography.bodyLarge,
            )
        }
        return
    }

    val high = result.items.filter { it.isHigh }
    val rest = result.items.filterNot { it.isHigh }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item(key = "summary") {
            Column {
                Text(
                    "${result.emailCount} emails · ${result.elapsedSeconds}s",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (result.truncated) {
                    Text(
                        "More emails matched than the server's limit, so older ones were skipped.",
                        style = MaterialTheme.typography.bodySmall,
                        color = StatusColors.processing(),
                    )
                }
            }
        }
        if (high.isNotEmpty()) {
            item(key = "header-high") { SectionHeader("Needs attention (${high.size})") }
            items(high, key = { it.id }) { EmailCard(it) }
        }
        if (rest.isNotEmpty()) {
            item(key = "header-rest") { SectionHeader("Everything else (${rest.size})") }
            items(rest, key = { it.id }) { EmailCard(it) }
        }
    }
}

@Composable
private fun SectionHeader(text: String) {
    Text(text, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
}

@Composable
private fun EmailCard(item: EmailItem) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                item.subject,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                listOf(item.sender, shortDate(item.date)).filter { it.isNotBlank() }.joinToString(" · "),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                item.summary,
                style = MaterialTheme.typography.bodyMedium,
                color = if (item.summarized) MaterialTheme.colorScheme.onSurface
                else MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (item.deadline != null || item.needsAction) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    item.deadline?.let { Tag("Deadline: $it", StatusColors.processing()) }
                    if (item.needsAction) Tag("Action needed", StatusColors.failure())
                }
            }
        }
    }
}

@Composable
private fun Tag(text: String, color: Color) {
    Surface(shape = RoundedCornerShape(8.dp), color = color.copy(alpha = 0.15f)) {
        Text(
            text,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            style = MaterialTheme.typography.labelMedium,
            color = color,
        )
    }
}
