"""Photo evidence storage: S3-backed, with a local-disk fallback so local
development keeps working before the bucket exists."""
import logging
import os
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app import config

logger = logging.getLogger("civicmate.evidence")

os.makedirs(config.UPLOAD_DIR, exist_ok=True)


class LocalEvidenceStore:
    def save(self, filename: str, content: bytes) -> str:
        safe_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        path = os.path.join(config.UPLOAD_DIR, safe_name)
        with open(path, "wb") as f:
            f.write(content)
        return f"/static/uploads/{safe_name}"


class S3EvidenceStore:
    def __init__(self, bucket: str, region_name: str):
        self._bucket = bucket
        self._client = boto3.client("s3", region_name=region_name)
        self._client.head_bucket(Bucket=bucket)  # raises if unreachable

    def save(self, filename: str, content: bytes) -> str:
        key = f"uploads/{uuid.uuid4().hex[:8]}_{filename}"
        self._client.put_object(Bucket=self._bucket, Key=key, Body=content)
        return f"https://{self._bucket}.s3.amazonaws.com/{key}"


def build_evidence_store():
    try:
        s3_store = S3EvidenceStore(config.S3_BUCKET, config.AWS_REGION)
        logger.info("Using S3 evidence store (bucket=%s)", config.S3_BUCKET)
        return s3_store
    except (BotoCoreError, ClientError, Exception) as exc:  # noqa: BLE001
        logger.warning(
            "S3 unavailable (%s); falling back to local disk storage. "
            "Run scripts/setup_aws.py to create the bucket.", exc,
        )
        return LocalEvidenceStore()


evidence_store = build_evidence_store()
