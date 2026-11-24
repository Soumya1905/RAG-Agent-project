"""Prepare emails for the model and pack them into size-limited chunks.

Pipeline per email: clean (regex) -> trim (NLTK) -> format with a numbered header.
Whole emails are packed together, never split, so sender and deadline stay with their text.
"""
from dataclasses import dataclass

from app.config import Settings, settings as default_settings
from app.services.email_cleaner import clean_email_text
from app.services.email_trimmer import trim_text
from app.services.gmail_service import Email


@dataclass
class Chunk:
    first: int  # 1-based number of the first email in this chunk
    blocks: list[str]

    @property
    def text(self) -> str:
        return "\n\n".join(self.blocks)

    @property
    def size(self) -> int:
        return len(self.text)


def format_email(number: int, email: Email, max_chars: int) -> str:
    body = clean_email_text(email.body) or clean_email_text(email.snippet) or "(no text)"
    body = trim_text(body, max_chars)
    return (
        f"--- Email {number} ---\nFrom: {email.sender}\nDate: {email.date}\n"
        f"Subject: {email.subject}\n\n{body}"
    )


def build_chunks(emails: list[Email], config: Settings = default_settings) -> list[Chunk]:
    """Pack emails (in order) into chunks of at most `chunk_max_chars` characters."""
    chunks: list[Chunk] = []
    current: list[str] = []
    current_size = 0
    first = 1
    for number, email in enumerate(emails, 1):
        block = format_email(number, email, config.email_max_chars)
        added = len(block) + 2  # blank line between blocks
        if current and current_size + added > config.chunk_max_chars:
            chunks.append(Chunk(first=first, blocks=current))
            current, current_size, first = [], 0, number
        current.append(block)
        current_size += added
    if current:
        chunks.append(Chunk(first=first, blocks=current))
    return chunks
