"""One-time magic-link tokens for citizen email verification.

Closes the gap flagged in app/auth.py: a session token used to be issued
for any claimed email with no proof of mailbox ownership. Now, a session
token is only issued after the citizen clicks a one-time link mailed to
that address (app/email_sender.py) — proving they can read mail sent
there, not just that they typed a string.

DynamoDB-backed with an in-memory fallback (same pattern as app/store.py),
using DynamoDB TTL to auto-expire unused links rather than relying on a
cleanup job.
"""
import logging
import secrets
import time

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app import config

logger = logging.getLogger("civicmate.magic_link")

TOKEN_BYTES = 24  # -> 32 URL-safe chars, unguessable


class InMemoryLinkStore:
    def __init__(self):
        self._data: dict[str, dict] = {}

    def put(self, token: str, email: str, expires_at: int) -> None:
        self._data[token] = {"email": email, "expires_at": expires_at, "used": False}

    def consume(self, token: str) -> str | None:
        entry = self._data.get(token)
        if not entry or entry["used"] or entry["expires_at"] < time.time():
            return None
        entry["used"] = True
        return entry["email"]


class DynamoDBLinkStore:
    def __init__(self, table_name: str, region_name: str):
        self._table = boto3.resource("dynamodb", region_name=region_name).Table(table_name)
        self._table.load()  # raises if the table doesn't exist / isn't reachable

    def put(self, token: str, email: str, expires_at: int) -> None:
        self._table.put_item(Item={"token": token, "email": email, "expires_at": expires_at, "used": False})

    def consume(self, token: str) -> str | None:
        response = self._table.get_item(Key={"token": token})
        item = response.get("Item")
        if not item or item.get("used") or int(item["expires_at"]) < time.time():
            return None
        self._table.update_item(
            Key={"token": token},
            UpdateExpression="SET used = :true",
            ExpressionAttributeValues={":true": True},
        )
        return item["email"]


def build_store():
    try:
        store = DynamoDBLinkStore(config.MAGIC_LINKS_TABLE, config.AWS_REGION)
        logger.info("Using DynamoDB magic-link store (table=%s)", config.MAGIC_LINKS_TABLE)
        return store
    except (BotoCoreError, ClientError, Exception) as exc:  # noqa: BLE001
        logger.warning(
            "DynamoDB unavailable for magic links (%s); falling back to in-memory store "
            "(links won't survive a restart). Run scripts/setup_aws.py to create the table.", exc,
        )
        return InMemoryLinkStore()


store = build_store()


def create_link_token(email: str) -> str:
    token = secrets.token_urlsafe(TOKEN_BYTES)
    store.put(token, email, int(time.time()) + config.MAGIC_LINK_TTL_SECONDS)
    return token


def consume_link_token(token: str) -> str | None:
    """Returns the verified email if the token is valid and unused, else None.
    Consuming (marking used) happens atomically with the validity check so a
    token can't be replayed even if intercepted."""
    return store.consume(token)
