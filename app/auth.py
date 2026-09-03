"""Lightweight citizen session model.

This is deliberately NOT full authentication — there is no password and no
email-ownership verification (no magic link / OTP). It exists to close the
"anyone can list anyone's complaints" gap: a citizen calls POST /api/session
with their email and gets back an opaque token that scopes every subsequent
request to that email. Forging a token for an email you don't own requires
the server-side secret, so a casual client can no longer enumerate other
citizens' complaints just by calling the list endpoint.

Production hardening path (not built): send the token via a verified email
link (magic link) or OTP instead of returning it directly in the API
response, so the token proves mailbox ownership rather than just claimed
ownership.
"""
import hashlib
import hmac
import os

from fastapi import Header, HTTPException

_SECRET = os.getenv("CIVICMATE_SESSION_SECRET")
if not _SECRET:
    # Dev-only fallback so the app still runs without extra setup. Tokens
    # minted with this secret are NOT stable across restarts in production —
    # set CIVICMATE_SESSION_SECRET explicitly outside local dev.
    _SECRET = "dev-insecure-secret-set-CIVICMATE_SESSION_SECRET"


def issue_token(email: str) -> str:
    normalized = email.strip().lower()
    return hmac.new(_SECRET.encode(), normalized.encode(), hashlib.sha256).hexdigest()[:32]


def verify_token(email: str, token: str) -> bool:
    expected = issue_token(email)
    return hmac.compare_digest(expected, token)


def require_citizen(
    x_citizen_email: str | None = Header(None),
    x_citizen_token: str | None = Header(None),
) -> str:
    """FastAPI dependency: returns the authenticated citizen's normalized email."""
    if not x_citizen_email or not x_citizen_token or not verify_token(x_citizen_email, x_citizen_token):
        raise HTTPException(401, "Invalid or missing citizen session")
    return x_citizen_email.strip().lower()
