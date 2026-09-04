# CivicMate AI

Civic-assistance agent for reporting local public-service problems. Built with the [Strands Agents SDK](https://github.com/strands-agents/sdk-python) and Amazon Bedrock for the [Agents for Humans](https://agentsforhumans.devpost.com/) hackathon — Good Neighbor Agents track. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design.

Licensed under the [MIT License](LICENSE).

**Live demo:** http://54.236.69.4:8000 — running on EC2 with real DynamoDB, S3, Bedrock (Nova Lite) inference, and SES email delivery, not fallbacks. See "Deploy to AWS (EC2)" below for why EC2 rather than App Runner, and `ARCHITECTURE.md` section 19a for details. Magic-link sign-in emails send from `trichytoday60@gmail.com`; SES is still in sandbox mode, so delivery only works to recipient addresses also verified in SES (section 19b) — everything else logs the link server-side instead of failing.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit AWS_REGION / S3_BUCKET / SES_SENDER_EMAIL as needed
```

Configure AWS credentials (`aws configure`, or export `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`), set `SES_SENDER_EMAIL` in `.env` to an address you control, then provision everything:

```bash
python scripts/setup_aws.py
```

This creates the DynamoDB tables (complaints + magic-link tokens) and S3 bucket, and — if `SES_SENDER_EMAIL` is set — kicks off SES sender verification, which emails **you** a confirmation link. Click it before magic-link sign-in emails can actually send.

**Note:** SES accounts start in sandbox mode, which only allows sending to *also-verified* recipient addresses until AWS grants production access (request it via the SES console — same kind of approval wait as the Bedrock quota). Until then, `app/email_sender.py` logs the sign-in link server-side instead of emailing it whenever SES can't deliver, so sign-in still works — check `docker logs` / server output for the link.

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

4. Real Bedrock inference works out of the box once the instance role has `bedrock:InvokeModel` **and** `bedrock:InvokeModelWithResponseStream` (both are in `infra/apprunner-instance-permissions-policy.json` — the second one is easy to miss, since Strands' `BedrockModel` uses the streaming Converse API by default).

**Note on this account:** App Runner returned `SubscriptionRequiredException` on this particular AWS account (account-level service activation, not an IAM issue — confirmed via the read-only `apprunner:ListServices` call too) — see "Deploy to AWS (EC2)" below for the fallback path actually used for the live demo. The App Runner path above is untested end-to-end on a real account as a result, though the container itself is verified (see the Dockerfile testing notes in `ARCHITECTURE.md` section 16).

## Deploy to AWS (EC2)

Used for the live demo after App Runner turned out to be blocked at the account level on this particular AWS account. EC2 is the most universally-available AWS compute service, so it's a reasonable fallback when a newer managed service isn't yet activated.

1. Provision DynamoDB/S3 and push the app image to ECR (same as steps 1 above).
2. **Create the instance role** (ECR pull + Bedrock + DynamoDB + S3 + AgentCore-invoke, scoped to your specific resources — fill in `infra/ec2-instance-permissions-policy.json`'s placeholders first):

   ```bash
   aws iam create-role --role-name CivicMateEC2InstanceRole \
     --assume-role-policy-document file://infra/ec2-instance-trust-policy.json
   aws iam put-role-policy --role-name CivicMateEC2InstanceRole \
     --policy-name CivicMateEC2Permissions \
     --policy-document file://infra/ec2-instance-permissions-policy.json
   aws iam attach-role-policy --role-name CivicMateEC2InstanceRole \
     --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
   aws iam create-instance-profile --instance-profile-name CivicMateEC2InstanceProfile
   aws iam add-role-to-instance-profile --instance-profile-name CivicMateEC2InstanceProfile --role-name CivicMateEC2InstanceRole
   ```

3. **Security group** (port 8000 only — no SSH; use SSM Session Manager for shell access):

   ```bash
   VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query 'Vpcs[0].VpcId' --output text)
   SG_ID=$(aws ec2 create-security-group --group-name civicmate-app-sg --description "CivicMate: allow 8000" --vpc-id $VPC_ID --query GroupId --output text)
   aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 8000 --cidr 0.0.0.0/0
   ```

4. **Launch the instance.** Fill in `infra/ec2-user-data.template.sh`'s placeholders (including a fresh `openssl rand -hex 32` session secret), then:

   ```bash
   AMI_ID=$(aws ec2 describe-images --owners amazon \
     --filters "Name=name,Values=al2023-ami-2023*-x86_64" "Name=state,Values=available" \
     --query 'sort_by(Images, &CreationDate)[-1].ImageId' --output text)

   aws ec2 run-instances --image-id $AMI_ID --instance-type t3.small \
     --security-group-ids $SG_ID \
     --iam-instance-profile Name=CivicMateEC2InstanceProfile \
     --user-data file://infra/ec2-user-data.filled.sh \
     --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=civicmate-app}]'
   ```

   Get the public IP with `aws ec2 describe-instances --instance-ids <id> --query 'Reservations[0].Instances[0].PublicIpAddress'` — the app is live at `http://<that-ip>:8000` a minute or two later (user-data installs Docker and pulls the image on first boot).

5. **To redeploy after a code change:** rebuild/push the image, then `aws ssm send-command` with `AWS-RunShellScript` to `docker pull ...`, `docker stop civicmate`, `docker rm civicmate`, and re-run `docker run` — no SSH needed.

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
