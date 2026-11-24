"""Fetch inbox emails and summarize them locally with Ollama (clean -> trim -> chunk -> map-reduce).

Usage (from the backend/ directory):
    python -m scripts.test_summary                  # last SUMMARY_WINDOW_HOURS hours
    python -m scripts.test_summary --hours 24
    python -m scripts.test_summary --latest 10      # newest 10 emails instead
    python -m scripts.test_summary --dry-run        # show the chunks only; no model call
"""
import argparse
import sys
import time

from app.services.chunker import build_chunks
from app.services.gmail_service import GmailError, GmailService
from app.services.ollama_service import OllamaError
from app.services.summary_service import SummaryService

sys.stdout.reconfigure(encoding="utf-8")  # emails contain emoji; Windows default is cp1252


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float)
    ap.add_argument("--latest", type=int)
    ap.add_argument("--dry-run", action="store_true", help="show chunks, skip the model")
    args = ap.parse_args()

    try:
        gmail = GmailService()
        result = gmail.fetch_latest(args.latest) if args.latest else gmail.fetch_since(args.hours)
        emails = result.emails
        note = " (more existed; only the newest were fetched)" if result.truncated else ""
        print(f"Fetched {len(emails)} email(s){note}")

        if args.dry_run:
            chunks = build_chunks(emails)
            print(f"{len(chunks)} chunk(s) -> {len(chunks)} model call(s), plus a retry for any invalid answer\n")
            for i, c in enumerate(chunks, 1):
                print(f"=== Chunk {i}: emails {c.first}-{c.first + len(c.blocks) - 1}, {c.size} chars ===")
                print(c.text[:800] + ("\n..." if c.size > 800 else "") + "\n")
            return 0

        start = time.time()

        def progress(step: int, total: int, what: str) -> None:
            print(f"  [{step}/{total}] {what} done ({time.time() - start:.0f}s)")

        digest = SummaryService().digest(emails, on_progress=progress)
        print(f"\n{digest.text}\n\n({digest.email_count} emails, {digest.chunk_count} chunk(s), "
              f"{digest.model_calls} model call(s), {time.time() - start:.0f}s)")
    except (GmailError, OllamaError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
