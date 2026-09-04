"""One-time provisioning of the AWS resources CivicMate needs:
DynamoDB table for complaint records, S3 bucket for photo evidence.

Run once after `aws configure` (or equivalent credential setup):

    python scripts/setup_aws.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boto3
from botocore.exceptions import ClientError

from app import config


def ensure_dynamodb_table():
    ddb = boto3.client("dynamodb", region_name=config.AWS_REGION)
    try:
        ddb.describe_table(TableName=config.DYNAMODB_TABLE)
        print(f"[dynamodb] table already exists: {config.DYNAMODB_TABLE}")
        return
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    print(f"[dynamodb] creating table: {config.DYNAMODB_TABLE}")
    ddb.create_table(
        TableName=config.DYNAMODB_TABLE,
        KeySchema=[{"AttributeName": "complaint_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "complaint_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    ddb.get_waiter("table_exists").wait(TableName=config.DYNAMODB_TABLE)
    print("[dynamodb] table ready")


def ensure_magic_links_table():
    ddb = boto3.client("dynamodb", region_name=config.AWS_REGION)
    try:
        ddb.describe_table(TableName=config.MAGIC_LINKS_TABLE)
        print(f"[dynamodb] table already exists: {config.MAGIC_LINKS_TABLE}")
        return
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    print(f"[dynamodb] creating table: {config.MAGIC_LINKS_TABLE}")
    ddb.create_table(
        TableName=config.MAGIC_LINKS_TABLE,
        KeySchema=[{"AttributeName": "token", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "token", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    ddb.get_waiter("table_exists").wait(TableName=config.MAGIC_LINKS_TABLE)
    ddb.update_time_to_live(
        TableName=config.MAGIC_LINKS_TABLE,
        TimeToLiveSpecification={"Enabled": True, "AttributeName": "expires_at"},
    )
    print("[dynamodb] table ready, TTL enabled on expires_at (unused links auto-expire)")


def ensure_s3_bucket():
    s3 = boto3.client("s3", region_name=config.AWS_REGION)
    try:
        s3.head_bucket(Bucket=config.S3_BUCKET)
        print(f"[s3] bucket already exists: {config.S3_BUCKET}")
        return
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code not in ("404", "NoSuchBucket"):
            raise

    print(f"[s3] creating bucket: {config.S3_BUCKET}")
    kwargs = {"Bucket": config.S3_BUCKET}
    if config.AWS_REGION != "us-east-1":
        kwargs["CreateBucketConfiguration"] = {"LocationConstraint": config.AWS_REGION}
    s3.create_bucket(**kwargs)
    s3.put_public_access_block(
        Bucket=config.S3_BUCKET,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    print("[s3] bucket ready (public access blocked)")


if __name__ == "__main__":
    if config.S3_BUCKET.endswith("-change-me") or "CHANGE-ME" in config.S3_BUCKET.upper():
        sys.exit(
            "S3_BUCKET is still the placeholder value. Set a globally-unique "
            "bucket name in your .env before running setup."
        )
    ensure_dynamodb_table()
    ensure_magic_links_table()
    ensure_s3_bucket()
    if not config.BREVO_API_KEY:
        print(
            "[brevo] BREVO_API_KEY not set — magic-link emails will log instead of send. "
            "Verify a sender at app.brevo.com (Senders, Domains & Dedicated IPs > Senders) "
            "and set BREVO_API_KEY + SENDER_EMAIL in .env."
        )
    print("\nAWS resources ready. Start the app with: uvicorn app.main:app --reload")
