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

# Citizen email verification (magic link, see app/magic_link.py + app/email_sender.py).
# Sent via Brevo rather than SES or SendGrid: SES sandbox mode requires every
# recipient to be individually pre-verified (defeats letting arbitrary citizens
# sign in); SendGrid's "free" tier is a 60-day trial, not permanent. Brevo's free
# plan (300 emails/day) has neither limitation, and uses the same
# verify-the-sender-once model — any recipient works after that.
MAGIC_LINKS_TABLE = os.getenv("MAGIC_LINKS_TABLE", "civicmate-magic-links")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
MAGIC_LINK_TTL_SECONDS = 15 * 60

# Autonomous follow-through (app/scheduler.py): a background loop periodically
# asks the agent whether each open complaint needs a follow-up or escalation,
# rather than a human clicking "Simulate follow-up/escalation." Defaults are
# realistic (24h/72h); override for a demo where waiting a real day isn't
# practical (e.g. FOLLOWUP_THRESHOLD_SECONDS=60 ESCALATION_THRESHOLD_SECONDS=120).
AUTONOMOUS_FOLLOWTHROUGH_ENABLED = os.getenv("AUTONOMOUS_FOLLOWTHROUGH_ENABLED", "1") == "1"
AUTONOMOUS_CHECK_INTERVAL_SECONDS = float(os.getenv("AUTONOMOUS_CHECK_INTERVAL_SECONDS", "300"))
FOLLOWUP_THRESHOLD_SECONDS = float(os.getenv("FOLLOWUP_THRESHOLD_SECONDS", str(24 * 3600)))
ESCALATION_THRESHOLD_SECONDS = float(os.getenv("ESCALATION_THRESHOLD_SECONDS", str(72 * 3600)))

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_UPLOAD_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
