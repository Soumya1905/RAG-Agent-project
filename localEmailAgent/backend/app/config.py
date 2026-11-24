"""Central configuration, read from environment variables with safe local defaults."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# Values in backend/.env fill in anything not already set in the real environment.
load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:4b-instruct-2507-q4_K_M")
    ollama_timeout: float = float(os.getenv("OLLAMA_TIMEOUT", "300"))
    # Qwen3 "thinking" mode is slow on small hardware; off by default.
    ollama_num_ctx: int = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
    ollama_think: bool = _env_bool("OLLAMA_THINK", False)

    # Gmail (read-only). Both files live in the git-ignored secrets/ folder.
    gmail_credentials_path: Path = Path(
        os.getenv("GMAIL_CREDENTIALS_PATH", BASE_DIR / "secrets" / "credentials.json")
    )
    gmail_token_path: Path = Path(
        os.getenv("GMAIL_TOKEN_PATH", BASE_DIR / "secrets" / "token.json")
    )
    gmail_max_results: int = int(os.getenv("GMAIL_MAX_RESULTS", "10"))
    # "Summarize" window: how far back to look, and a safety cap on emails fetched.
    summary_window_hours: int = int(os.getenv("SUMMARY_WINDOW_HOURS", "12"))
    gmail_window_max_emails: int = int(os.getenv("GMAIL_WINDOW_MAX_EMAILS", "25"))
    gmail_exclude_noise: bool = _env_bool("GMAIL_EXCLUDE_NOISE", True)  # promotions + social

    # API. Default binds to this machine only. To reach it from a phone, set API_HOST=0.0.0.0
    # AND set API_TOKEN so only your app can read your email digests.
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    api_token: str = os.getenv("API_TOKEN", "")
    api_max_jobs: int = int(os.getenv("API_MAX_JOBS", "20"))  # finished jobs kept in memory

    # Summaries: each email is trimmed to email_max_chars, then emails are packed into
    # chunks of at most chunk_max_chars so every model call stays small and fast on CPU.
    email_max_chars: int = int(os.getenv("EMAIL_MAX_CHARS", "1200"))
    chunk_max_chars: int = int(os.getenv("CHUNK_MAX_CHARS", "4000"))


settings = Settings()
