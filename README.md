# CivicMate AI

Civic-assistance agent for reporting local public-service problems. Built with the [Strands Agents SDK](https://github.com/strands-agents/sdk-python) and Amazon Bedrock for the [Agents for Humans](https://agentsforhumans.devpost.com/) hackathon — Good Neighbor Agents track. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design.

Licensed under the [MIT License](LICENSE).

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

## Deploy to AWS (App Runner)

App Runner is the simplest managed way to host this: point it at a container image and it gives you a scaling, HTTPS-terminated public URL with no VPC/load-balancer/ECS-cluster setup required.

**Before deploying:** hosting means multiple running instances, so the in-memory store and local-disk upload fallback (fine for local dev) are not safe in production — provision the real DynamoDB table and S3 bucket first with `python scripts/setup_aws.py`, and make sure `.env`'s `S3_BUCKET` points at that bucket.

1. **Build and push the image to ECR** (build for `linux/amd64` so it matches App Runner regardless of your local machine's architecture):

   ```bash
   export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
   export REGION=us-east-1   # match AWS_REGION in .env

   aws ecr create-repository --repository-name civicmate --region $REGION
   aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

   docker buildx build --platform linux/amd64 -t civicmate .
   docker tag civicmate:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/civicmate:latest
   docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/civicmate:latest
   ```

2. **Create the two IAM roles App Runner needs** — one so the App Runner service can pull your private image from ECR, one so the *running container* can call Bedrock/DynamoDB/S3 (least-privilege, scoped to your specific table/bucket/model):

   ```bash
   aws iam create-role --role-name AppRunnerECRAccessRole \
     --assume-role-policy-document file://infra/apprunner-ecr-access-trust-policy.json
   aws iam attach-role-policy --role-name AppRunnerECRAccessRole \
     --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess

   aws iam create-role --role-name CivicMateAppRunnerInstanceRole \
     --assume-role-policy-document file://infra/apprunner-instance-trust-policy.json
   ```

   Edit `infra/apprunner-instance-permissions-policy.json`, replacing `<REGION>`, `<ACCOUNT_ID>`, and `<YOUR_BUCKET_NAME>` with your real values, then attach it:

   ```bash
   aws iam put-role-policy --role-name CivicMateAppRunnerInstanceRole \
     --policy-name CivicMatePermissions \
     --policy-document file://infra/apprunner-instance-permissions-policy.json
   ```

3. **Create the App Runner service.** Edit `infra/apprunner-service.json`, replacing every `<...>` placeholder (account ID, region, bucket name, and a fresh session secret from `openssl rand -hex 32`), then:

   ```bash
   aws apprunner create-service --cli-input-json file://infra/apprunner-service.json
   ```

   `aws apprunner describe-service --service-arn <arn from the output>` shows the assigned public URL once the service reaches `RUNNING`. Auto-deployments are enabled, so pushing a new image tag to the same ECR repo redeploys automatically.

4. Once Bedrock quota clears (section 19 of `ARCHITECTURE.md`), the deployed service starts using real Bedrock inference automatically — no redeploy needed, since that's a runtime fallback, not a build-time choice.

## Deploy the agent to Bedrock AgentCore Runtime (optional)

The triage agent (`agentcore/runtime_app.py`) can run on Amazon Bedrock AgentCore Runtime instead of in-process inside the FastAPI app — the same container/ECR pattern as above, but for the agent alone. Skip this section entirely to keep running the in-process Strands agent (section above); nothing else changes if you do.

AgentCore Runtime **requires ARM64 images** (the Dockerfile already pins this).

1. **Build and push the agent image** (note: `-f agentcore/Dockerfile`, but the build context is the repo root, since it copies `app/tools.py`):

   ```bash
   aws ecr create-repository --repository-name civicmate-agent --region $REGION

   docker buildx build --platform linux/arm64 -f agentcore/Dockerfile -t civicmate-agent .
   docker tag civicmate-agent:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/civicmate-agent:latest
   docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/civicmate-agent:latest
   ```

2. **Create the AgentCore execution role** (edit `infra/agentcore-trust-policy.json` and `infra/agentcore-execution-permissions-policy.json` first, replacing `<REGION>`, `<ACCOUNT_ID>`, `<AGENT_NAME>` with `civicmate_triage`):

   ```bash
   aws iam create-role --role-name CivicMateAgentCoreExecutionRole \
     --assume-role-policy-document file://infra/agentcore-trust-policy.json
   aws iam put-role-policy --role-name CivicMateAgentCoreExecutionRole \
     --policy-name CivicMateAgentCorePermissions \
     --policy-document file://infra/agentcore-execution-permissions-policy.json
   ```

3. **Create the AgentCore Runtime.** Edit `infra/agentcore-runtime.json`'s placeholders, then:

   ```bash
   aws bedrock-agentcore-control create-agent-runtime --cli-input-json file://infra/agentcore-runtime.json
   ```

   (Requires a recent `aws-cli` version — update with `brew upgrade awscli` if this command isn't recognized.) The response includes `agentRuntimeArn`.

4. **Point the backend at it.** Add `AGENTCORE_RUNTIME_ARN=<arn from step 3>` to your `.env` (local dev) or to the App Runner service's `RuntimeEnvironmentVariables` (redeploy `infra/apprunner-service.json`), and grant the App Runner instance role `bedrock-agentcore:InvokeAgentRuntime` (already included in `infra/apprunner-instance-permissions-policy.json` — fill in the runtime ARN's account/region).

`app/agent.py`'s fallback chain tries AgentCore Runtime first when `AGENTCORE_RUNTIME_ARN` is set, then falls back to the in-process Strands+Bedrock call, then the demo engine — so a misconfigured or unreachable AgentCore Runtime degrades gracefully rather than breaking the app.
