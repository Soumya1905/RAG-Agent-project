"""FastAPI app: start a summarize job, poll its progress, check service health.

Run (from backend/):  python -m scripts.run_api     then open http://127.0.0.1:8000/docs
"""
import hmac
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.config import Settings, settings as default_settings
from app.jobs import JobManager
from app.services.ollama_service import OllamaService


class SummarizeRequest(BaseModel):
    """Pick a time window OR a count. Neither = the default window (SUMMARY_WINDOW_HOURS)."""

    hours: float | None = Field(None, gt=0, le=168, description="Emails from the last N hours")
    latest: int | None = Field(None, ge=1, le=100, description="The newest N emails")

    @model_validator(mode="after")
    def _one_mode(self):
        if self.hours is not None and self.latest is not None:
            raise ValueError("Provide either 'hours' or 'latest', not both.")
        return self


def create_app(manager: JobManager | None = None, config: Settings = default_settings) -> FastAPI:
    manager = manager or JobManager(max_jobs=config.api_max_jobs)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        manager.shutdown()

    app = FastAPI(title="Local Email Assistant", lifespan=lifespan)

    def require_token(authorization: str | None = Header(None)) -> None:
        """If API_TOKEN is set, require 'Authorization: Bearer <token>'."""
        if config.api_token and not hmac.compare_digest(
            authorization or "", f"Bearer {config.api_token}"
        ):
            raise HTTPException(status_code=401, detail="Missing or invalid token.")

    @app.get("/health")
    def health() -> dict:
        """Is Ollama up with the model installed, and are Gmail credentials in place?"""
        ollama_status = OllamaService(config).check()
        gmail_ready = config.gmail_token_path.exists()
        return {
            "ok": ollama_status["reachable"] and ollama_status["model_installed"] and gmail_ready,
            "ollama": {"model": config.ollama_model, **ollama_status},
            "gmail": {
                "credentials_file": config.gmail_credentials_path.exists(),
                "signed_in": gmail_ready,  # token.json exists (run scripts.test_gmail once)
            },
        }

    @app.post("/summarize", status_code=202, dependencies=[Depends(require_token)])
    def start_summary(req: SummarizeRequest | None = None) -> dict:
        """Start a background summary. Poll GET /summarize/{job_id} for progress and the result."""
        req = req or SummarizeRequest()
        job = manager.submit(hours=req.hours, latest=req.latest)
        return {"job_id": job.id, "status": job.status}

    @app.get("/summarize/{job_id}", dependencies=[Depends(require_token)])
    def get_summary(job_id: str) -> dict:
        job = manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Unknown job id (jobs are lost on restart).")
        return job.to_dict()

    return app


app = create_app()
