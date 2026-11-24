"""Read-only Gmail access via the Gmail API (OAuth 2.0 desktop flow)."""
import base64
import re
import time
from dataclasses import dataclass
from html import unescape

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import Settings, settings as default_settings

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailError(Exception):
    """Base class for Gmail service errors."""


class GmailCredentialsMissingError(GmailError):
    """credentials.json (the OAuth client file) was not found."""


class GmailAuthError(GmailError):
    """Authentication failed or the stored token can no longer be refreshed."""


@dataclass
class Email:
    id: str
    thread_id: str
    subject: str
    sender: str
    date: str
    snippet: str
    body: str


@dataclass
class FetchResult:
    emails: list[Email]
    truncated: bool = False  # True if more matching emails existed than the cap allowed


class GmailService:
    def __init__(self, config: Settings = default_settings):
        self.config = config
        self._service = None

    def _get_credentials(self) -> Credentials:
        token_path = self.config.gmail_token_path
        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                creds = None  # fall through to a fresh login
        else:
            creds = None

        if creds is None:
            cred_path = self.config.gmail_credentials_path
            if not cred_path.exists():
                raise GmailCredentialsMissingError(
                    f"OAuth client file not found at {cred_path}. Download it from "
                    "Google Cloud Console (APIs & Services > Credentials > OAuth client ID "
                    "of type 'Desktop app') and save it there."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES)
            creds = flow.run_local_server(port=0)  # opens browser for consent

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
        return creds

    @property
    def service(self):
        if self._service is None:
            try:
                self._service = build(
                    "gmail", "v1", credentials=self._get_credentials(), cache_discovery=False
                )
            except GmailError:
                raise
            except Exception as exc:
                raise GmailAuthError(f"Gmail authentication failed: {exc}") from exc
        return self._service

    def list_emails(self, max_results: int | None = None, query: str = "") -> list[Email]:
        """Return recent emails (newest first). `query` uses Gmail search syntax."""
        return self._fetch(query, max_results or self.config.gmail_max_results).emails

    def fetch_since(
        self, hours: float | None = None, exclude_noise: bool | None = None
    ) -> FetchResult:
        """Inbox emails received in the last `hours` hours (newest first).

        At most `gmail_window_max_emails` are returned; `truncated` says if older ones were cut.
        """
        hours = hours if hours is not None else self.config.summary_window_hours
        query = f"in:inbox after:{int(time.time() - hours * 3600)}"
        return self._fetch(
            query + self._noise_filter(exclude_noise), self.config.gmail_window_max_emails
        )

    def fetch_latest(self, count: int, exclude_noise: bool | None = None) -> FetchResult:
        """The newest `count` inbox emails (capped at `gmail_window_max_emails`)."""
        limit = min(count, self.config.gmail_window_max_emails)
        result = self._fetch("in:inbox" + self._noise_filter(exclude_noise), limit)
        result.truncated = result.truncated or count > limit
        return result

    def _noise_filter(self, exclude_noise: bool | None) -> str:
        if exclude_noise is None:
            exclude_noise = self.config.gmail_exclude_noise
        return " -category:promotions -category:social" if exclude_noise else ""

    def _fetch(self, query: str, limit: int) -> FetchResult:
        try:
            ids: list[str] = []
            page_token = None
            while len(ids) < limit + 1:  # one extra id tells us whether we cut anything off
                resp = (
                    self.service.users()
                    .messages()
                    .list(
                        userId="me",
                        q=query,
                        maxResults=min(limit + 1 - len(ids), 100),
                        pageToken=page_token,
                    )
                    .execute()
                )
                ids += [m["id"] for m in resp.get("messages", [])]
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
            emails = [
                self._parse(
                    self.service.users().messages().get(userId="me", id=i, format="full").execute()
                )
                for i in ids[:limit]
            ]
            return FetchResult(emails=emails, truncated=len(ids) > limit)
        except HttpError as exc:
            raise GmailError(f"Gmail API error ({exc.status_code}): {exc.reason}") from exc
        except OSError as exc:
            raise GmailError(f"Network error talking to Gmail: {exc}") from exc

    @staticmethod
    def _parse(msg: dict) -> Email:
        payload = msg.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
        return Email(
            id=msg["id"],
            thread_id=msg["threadId"],
            subject=headers.get("subject", "(no subject)"),
            sender=headers.get("from", ""),
            date=headers.get("date", ""),
            snippet=unescape(msg.get("snippet", "")),
            body=_extract_body(payload),
        )


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


def _extract_body(payload: dict) -> str:
    """Prefer text/plain; fall back to tag-stripped text/html."""
    plain, html = [], []

    def walk(part: dict) -> None:
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data and mime == "text/plain":
            plain.append(_decode(data))
        elif data and mime == "text/html":
            html.append(_decode(data))
        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)
    if plain:
        return "\n".join(plain).strip()
    text = re.sub(r"(?is)<(script|style).*?</\1>", "", "\n".join(html))
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()
