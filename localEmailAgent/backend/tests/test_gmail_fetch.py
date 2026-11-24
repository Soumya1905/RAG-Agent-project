from dataclasses import replace

from app.config import settings
from app.services.gmail_service import GmailService


class FakeGmail:
    """Mimics service.users().messages().list/get(...).execute()."""

    def __init__(self, total: int):
        self.total = total
        self.queries = []

    def users(self):
        return self

    def messages(self):
        return self

    def list(self, userId, q, maxResults, pageToken=None):
        self.queries.append(q)
        start = int(pageToken or 0)
        end = min(start + maxResults, self.total)
        resp = {"messages": [{"id": str(i)} for i in range(start, end)]}
        if end < self.total:
            resp["nextPageToken"] = str(end)
        return _Exec(resp)

    def get(self, userId, id, format):
        return _Exec({"id": id, "threadId": "t", "snippet": "s", "payload": {"headers": []}})


class _Exec:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


def make_service(total: int, cap: int = 5) -> tuple[GmailService, FakeGmail]:
    svc = GmailService(replace(settings, gmail_window_max_emails=cap))
    fake = FakeGmail(total)
    svc._service = fake
    return svc, fake


def test_under_cap_not_truncated():
    svc, _ = make_service(total=3)
    result = svc.fetch_since(12)
    assert len(result.emails) == 3 and not result.truncated


def test_over_cap_is_truncated_to_cap():
    svc, _ = make_service(total=9)
    result = svc.fetch_since(12)
    assert len(result.emails) == 5 and result.truncated


def test_exactly_cap_not_truncated():
    svc, _ = make_service(total=5)
    assert not svc.fetch_since(12).truncated


def test_query_targets_inbox_and_excludes_noise_by_default():
    svc, fake = make_service(total=1)
    svc.fetch_since(12)
    q = fake.queries[0]
    assert "in:inbox" in q and "after:" in q and "-category:promotions" in q


def test_all_flag_includes_noise():
    svc, fake = make_service(total=1)
    svc.fetch_since(12, exclude_noise=False)
    assert "-category:" not in fake.queries[0]


def test_fetch_latest_caps_and_flags_truncation():
    svc, _ = make_service(total=50, cap=5)
    result = svc.fetch_latest(20)
    assert len(result.emails) == 5 and result.truncated
