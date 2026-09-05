"""Sends transactional email (magic-link sign-in, case status updates) via Brevo.

Two providers were tried first and abandoned:
- SES sandbox mode requires every *recipient* to be individually
  pre-verified until AWS grants production access, which defeats the
  point of letting arbitrary citizens sign in.
- SendGrid's "free" tier turned out to be a 60-day trial, not permanent.

Brevo's free plan (300 emails/day, no credit card, no time limit) uses
the same single-sender-verification model that made SendGrid attractive:
verify the sender once, then any recipient works immediately — no AWS
review, no per-citizen verification, no expiry.

Falls back to logging server-side (never returning the content via an API
response for the magic link — that would defeat the point of verification)
when Brevo isn't configured or a send fails. Email must degrade, not break,
core flows — same philosophy as every other integration in this app
(store.py, evidence.py, agent.py).

Honest limitation: a `True` return means Brevo's API *accepted* the send
for processing, not that it was confirmed delivered — that only shows up
later in Brevo's own async event log. See ARCHITECTURE.md section 19b for
the incident where this distinction mattered (a misconfigured sender was
accepted every time and silently never delivered).
"""
import json
import logging
import urllib.error
import urllib.request

from app import config

logger = logging.getLogger("civicmate.email")

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def _send(to_email: str, subject: str, body: str, fallback_detail: str) -> bool:
    """Returns True if Brevo accepted the send, False if it fell back to
    logging. Never raises."""
    if not config.BREVO_API_KEY or not config.SENDER_EMAIL:
        logger.warning("Brevo not configured; %s", fallback_detail)
        return False

    payload = {
        "sender": {"name": "CivicMate AI", "email": config.SENDER_EMAIL},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": body,
    }
    request = urllib.request.Request(
        BREVO_API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "api-key": config.BREVO_API_KEY,
            "content-type": "application/json",
            "accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        logger.warning(
            "Brevo send failed (%s %s): %s. Falling back to logging. %s",
            exc.code, exc.reason, detail, fallback_detail,
        )
        return False
    except (urllib.error.URLError, TimeoutError, Exception) as exc:  # noqa: BLE001
        logger.warning("Brevo send failed (%s). Falling back to logging. %s", exc, fallback_detail)
        return False


def send_magic_link(to_email: str, link_url: str) -> bool:
    body = (
        f"Click to sign in to CivicMate AI (valid for "
        f"{config.MAGIC_LINK_TTL_SECONDS // 60} minutes):\n\n{link_url}\n\n"
        "If you didn't request this, you can ignore this email."
    )
    return _send(
        to_email, "Sign in to CivicMate AI", body,
        fallback_detail=f"magic link for {to_email}: {link_url}",
    )


def send_status_update(to_email: str, reference_number: str, event: str, detail: str) -> bool:
    """Notifies a citizen of an autonomous follow-up/escalation decision
    (app/scheduler.py) — the agent acting on its own, not a human clicking
    a button, so the citizen finds out the same way: automatically."""
    body = (
        f"Update on your CivicMate report {reference_number}:\n\n"
        f"{event}\n{detail}\n\n"
        "This update was generated automatically by CivicMate AI, without a "
        "person needing to check on your case."
    )
    return _send(
        to_email, f"CivicMate update: {reference_number}", body,
        fallback_detail=f"status update for {reference_number} to {to_email}: {event}",
    )
