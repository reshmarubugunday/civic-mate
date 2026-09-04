"""Sends the magic-link verification email via Brevo.

Two providers were tried first and abandoned:
- SES sandbox mode requires every *recipient* to be individually
  pre-verified until AWS grants production access, which defeats the
  point of letting arbitrary citizens sign in.
- SendGrid's "free" tier turned out to be a 60-day trial, not permanent.

Brevo's free plan (300 emails/day, no credit card, no time limit) uses
the same single-sender-verification model that made SendGrid attractive:
verify the sender once, then any recipient works immediately — no AWS
review, no per-citizen verification, no expiry.

Falls back to logging the link server-side (never returning it via the
API — that would defeat the point of verification) when Brevo isn't
configured or a send fails. Sign-in must degrade, not break, when email
delivery isn't available — same philosophy as every other integration in
this app (store.py, evidence.py, agent.py).
"""
import json
import logging
import urllib.error
import urllib.request

from app import config

logger = logging.getLogger("civicmate.email")

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def send_magic_link(to_email: str, link_url: str) -> bool:
    """Returns True if Brevo accepted the send, False if it fell back to
    logging. Never raises."""
    if not config.BREVO_API_KEY or not config.SENDER_EMAIL:
        logger.warning("Brevo not configured; magic link for %s: %s", to_email, link_url)
        return False

    body = (
        f"Click to sign in to CivicMate AI (valid for "
        f"{config.MAGIC_LINK_TTL_SECONDS // 60} minutes):\n\n{link_url}\n\n"
        "If you didn't request this, you can ignore this email."
    )
    payload = {
        "sender": {"name": "CivicMate AI", "email": config.SENDER_EMAIL},
        "to": [{"email": to_email}],
        "subject": "Sign in to CivicMate AI",
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
            "Brevo send failed (%s %s): %s. Falling back to logging. Magic link for %s: %s",
            exc.code, exc.reason, detail, to_email, link_url,
        )
        return False
    except (urllib.error.URLError, TimeoutError, Exception) as exc:  # noqa: BLE001
        logger.warning(
            "Brevo send failed (%s). Falling back to logging. Magic link for %s: %s",
            exc, to_email, link_url,
        )
        return False
