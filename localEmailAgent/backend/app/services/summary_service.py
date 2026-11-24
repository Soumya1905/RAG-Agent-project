"""Summarize emails with the local Ollama model.

Each chunk of emails is sent in one call and the model returns one structured entry per email
(summary, needs_action, deadline). Sender, subject and date are taken from the email itself.
The entries are joined back to their emails, sorted by priority in plain Python, and rendered
as a text digest. There is no final "combine" model call.
"""
import logging
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import parseaddr

from app.config import Settings, settings as default_settings
from app.schemas import ChunkSummaries, EmailItem, ModelEmailSummary
from app.services.chunker import Chunk, build_chunks
from app.services.gmail_service import Email
from app.services.ollama_service import OllamaInvalidOutputError, OllamaService

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an email assistant. Read emails accurately and concisely. "
    "Only use information present in the emails; never invent details or deadlines."
)

CHUNK_PROMPT = """Below are {n} numbered emails. Return one entry for EACH email, none skipped:
- email_number: the number in its '--- Email N ---' header
- summary: one sentence saying what the email says
- needs_action: true only if the recipient must reply or do something
- deadline: the deadline or date/time the email states, or an empty string if it states none

{emails}"""

# Called as on_progress(step, total_steps, description); step 0 announces the total up front.
ProgressCallback = Callable[[int, int, str], None]

_NO_DEADLINE = {"", "none", "n/a", "no deadline", "null"}


@dataclass
class DigestResult:
    items: list[EmailItem]
    text: str
    email_count: int
    chunk_count: int
    model_calls: int


class SummaryService:
    def __init__(self, ollama: OllamaService | None = None, config: Settings = default_settings):
        self.ollama = ollama or OllamaService()
        self.config = config

    def digest(
        self, emails: list[Email], on_progress: ProgressCallback | None = None
    ) -> DigestResult:
        if not emails:
            return DigestResult([], "No emails to summarize.", 0, 0, 0)
        report = on_progress or (lambda *_: None)
        chunks = build_chunks(emails, self.config)
        report(0, len(chunks), "starting")

        by_number: dict[int, ModelEmailSummary] = {}
        calls = 0
        for step, chunk in enumerate(chunks, 1):
            results, used = self._summarize_chunk(chunk)
            calls += used
            by_number.update(results)
            report(step, len(chunks), f"chunk {step}/{len(chunks)}")

        items = sort_by_priority(
            [make_item(email, by_number.get(n)) for n, email in enumerate(emails, 1)]
        )
        return DigestResult(items, render_text(items), len(emails), len(chunks), calls)

    def _summarize_chunk(self, chunk: Chunk) -> tuple[dict[int, ModelEmailSummary], int]:
        """Returns ({email_number: result}, model calls used). One retry on invalid output."""
        numbers = range(chunk.first, chunk.first + len(chunk.blocks))
        prompt = CHUNK_PROMPT.format(n=len(chunk.blocks), emails=chunk.text)
        for attempt in (1, 2):
            try:
                parsed = self.ollama.generate_structured(prompt, ChunkSummaries, SYSTEM_PROMPT)
            except OllamaInvalidOutputError:
                log.warning("Invalid structured output for chunk at email %d (attempt %d)",
                            chunk.first, attempt)
                continue
            # Keep only numbers that belong to this chunk; first answer per number wins.
            results: dict[int, ModelEmailSummary] = {}
            for entry in parsed.emails:
                if entry.email_number in numbers and entry.email_number not in results:
                    results[entry.email_number] = entry
            return results, attempt
        return {}, 2


def _display_sender(raw: str) -> str:
    name, address = parseaddr(raw)
    return name or address or raw or "(unknown sender)"


def make_item(email: Email, result: ModelEmailSummary | None) -> EmailItem:
    deadline = None
    if result and result.deadline.strip().lower() not in _NO_DEADLINE:
        deadline = result.deadline.strip()
    needs_action = bool(result and result.needs_action)
    return EmailItem(
        id=email.id,
        sender=_display_sender(email.sender),
        subject=email.subject,
        date=email.date,
        summary=result.summary.strip() if result and result.summary.strip() else "Summary unavailable.",
        needs_action=needs_action,
        deadline=deadline,
        priority="high" if needs_action or deadline else "normal",
        summarized=result is not None,
    )


def sort_by_priority(items: list[EmailItem]) -> list[EmailItem]:
    """Deadline first, then needs-action, then the rest; original (newest-first) order within."""
    return sorted(items, key=lambda i: (i.deadline is None, not i.needs_action))


def render_text(items: list[EmailItem]) -> str:
    def line(i: EmailItem) -> str:
        extra = f" (deadline: {i.deadline})" if i.deadline else ""
        return f"- {i.sender}: {i.subject} - {i.summary}{extra}"

    high = [line(i) for i in items if i.priority == "high"]
    rest = [line(i) for i in items if i.priority != "high"]
    parts = []
    if high:
        parts.append("Needs attention:\n" + "\n".join(high))
    if rest:
        parts.append("FYI:\n" + "\n".join(rest))
    return "\n\n".join(parts)
