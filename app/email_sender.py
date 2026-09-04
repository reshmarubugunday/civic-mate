"""Sends the magic-link verification email via SendGrid.

SES was tried first but abandoned for this purpose: SES sandbox mode
requires every *recipient* to be individually pre-verified until AWS
grants production access, which defeats the point of letting arbitrary
citizens sign in — only the app's own verified sender could receive mail.
SendGrid's single-sender verification model only requires verifying the
sender once; after that, any recipient works immediately, no per-citizen
verification and no AWS review wait.

Falls back to logging the link server-side (never returning it via the
API — that would defeat the point of verification) when SendGrid isn't
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

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


def send_magic_link(to_email: str, link_url: str) -> bool:
    """Returns True if SendGrid accepted the send, False if it fell back to
    logging. Never raises."""
    if not config.SENDGRID_API_KEY or not config.SENDER_EMAIL:
        logger.warning("SendGrid not configured; magic link for %s: %s", to_email, link_url)
        return False

    body = (
        f"Click to sign in to CivicMate AI (valid for "
        f"{config.MAGIC_LINK_TTL_SECONDS // 60} minutes):\n\n{link_url}\n\n"
        "If you didn't request this, you can ignore this email."
    )
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": config.SENDER_EMAIL, "name": "CivicMate AI"},
        "subject": "Sign in to CivicMate AI",
        "content": [{"type": "text/plain", "value": body}],
    }
    request = urllib.request.Request(
        SENDGRID_API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {config.SENDGRID_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        logger.warning(
            "SendGrid send failed (%s %s): %s. Falling back to logging. Magic link for %s: %s",
            exc.code, exc.reason, detail, to_email, link_url,
        )
        return False
    except (urllib.error.URLError, TimeoutError, Exception) as exc:  # noqa: BLE001
        logger.warning(
            "SendGrid send failed (%s). Falling back to logging. Magic link for %s: %s",
            exc, to_email, link_url,
        )
        return False
