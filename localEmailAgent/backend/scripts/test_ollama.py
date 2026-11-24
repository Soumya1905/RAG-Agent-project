"""Send a prompt to the local Ollama model and print the reply.

Usage (from the backend/ directory):
    python -m scripts.test_ollama
    python -m scripts.test_ollama "Summarize: meeting moved to 3pm Friday."
"""
import sys

from app.config import settings
from app.services.ollama_service import OllamaError, OllamaService


sys.stdout.reconfigure(encoding="utf-8")  # emails contain emoji; Windows default is cp1252


def main() -> int:
    prompt = " ".join(sys.argv[1:]) or "Reply with one short sentence confirming you are working."
    print(f"Model: {settings.ollama_model} @ {settings.ollama_host}")
    print(f"Prompt: {prompt}\n")
    try:
        print(OllamaService().generate(prompt))
    except OllamaError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
