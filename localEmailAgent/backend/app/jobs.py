"""In-memory background jobs for summarization.

One worker thread runs jobs one at a time: the model is CPU-bound, so running two summaries
at once would just make both slower. Jobs live in memory only and are lost on restart.
"""
import logging
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from app.services.gmail_service import GmailError, GmailService
from app.services.ollama_service import OllamaError
from app.services.summary_service import SummaryService

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Job:
    id: str
    hours: float | None
    latest: int | None
    status: str = "queued"  # queued -> fetching -> summarizing -> done | error
    step: int = 0
    total: int = 0
    stage: str = ""
    created_at: str = field(default_factory=_now)
    finished_at: str | None = None
    result: dict | None = None
    error: dict | None = None  # {"kind": "gmail" | "ollama" | "internal", "message": str}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "progress": {"step": self.step, "total": self.total, "stage": self.stage},
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
        }


class JobManager:
    def __init__(
        self,
        gmail_factory: Callable[[], GmailService] = GmailService,
        summary_factory: Callable[[], SummaryService] = SummaryService,
        max_jobs: int = 20,
    ):
        self._gmail_factory = gmail_factory
        self._summary_factory = summary_factory
        self._max_jobs = max_jobs
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="summarize")

    def submit(self, hours: float | None = None, latest: int | None = None) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], hours=hours, latest=latest)
        with self._lock:
            self._jobs[job.id] = job
            self._evict()
        self._executor.submit(self._run, job)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _evict(self) -> None:
        """Drop the oldest finished jobs once more than max_jobs are held."""
        for job_id in list(self._jobs):
            if len(self._jobs) <= self._max_jobs:
                break
            if self._jobs[job_id].status in {"done", "error"}:
                del self._jobs[job_id]

    def _run(self, job: Job) -> None:
        started = time.time()
        try:
            job.status, job.stage = "fetching", "fetching emails"
            gmail = self._gmail_factory()
            fetched = (
                gmail.fetch_latest(job.latest) if job.latest else gmail.fetch_since(job.hours)
            )

            job.status, job.stage = "summarizing", "summarizing"

            def on_progress(step: int, total: int, label: str) -> None:
                job.step, job.total, job.stage = step, total, label

            digest = self._summary_factory().digest(fetched.emails, on_progress=on_progress)
            job.result = {
                "items": [asdict(item) for item in digest.items],
                "digest": digest.text,
                "email_count": digest.email_count,
                "chunk_count": digest.chunk_count,
                "model_calls": digest.model_calls,
                "truncated": fetched.truncated,
                "elapsed_seconds": round(time.time() - started),
            }
            job.status = "done"
        except GmailError as exc:
            job.status, job.error = "error", {"kind": "gmail", "message": str(exc)}
        except OllamaError as exc:
            job.status, job.error = "error", {"kind": "ollama", "message": str(exc)}
        except Exception:
            log.exception("Summarize job %s failed", job.id)
            job.status = "error"
            job.error = {"kind": "internal", "message": "Unexpected error; see the server log."}
        finally:
            job.finished_at = _now()
