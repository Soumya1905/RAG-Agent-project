"""Fetch inbox emails and show what cleanup and trimming do to each. No model is called.

Usage (from the backend/ directory):
    python -m scripts.test_fetch_clean                 # last SUMMARY_WINDOW_HOURS hours
    python -m scripts.test_fetch_clean --hours 24
    python -m scripts.test_fetch_clean --latest 15     # newest 15 emails instead of a time window
    python -m scripts.test_fetch_clean --all           # include Promotions/Social
    python -m scripts.test_fetch_clean --show          # also print the trimmed text
"""
import argparse
import sys

from app.config import settings
from app.services.email_cleaner import clean_email_text
from app.services.email_trimmer import trim_text
from app.services.gmail_service import GmailError, GmailService

sys.stdout.reconfigure(encoding="utf-8")  # emails contain emoji; Windows default is cp1252


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float)
    ap.add_argument("--latest", type=int)
    ap.add_argument("--all", action="store_true", help="include Promotions/Social")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()
    noise = False if args.all else None

    gmail = GmailService()
    try:
        result = (
            gmail.fetch_latest(args.latest, exclude_noise=noise)
            if args.latest
            else gmail.fetch_since(args.hours, exclude_noise=noise)
        )
    except GmailError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    raw_total = final_total = 0
    print(f"Fetched {len(result.emails)} email(s)" + (" (more existed; capped)" if result.truncated else ""))
    print(f"{'subject':<50} {'raw':>7} {'clean':>7} {'final':>7}\n")
    for e in result.emails:
        raw = e.body or e.snippet
        cleaned = clean_email_text(raw)
        final = trim_text(cleaned, settings.email_max_chars)
        raw_total += len(raw)
        final_total += len(final)
        print(f"{e.subject[:48]!r:<50} {len(raw):>7} {len(cleaned):>7} {len(final):>7}")
        if args.show:
            print(f"    {final[:600]!r}\n")
    if raw_total:
        print(f"\nTotal: {raw_total} -> {final_total} chars ({100 - 100 * final_total // raw_total}% removed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
