import time
from dataclasses import replace

from fastapi.testclient import TestClient

from app.config import settings
from app.jobs import JobManager
from app.main import create_app
from app.services.gmail_service import Email, FetchResult, GmailError
from app.services.ollama_service import OllamaUnavailableError
from app.schemas import EmailItem
from app.services.summary_service import DigestResult


def email(i: int) -> Email:
    return Email(str(i), "t", f"Subject {i}", "a@x.com", "Mon", "s", "body")


class FakeGmail:
    def __init__(self, count=3, truncated=False, error=None):
        self.count, self.truncated, self.error = count, truncated, error
        self.calls = []

    def _result(self):
        if self.error:
            raise self.error
        return FetchResult([email(i) for i in range(self.count)], self.truncated)

    def fetch_since(self, hours=None):
        self.calls.append(("since", hours))
        return self._result()

    def fetch_latest(self, count):
        self.calls.append(("latest", count))
        return self._result()


class FakeSummary:
    def __init__(self, error=None):
        self.error = error

    def digest(self, emails, on_progress=None):
        if self.error:
            raise self.error
        for step in (0, 1, 2):
            on_progress(step, 2, f"step {step}")
        items = [
            EmailItem(e.id, "Sender", e.subject, e.date, "sum", True, "Fri", "high", True)
            for e in emails
        ]
        return DigestResult(items, "the digest", len(emails), 2, 2)


def make_client(gmail=None, summary=None, config=settings):
    gmail = gmail or FakeGmail()
    manager = JobManager(lambda: gmail, lambda: summary or FakeSummary(), max_jobs=3)
    return TestClient(create_app(manager, config)), gmail


def wait_done(client, job_id, headers=None):
    for _ in range(100):
        body = client.get(f"/summarize/{job_id}", headers=headers).json()
        if body["status"] in {"done", "error"}:
            return body
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_summarize_happy_path():
    client, gmail = make_client(FakeGmail(count=3, truncated=True))
    resp = client.post("/summarize", json={"hours": 6})
    assert resp.status_code == 202
    job = wait_done(client, resp.json()["job_id"])
    assert job["status"] == "done"
    assert job["result"]["digest"] == "the digest"
    assert job["result"]["email_count"] == 3
    assert len(job["result"]["items"]) == 3
    assert job["result"]["items"][0] == {
        "id": "0", "sender": "Sender", "subject": "Subject 0", "date": "Mon", "summary": "sum",
        "needs_action": True, "deadline": "Fri", "priority": "high", "summarized": True,
    }
    assert job["result"]["truncated"] is True
    assert job["progress"] == {"step": 2, "total": 2, "stage": "step 2"}
    assert gmail.calls == [("since", 6)]


def test_latest_mode_and_empty_body():
    client, gmail = make_client()
    wait_done(client, client.post("/summarize", json={"latest": 7}).json()["job_id"])
    wait_done(client, client.post("/summarize").json()["job_id"])  # no body = default window
    assert gmail.calls == [("latest", 7), ("since", None)]


def test_rejects_both_modes_and_bad_values():
    client, _ = make_client()
    assert client.post("/summarize", json={"hours": 1, "latest": 5}).status_code == 422
    assert client.post("/summarize", json={"hours": 0}).status_code == 422
    assert client.post("/summarize", json={"latest": 1000}).status_code == 422


def test_unknown_job_is_404():
    client, _ = make_client()
    assert client.get("/summarize/nope").status_code == 404


def test_gmail_error_reported_on_job():
    client, _ = make_client(FakeGmail(error=GmailError("token expired")))
    job = wait_done(client, client.post("/summarize").json()["job_id"])
    assert job["status"] == "error"
    assert job["error"] == {"kind": "gmail", "message": "token expired"}


def test_ollama_error_reported_on_job():
    client, _ = make_client(summary=FakeSummary(error=OllamaUnavailableError("Ollama is down")))
    job = wait_done(client, client.post("/summarize").json()["job_id"])
    assert job["error"]["kind"] == "ollama"


def test_unexpected_error_does_not_leak_details():
    client, _ = make_client(summary=FakeSummary(error=RuntimeError("secret internals")))
    job = wait_done(client, client.post("/summarize").json()["job_id"])
    assert job["error"]["kind"] == "internal"
    assert "secret" not in job["error"]["message"]


def test_token_required_when_configured():
    client, _ = make_client(config=replace(settings, api_token="s3cret"))
    assert client.post("/summarize").status_code == 401
    assert client.post("/summarize", headers={"Authorization": "Bearer wrong"}).status_code == 401
    ok = {"Authorization": "Bearer s3cret"}
    resp = client.post("/summarize", headers=ok)
    assert resp.status_code == 202
    assert client.get(f"/summarize/{resp.json()['job_id']}").status_code == 401
    assert wait_done(client, resp.json()["job_id"], ok)["status"] == "done"


def test_health_is_open_and_reports_shape():
    client, _ = make_client(config=replace(settings, api_token="s3cret"))
    resp = client.get("/health")  # no token needed
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"ok", "ollama", "gmail"}
    assert "reachable" in body["ollama"] and "signed_in" in body["gmail"]


def test_old_finished_jobs_are_evicted():
    client, _ = make_client()
    ids = []
    for _ in range(5):
        ids.append(client.post("/summarize").json()["job_id"])
        wait_done(client, ids[-1])
    assert client.get(f"/summarize/{ids[0]}").status_code == 404
    assert client.get(f"/summarize/{ids[-1]}").status_code == 200
