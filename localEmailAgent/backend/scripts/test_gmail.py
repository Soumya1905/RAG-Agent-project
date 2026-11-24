"""Fetch recent emails from Gmail and print a short preview of each.

Usage (from the backend/ directory):
    python -m scripts.test_gmail            # latest 5 emails
    python -m scripts.test_gmail 3 "is:unread"
The first run opens a browser for Google sign-in and saves secrets/token.json.
"""
import sys

from app.services.gmail_service import GmailError, GmailService


sys.stdout.reconfigure(encoding="utf-8")  # emails contain emoji; Windows default is cp1252


def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    query = sys.argv[2] if len(sys.argv) > 2 else ""
    try:
        emails = GmailService().list_emails(max_results=count, query=query)
    except GmailError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Fetched {len(emails)} email(s)\n")
    for e in emails:
        print(f"From:    {e.sender}\nDate:    {e.date}\nSubject: {e.subject}")
        print(f"Body:    {e.body[:200]!r}\n" + "-" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
