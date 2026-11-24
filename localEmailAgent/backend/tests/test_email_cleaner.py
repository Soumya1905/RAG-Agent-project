from app.services.email_cleaner import clean_email_text


def test_strips_quoted_reply_gmail_style():
    t = "Sounds good, see you at 3.\n\nOn Mon, Jan 5, 2026 at 9:00 AM Bob <bob@x.com>\nwrote:\n> Can we meet?\n> At 3?"
    assert clean_email_text(t) == "Sounds good, see you at 3."


def test_strips_outlook_original_message():
    t = "Approved.\n\n-----Original Message-----\nFrom: A\nSent: Monday\nPlease approve."
    assert clean_email_text(t) == "Approved."


def test_strips_signature_delimiter():
    assert clean_email_text("Report due Friday 5pm.\n-- \nJohn Smith\nCEO") == "Report due Friday 5pm."


def test_strips_gt_quote_lines_and_footer():
    t = "Hello\n> old text\nPlease reply by Tuesday.\nClick here to unsubscribe from this list"
    assert clean_email_text(t) == "Hello\nPlease reply by Tuesday."


def test_replaces_urls_and_collapses_whitespace():
    t = "See https://example.com/track?id=abc123&x=y   for   details\n\n\n\nThanks"
    assert clean_email_text(t) == "See [link] for details\n\nThanks"


def test_keeps_deadline_content_intact():
    t = "The invoice of $450 is due on 12 March. On Friday we ship the order."
    assert clean_email_text(t) == t


def test_empty():
    assert clean_email_text("") == ""
