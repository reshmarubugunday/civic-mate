#!/bin/bash
# EC2 user-data: installs Docker, pulls the CivicMate image from ECR, and
# runs it. Runs once at first boot; --restart unless-stopped means a reboot
# just restarts the existing container rather than re-running this script.
set -e

dnf install -y docker unzip
systemctl enable docker
systemctl start docker

if ! command -v aws &> /dev/null; then
  curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
  unzip -q /tmp/awscliv2.zip -d /tmp
  /tmp/aws/install
fi

REGION="<REGION>"
ACCOUNT_ID="<ACCOUNT_ID>"

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

docker pull "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/civicmate:latest"

docker run -d --restart unless-stopped -p 8000:8000 \
  -e AWS_REGION="<REGION>" \
  -e BEDROCK_MODEL_ID="amazon.nova-lite-v1:0" \
  -e DYNAMODB_TABLE="civicmate-complaints" \
  -e S3_BUCKET="<YOUR_BUCKET_NAME>" \
  -e MAGIC_LINKS_TABLE="civicmate-magic-links" \
  -e SENDER_EMAIL="<YOUR_SENDGRID_VERIFIED_SENDER_EMAIL>" \
  -e SENDGRID_API_KEY="<YOUR_SENDGRID_API_KEY>" \
  -e APP_BASE_URL="<PUBLIC_URL_e.g._http://this-instances-ip:8000>" \
  -e CIVICMATE_SESSION_SECRET="<GENERATE_WITH_openssl_rand_-hex_32>" \
  -e FORCE_DEMO_ENGINE="0" \
  --name civicmate \
  "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/civicmate:latest"
