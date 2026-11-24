import re
from dataclasses import replace

from app.config import settings
from app.services.chunker import build_chunks
from app.services.email_trimmer import trim_text
from app.services.gmail_service import Email
from app.schemas import ChunkSummaries, ModelEmailSummary
from app.services.ollama_service import OllamaInvalidOutputError
from app.services.summary_service import SummaryService, make_item, sort_by_priority


def make_email(i: int, body: str = "Short body.") -> Email:
    return Email(str(i), "t", f"Subject {i}", f"s{i}@x.com", "Mon", "snippet", body)


class FakeOllama:
    """Answers every chunk with a valid entry per email number found in the prompt."""

    def __init__(self, actions=(), deadlines=None, fail_first=0):
        self.prompts = []
        self.actions = set(actions)  # email numbers that need action
        self.deadlines = deadlines or {}  # email number -> deadline text
        self.fail_first = fail_first

    def generate_structured(self, prompt, schema, system=None):
        self.prompts.append(prompt)
        if len(self.prompts) <= self.fail_first:
            raise OllamaInvalidOutputError("bad json")
        numbers = [int(n) for n in re.findall(r"--- Email (\d+) ---", prompt)]
        return ChunkSummaries(emails=[
            ModelEmailSummary(
                email_number=n, summary=f"summary {n}", needs_action=n in self.actions,
                deadline=self.deadlines.get(n, ""),
            )
            for n in numbers
        ])


# --- trimmer -----------------------------------------------------------------

def test_trim_leaves_short_text_unchanged():
    assert trim_text("Hello there.", 100) == "Hello there."


def test_trim_respects_budget_and_keeps_deadline_sentence():
    filler = " ".join(f"Filler sentence number {i} about nothing in particular." for i in range(60))
    text = "Hi team. " + filler + " The report is due Friday 5pm. " + filler
    out = trim_text(text, 500)
    assert len(out) <= 500 + len(" [...]")
    assert "due Friday 5pm" in out
    assert out.startswith("Hi team.")


def test_trim_hard_cuts_single_huge_sentence():
    out = trim_text("word " * 1000, 100)
    assert len(out) <= 104


# --- chunker -----------------------------------------------------------------

def test_chunker_packs_whole_emails_within_limit():
    cfg = replace(settings, chunk_max_chars=600, email_max_chars=200)
    emails = [make_email(i, "x" * 150) for i in range(1, 9)]
    chunks = build_chunks(emails, cfg)
    assert len(chunks) > 1
    assert all(c.size <= 600 for c in chunks)
    assert sum(len(c.blocks) for c in chunks) == 8  # nothing dropped or duplicated
    assert chunks[1].first == chunks[0].first + len(chunks[0].blocks)


def test_chunker_numbers_emails_globally():
    cfg = replace(settings, chunk_max_chars=400, email_max_chars=150)
    chunks = build_chunks([make_email(i, "y" * 120) for i in range(1, 6)], cfg)
    assert "--- Email 5 ---" in chunks[-1].text


# --- summarizer --------------------------------------------------------------

SMALL = replace(settings, chunk_max_chars=400, email_max_chars=150)


def six_emails():
    return [make_email(i, "z" * 120) for i in range(1, 7)]


def test_one_call_per_chunk_and_no_combine_call():
    fake = FakeOllama()
    result = SummaryService(fake, SMALL).digest(six_emails())
    assert result.chunk_count > 1
    assert result.model_calls == result.chunk_count == len(fake.prompts)
    assert len(result.items) == 6


def test_sender_subject_come_from_email_not_model():
    result = SummaryService(FakeOllama()).digest([make_email(1)])
    item = result.items[0]
    assert (item.sender, item.subject) == ("s1@x.com", "Subject 1")
    assert item.summary == "summary 1" and item.summarized


def test_sorted_deadline_then_action_then_rest():
    fake = FakeOllama(actions={2, 5}, deadlines={4: "Friday 5pm"})
    items = SummaryService(fake, SMALL).digest(six_emails()).items
    assert [i.subject for i in items] == [
        "Subject 4", "Subject 2", "Subject 5", "Subject 1", "Subject 3", "Subject 6"]
    assert [i.priority for i in items] == ["high"] * 3 + ["normal"] * 3
    assert items[0].deadline == "Friday 5pm"


def test_progress_announces_total_first_then_each_chunk():
    steps = []
    SummaryService(FakeOllama(), SMALL).digest(six_emails(), on_progress=lambda *a: steps.append(a))
    total = steps[0][1]
    assert steps[0][0] == 0 and total > 1
    assert [s[0] for s in steps] == list(range(total + 1))


def test_retries_once_on_invalid_output():
    fake = FakeOllama(fail_first=1)
    result = SummaryService(fake).digest([make_email(1)])
    assert result.model_calls == 2 and result.items[0].summarized


def test_gives_fallback_item_when_model_keeps_failing():
    fake = FakeOllama(fail_first=99)
    item = SummaryService(fake).digest([make_email(1)]).items[0]
    assert item.summary == "Summary unavailable." and not item.summarized
    assert (item.subject, item.priority) == ("Subject 1", "normal")


def test_missing_and_foreign_numbers_are_handled():
    class Partial(FakeOllama):
        def generate_structured(self, prompt, schema, system=None):
            return ChunkSummaries(emails=[
                ModelEmailSummary(email_number=2, summary="two", needs_action=False, deadline=""),
                ModelEmailSummary(email_number=99, summary="ghost", needs_action=True, deadline="x"),
            ])

    items = SummaryService(Partial()).digest([make_email(1), make_email(2)]).items
    by_subject = {i.subject: i for i in items}
    assert by_subject["Subject 2"].summary == "two"
    assert not by_subject["Subject 1"].summarized
    assert all(i.summary != "ghost" for i in items)


def test_sender_display_name_and_none_deadline_words():
    e = Email("1", "t", "Hi", "Jane Doe <jane@x.com>", "Mon", "s", "b")
    item = make_item(e, ModelEmailSummary(email_number=1, summary="s", needs_action=False, deadline="None"))
    assert item.sender == "Jane Doe" and item.deadline is None


def test_digest_text_has_sections():
    fake = FakeOllama(actions={1})
    text = SummaryService(fake).digest([make_email(1), make_email(2)]).text
    assert text.startswith("Needs attention:") and "FYI:" in text


def test_no_emails():
    result = SummaryService(FakeOllama()).digest([])
    assert result.model_calls == 0 and result.items == []
