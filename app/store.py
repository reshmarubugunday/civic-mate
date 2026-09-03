"""Complaint persistence: DynamoDB-backed, with an in-memory fallback so
local development keeps working before AWS resources exist."""
import logging
from typing import List, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app import config
from app.models import Complaint

logger = logging.getLogger("civicmate.store")


class InMemoryStore:
    def __init__(self):
        self._data: dict[str, Complaint] = {}

    def put(self, complaint: Complaint) -> None:
        self._data[complaint.complaint_id] = complaint

    def get(self, complaint_id: str) -> Optional[Complaint]:
        return self._data.get(complaint_id)

    def list(self) -> List[Complaint]:
        return sorted(self._data.values(), key=lambda c: c.created_at, reverse=True)


class DynamoDBStore:
    def __init__(self, table_name: str, region_name: str):
        self._resource = boto3.resource("dynamodb", region_name=region_name)
        self._table = self._resource.Table(table_name)
        self._table.load()  # raises if the table doesn't exist / isn't reachable

    def put(self, complaint: Complaint) -> None:
        self._table.put_item(Item=complaint.model_dump(mode="json"))

    def get(self, complaint_id: str) -> Optional[Complaint]:
        response = self._table.get_item(Key={"complaint_id": complaint_id})
        item = response.get("Item")
        return Complaint.model_validate(item) if item else None

    def list(self) -> List[Complaint]:
        items = self._table.scan().get("Items", [])
        complaints = [Complaint.model_validate(item) for item in items]
        return sorted(complaints, key=lambda c: c.created_at, reverse=True)


def build_store():
    try:
        store = DynamoDBStore(config.DYNAMODB_TABLE, config.AWS_REGION)
        logger.info("Using DynamoDB store (table=%s)", config.DYNAMODB_TABLE)
        return store
    except (BotoCoreError, ClientError, Exception) as exc:  # noqa: BLE001
        logger.warning(
            "DynamoDB unavailable (%s); falling back to in-memory store. "
            "Run scripts/setup_aws.py to create the table.", exc,
        )
        return InMemoryStore()


store = build_store()
