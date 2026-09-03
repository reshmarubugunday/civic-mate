# CivicMate AI

Civic-assistance agent for reporting local public-service problems. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit AWS_REGION / S3_BUCKET / DYNAMODB_TABLE as needed
```

Configure AWS credentials (`aws configure`, or export `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`), then provision the DynamoDB table and S3 bucket:

```bash
python scripts/setup_aws.py
```

## Run

```bash
uvicorn app.main:app --reload
```

- App: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

If AWS credentials, Bedrock access, DynamoDB, or S3 aren't reachable, CivicMate falls back to a deterministic demo engine and local/in-memory storage — the `/health` endpoint and each complaint's `engine` field always report which mode is active. Set `FORCE_DEMO_ENGINE=1` to force the demo engine regardless of AWS availability.
