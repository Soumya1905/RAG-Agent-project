package com.swapnil.localemail

import com.swapnil.localemail.data.AppJson
import com.swapnil.localemail.data.Health
import com.swapnil.localemail.data.Job
import com.swapnil.localemail.data.RunState
import com.swapnil.localemail.data.toRunState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Parses JSON in the exact shape the backend sends (see backend/app/jobs.py and schemas.py). */
class ContractTest {
    private val doneJson = """
        {"id":"ab12","status":"done","progress":{"step":1,"total":1,"stage":"chunk 1/1"},
         "created_at":"2026-11-24T10:00:00+00:00","finished_at":"2026-11-24T10:01:00+00:00",
         "error":null,
         "result":{"items":[
            {"id":"1","sender":"Prof. Rao","subject":"Project report","date":"Mon, 24 Nov 2026 09:12:00 +0530",
             "summary":"Submit the report.","needs_action":true,"deadline":"Friday 5pm","priority":"high","summarized":true},
            {"id":"2","sender":"Amit","subject":"Lunch pics","date":"Mon","summary":"Photos.",
             "needs_action":false,"deadline":null,"priority":"normal","summarized":true}],
          "digest":"Needs attention: ...","email_count":2,"chunk_count":1,"model_calls":1,
          "truncated":true,"elapsed_seconds":56}}
    """.trimIndent()

    @Test
    fun parsesDoneJobWithItems() {
        val job = AppJson.decodeFromString<Job>(doneJson)
        val items = job.result!!.items
        assertEquals(2, items.size)
        assertEquals("Friday 5pm", items[0].deadline)
        assertTrue(items[0].isHigh && items[0].needsAction)
        assertNull(items[1].deadline)
        assertFalse(items[1].isHigh)
        assertTrue(job.result.truncated)
        assertEquals(56, job.result.elapsedSeconds)
    }

    @Test
    fun ignoresUnknownFieldsFromNewerServer() {
        val job = AppJson.decodeFromString<Job>("""{"id":"x","status":"queued","brand_new_field":123}""")
        assertEquals("queued", job.status)
    }

    @Test
    fun parsesHealth() {
        val h = AppJson.decodeFromString<Health>(
            """{"ok":true,"ollama":{"model":"m","reachable":true,"model_installed":true,"detail":""},
               "gmail":{"credentials_file":true,"signed_in":true}}""",
        )
        assertTrue(h.ok && h.ollama.modelInstalled && h.gmail.signedIn)
    }

    @Test
    fun mapsJobStatusesToRunStates() {
        assertEquals(RunState.Processing("Waiting in the queue…"), Job("1", "queued").toRunState())
        assertEquals(RunState.Processing("Fetching your emails…"), Job("1", "fetching").toRunState())
        val summarizing = AppJson.decodeFromString<Job>(
            """{"id":"1","status":"summarizing","progress":{"step":2,"total":5,"stage":"chunk 2/5"}}""",
        ).toRunState()
        assertEquals(RunState.Processing("Summarizing… 2 of 5", 2, 5), summarizing)
        assertTrue(AppJson.decodeFromString<Job>(doneJson).toRunState() is RunState.Done)
        val failed = AppJson.decodeFromString<Job>(
            """{"id":"1","status":"error","error":{"kind":"ollama","message":"Ollama is down"}}""",
        ).toRunState()
        assertEquals(RunState.Failed("Ollama is down"), failed)
    }
}
