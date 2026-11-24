"""Shrink long email bodies to a character budget using NLTK sentence scoring.

Extractive only: whole sentences are kept or dropped, in their original order. Sentences that
look like they carry a date, time, amount or request are always preferred, so deadlines are
unlikely to be trimmed away. Short emails are returned unchanged.
"""
import re
from collections import Counter
from functools import lru_cache

import nltk

from app.config import BASE_DIR

NLTK_DIR = BASE_DIR / "nltk_data"
nltk.data.path.insert(0, str(NLTK_DIR))

# A sentence matching this is treated as important (time-sensitive or asks something).
_PRIORITY = re.compile(
    r"(?i)\b(deadline|due|urgent|asap|important|required|reminder|rsvp|expires?|overdue|"
    r"invoice|payment|meeting|interview|today|tonight|tomorrow|please|action|confirm|reply|"
    r"mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b"
    r"|\b\d{1,2}(:\d{2})?\s?(am|pm)\b|\b\d{1,2}[/.-]\d{1,2}([/.-]\d{2,4})?\b|[$€£₹]\s?\d"
)
_WORD = re.compile(r"[a-zA-Z']{3,}")
_FALLBACK_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


@lru_cache(maxsize=1)
def _stopwords() -> frozenset[str]:
    try:
        from nltk.corpus import stopwords

        return frozenset(stopwords.words("english"))
    except LookupError:
        return frozenset()


def split_sentences(text: str) -> list[str]:
    try:
        sentences = nltk.sent_tokenize(text)
    except LookupError:  # NLTK data missing: degrade to a simple regex splitter
        sentences = _FALLBACK_SPLIT.split(text)
    return [s.strip() for s in sentences if s.strip()]


def trim_text(text: str, max_chars: int) -> str:
    """Return `text` unchanged if it fits, else the best sentences that fit in `max_chars`."""
    if len(text) <= max_chars:
        return text

    sentences = split_sentences(text)
    stop = _stopwords()
    freq = Counter(w for s in sentences for w in map(str.lower, _WORD.findall(s)) if w not in stop)

    def score(s: str) -> float:
        words = [w for w in map(str.lower, _WORD.findall(s)) if w not in stop]
        return sum(freq[w] for w in words) / (len(words) or 1) if words else 0.0

    # Rank: opening sentence first, then priority sentences, then by word-frequency score.
    ranked = sorted(
        range(len(sentences)),
        key=lambda i: (i != 0, not _PRIORITY.search(sentences[i]), -score(sentences[i])),
    )
    chosen: set[int] = set()
    used = 0
    for i in ranked:
        cost = len(sentences[i]) + 1
        if used + cost <= max_chars:
            chosen.add(i)
            used += cost

    if not chosen:  # even the first sentence is too long: hard cut
        return text[:max_chars].rstrip() + " ..."
    kept = " ".join(sentences[i] for i in sorted(chosen))
    return kept + " [...]" if len(chosen) < len(sentences) else kept
