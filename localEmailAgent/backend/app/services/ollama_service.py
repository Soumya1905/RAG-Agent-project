"""Thin wrapper around the Ollama Python client with clear error handling."""
from typing import TypeVar

import ollama
from pydantic import BaseModel, ValidationError

from app.config import Settings, settings as default_settings

T = TypeVar("T", bound=BaseModel)


class OllamaError(Exception):
    """Base class for Ollama service errors."""


class OllamaInvalidOutputError(OllamaError):
    """The model answered, but not in the requested structure."""


class OllamaUnavailableError(OllamaError):
    """Ollama server is not reachable."""


class OllamaModelNotFoundError(OllamaError):
    """The configured model is not installed in Ollama."""


class OllamaService:
    def __init__(self, config: Settings = default_settings):
        self.config = config
        self.client = ollama.Client(host=config.ollama_host, timeout=config.ollama_timeout)

    def check(self) -> dict:
        """Quick status for /health: is the server reachable and is the model installed?"""
        try:
            installed = {m.model for m in self.client.list().models}
        except Exception as exc:  # any failure here just means "not usable right now"
            return {"reachable": False, "model_installed": False, "detail": str(exc)[:200]}
        return {
            "reachable": True,
            "model_installed": self.config.ollama_model in installed,
            "detail": "" if self.config.ollama_model in installed
            else f"Run: ollama pull {self.config.ollama_model}",
        }

    def generate(self, prompt: str, system: str | None = None) -> str:
        """Send a prompt to the model and return the response text."""
        return self._chat(prompt, system)

    def generate_structured(self, prompt: str, schema: type[T], system: str | None = None) -> T:
        """Ask for JSON matching a Pydantic model; Ollama constrains the output to its schema."""
        text = self._chat(prompt, system, response_format=schema.model_json_schema())
        try:
            return schema.model_validate_json(text)
        except ValidationError as exc:
            raise OllamaInvalidOutputError(
                f"Model returned output that does not match {schema.__name__}."
            ) from exc

    def _chat(self, prompt: str, system: str | None, response_format: dict | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat(
                model=self.config.ollama_model,
                messages=messages,
                think=self.config.ollama_think,
                format=response_format,
                options={"num_ctx": self.config.ollama_num_ctx},
            )
        except ollama.ResponseError as exc:
            if exc.status_code == 404:
                raise OllamaModelNotFoundError(
                    f"Model '{self.config.ollama_model}' not found. "
                    f"Run: ollama pull {self.config.ollama_model}"
                ) from exc
            raise OllamaError(f"Ollama returned an error ({exc.status_code}): {exc.error}") from exc
        except (ConnectionError, OSError) as exc:
            raise OllamaUnavailableError(
                f"Cannot reach Ollama at {self.config.ollama_host}. "
                "Is it running? Start it with: ollama serve"
            ) from exc
        except Exception as exc:  # httpx timeouts etc.
            if "timeout" in type(exc).__name__.lower():
                raise OllamaError(
                    f"Ollama request timed out after {self.config.ollama_timeout}s."
                ) from exc
            raise

        content = response.message.content or ""
        # Some Qwen3 builds emit reasoning inline even with think=False; keep only the answer.
        if "</think>" in content:
            content = content.rsplit("</think>", 1)[1]
        return content.strip()
