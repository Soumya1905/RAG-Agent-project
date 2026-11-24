package com.swapnil.localemail

import com.swapnil.localemail.data.shortDate
import com.swapnil.localemail.data.validateServerUrl
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class HelpersTest {
    @Test
    fun acceptsHttpsTailscaleAddressAndEmpty() {
        assertNull(validateServerUrl("https://soumya-laptop.tail1234.ts.net"))
        assertNull(validateServerUrl("  https://soumya-laptop.tail1234.ts.net/  "))
        assertNull(validateServerUrl(""))
    }

    @Test
    fun rejectsPlainHttpIncompleteAndSpaces() {
        assertNotNull(validateServerUrl("http://100.75.89.110:8000"))
        assertNotNull(validateServerUrl("soumya-laptop"))
        assertNotNull(validateServerUrl("https://"))
        assertNotNull(validateServerUrl("https://my laptop.ts.net"))
    }

    @Test
    fun shortensEmailDates() {
        assertEquals("Mon, 24 Nov 2026", shortDate("Mon, 24 Nov 2026 09:12:00 +0530"))
        assertEquals("4 Nov 2026", shortDate("4 Nov 2026 08:00:00 +0000"))
        assertEquals("Mon", shortDate("Mon"))
        assertEquals("Some odd format", shortDate("Some odd format"))
        assertEquals("Some very odd fo", shortDate("Some very odd format here"))
    }
}
