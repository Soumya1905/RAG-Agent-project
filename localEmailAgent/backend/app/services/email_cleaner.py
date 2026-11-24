"""Regex cleanup that strips non-content text from email bodies before summarizing.

Removes quoted reply chains, signatures, unsubscribe/footer boilerplate and long URLs.
Pure functions, no model or network involved.
"""
import re

# Everything from one of these markers onward is quoted history or a signature.
_CUT_MARKERS = [
    re.compile(r"(?ims)^[ \t]*on\s.{0,250}?\swrote:"),  # Gmail/Apple "On ... wrote:"
    re.compile(r"(?im)^[ \t]*-{2,}\s*original message\s*-{2,}"),  # Outlook
    re.compile(r"(?im)^[ \t]*-{2,}\s*forwarded message\s*-{2,}"),
    re.compile(r"(?im)^[ \t]*from:.{0,200}\n[ \t]*sent:"),  # Outlook header block
    re.compile(r"(?m)^-- ?$"),  # standard signature delimiter
    re.compile(r"(?im)^[ \t]*sent from my (iphone|ipad|android|mobile|galaxy)"),
]

# Single lines that are footer boilerplate.
_BOILERPLATE_LINE = re.compile(
    r"(?i)unsubscribe|view (this email )?in (your )?browser|you are receiving this|"
    r"you received this (email|message)|manage (your )?(email )?preferences|"
    r"all rights reserved|this email was sent to"
)
_URL = re.compile(r"https?://\S+|www\.\S+")


def clean_email_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Cut at the earliest quote/signature marker.
    cut = len(text)
    for marker in _CUT_MARKERS:
        m = marker.search(text)
        if m:
            cut = min(cut, m.start())
    text = text[:cut]

    lines = [
        line
        for line in text.split("\n")
        if not line.lstrip().startswith(">") and not _BOILERPLATE_LINE.search(line)
    ]
    text = "\n".join(lines)

    text = _URL.sub("[link]", text)
    text = re.sub(r"(\[link\][ \t]*){2,}", "[link] ", text)  # runs of links
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
