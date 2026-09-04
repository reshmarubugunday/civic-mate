"""Sends the magic-link verification email via SES.

Falls back to logging the link server-side (never returning it via the API
— that would defeat the point of verification) when SES isn't configured
or reachable, e.g. no SES_SENDER_EMAIL set, the sender identity isn't
verified yet, or the account is still in SES sandbox mode and the
recipient hasn't been separately verified. Sign-in must degrade, not
break, when email delivery isn't available — same philosophy as every
other AWS integration in this app (store.py, evidence.py, agent.py).
"""
import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app import config

logger = logging.getLogger("civicmate.email")


def send_magic_link(to_email: str, link_url: str) -> bool:
    """Returns True if actually handed off to SES, False if it fell back to
    logging. Never raises."""
    if not config.SES_SENDER_EMAIL:
        logger.warning("SES_SENDER_EMAIL not configured; magic link for %s: %s", to_email, link_url)
        return False

    body = (
        f"Click to sign in to CivicMate AI (valid for "
        f"{config.MAGIC_LINK_TTL_SECONDS // 60} minutes):\n\n{link_url}\n\n"
        "If you didn't request this, you can ignore this email."
    )
    try:
        client = boto3.client("ses", region_name=config.AWS_REGION)
        client.send_email(
            Source=config.SES_SENDER_EMAIL,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": "Sign in to CivicMate AI"},
                "Body": {"Text": {"Data": body}},
            },
        )
        return True
    except (BotoCoreError, ClientError, Exception) as exc:  # noqa: BLE001
        logger.warning(
            "SES send failed (%s) — likely sandbox mode with an unverified recipient. "
            "Falling back to logging. Magic link for %s: %s", exc, to_email, link_url,
        )
        return False
