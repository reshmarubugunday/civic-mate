import os

from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "civicmate-complaints")
S3_BUCKET = os.getenv("S3_BUCKET", "civicmate-evidence-change-me")
FORCE_DEMO_ENGINE = os.getenv("FORCE_DEMO_ENGINE", "0") == "1"

# ARN of the deployed AgentCore Runtime (infra/agentcore-runtime.json). If unset,
# triage falls back to a direct in-process Strands + Bedrock call (app/agent.py).
AGENTCORE_RUNTIME_ARN = os.getenv("AGENTCORE_RUNTIME_ARN", "")

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_UPLOAD_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
