# DesktopPilot AI — Phase 3: AWS Cloud + Production Build

> **Prerequisite:** Phase 1 and Phase 2 complete — Playwright working, DynamoDB memory wired, credits system active, WebSocket streaming live.
>
> **Goal:** Move the full pipeline to AWS (Lambda + Step Functions), create DynamoDB tables, build the `.exe` installer, deploy to Vercel with a real download URL, and set up CloudWatch monitoring.

---

## Phase 3 Scope

| Area | What Gets Built |
|---|---|
| DynamoDB Tables | Create DesktopPilotMemory + DesktopPilotCommands via AWS CLI |
| Lambda Functions | voice-handler, planner-handler, memory-handler, executor-handler |
| Step Functions | Full pipeline state machine with approval wait token |
| S3 Audio Pipeline | Electron uploads audio → S3 → Lambda triggers Transcribe |
| CloudWatch | Structured logs + custom metrics dashboard |
| IAM Roles | Least-privilege policies for all services |
| electron-builder | Build `.exe` NSIS installer, upload to S3 |
| Vercel Production | Set `VITE_DOWNLOAD_URL` to S3 `.exe` URL, deploy |
| Error Handling | Retry logic, dead letter queues, graceful fallbacks |

---

## AWS Architecture

```
Electron App (user's PC)
    │
    │  1. Upload audio blob
    ▼
Amazon S3 (desktoppilot-audio)
    │
    │  2. S3 event → invoke Lambda
    ▼
Lambda: voice-handler
    │  3. Start Transcribe job, poll, return transcript
    ▼
Amazon Transcribe
    │  4. Transcript text
    ▼
Lambda: planner-handler
    │  5. Invoke Bedrock Claude 3 Sonnet
    ▼
Amazon Bedrock
    │  6. JSON execution plan
    ▼
AWS Step Functions
    │  7. Orchestrate pipeline
    ├──→ [requires_approval=true] → WaitForApproval (task token)
    │         │  User approves in Electron app
    │         ▼
    └──→ Lambda: executor-handler
              │  8. POST plan to local FastAPI
              ▼
         FastAPI :8000 (local)
              │  9. Execute on desktop
              ▼
         Lambda: memory-handler
              │  10. Save to DynamoDB
              ▼
         Amazon DynamoDB
              │
              ▼
         Amazon CloudWatch (logs + metrics)
```

---

## Step 1 — Create DynamoDB Tables

```bash
# Memory table (user preferences + last project)
aws dynamodb create-table \
  --table-name DesktopPilotMemory \
  --attribute-definitions \
    AttributeName=user_id,AttributeType=S \
  --key-schema \
    AttributeName=user_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1

# Commands table (full history)
aws dynamodb create-table \
  --table-name DesktopPilotCommands \
  --attribute-definitions \
    AttributeName=user_id,AttributeType=S \
    AttributeName=timestamp,AttributeType=S \
  --key-schema \
    AttributeName=user_id,KeyType=HASH \
    AttributeName=timestamp,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1

# Seed default user with 100 credits
aws dynamodb put-item \
  --table-name DesktopPilotMemory \
  --item '{
    "user_id":          {"S": "default"},
    "credits_remaining":{"N": "100"},
    "last_updated":     {"S": "2025-01-01T00:00:00Z"}
  }' \
  --region us-east-1
```

---

## Step 2 — IAM Role

Create `DesktopPilotLambdaRole` with this policy:

`aws/iam/lambda-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Transcribe",
      "Effect": "Allow",
      "Action": ["transcribe:StartTranscriptionJob", "transcribe:GetTranscriptionJob"],
      "Resource": "*"
    },
    {
      "Sid": "Bedrock",
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel"],
      "Resource": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
    },
    {
      "Sid": "DynamoDB",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem", "dynamodb:PutItem",
        "dynamodb:UpdateItem", "dynamodb:Query"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:*:table/DesktopPilotMemory",
        "arn:aws:dynamodb:us-east-1:*:table/DesktopPilotCommands"
      ]
    },
    {
      "Sid": "S3",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::desktoppilot-audio/*"
    },
    {
      "Sid": "StepFunctions",
      "Effect": "Allow",
      "Action": ["states:StartExecution", "states:SendTaskSuccess", "states:SendTaskFailure"],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatch",
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents",
                 "cloudwatch:PutMetricData"],
      "Resource": "*"
    }
  ]
}
```

```bash
# Create role
aws iam create-role \
  --role-name DesktopPilotLambdaRole \
  --assume-role-policy-document file://aws/iam/trust-policy.json

# Attach policy
aws iam put-role-policy \
  --role-name DesktopPilotLambdaRole \
  --policy-name DesktopPilotPolicy \
  --policy-document file://aws/iam/lambda-policy.json
```

`aws/iam/trust-policy.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": ["lambda.amazonaws.com", "states.amazonaws.com"]},
    "Action": "sts:AssumeRole"
  }]
}
```

---

## Step 3 — Lambda Functions

### Lambda 1: voice-handler

`aws/lambda/voice_handler/handler.py`:

```python
import boto3, uuid, json, time, urllib.request, logging

log        = logging.getLogger()
log.setLevel(logging.INFO)
transcribe = boto3.client("transcribe")

def lambda_handler(event, context):
    audio_uri = event["audio_s3_uri"]
    job_name  = f"dp-{uuid.uuid4().hex[:10]}"

    log.info(json.dumps({"event": "transcribe_start", "job": job_name, "uri": audio_uri}))

    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": audio_uri},
        MediaFormat="wav",
        LanguageCode="en-US",
    )

    for attempt in range(30):
        time.sleep(2)
        job    = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        status = job["TranscriptionJob"]["TranscriptionJobStatus"]

        if status == "COMPLETED":
            uri = job["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
            with urllib.request.urlopen(uri) as f:
                data = json.loads(f.read())
            text = data["results"]["transcripts"][0]["transcript"]
            log.info(json.dumps({"event": "transcribe_complete", "text": text[:100]}))
            return {"transcript": text, "job_name": job_name}

        if status == "FAILED":
            reason = job["TranscriptionJob"].get("FailureReason", "Unknown")
            log.error(json.dumps({"event": "transcribe_failed", "reason": reason}))
            raise RuntimeError(f"Transcription failed: {reason}")

    raise TimeoutError("Transcription timed out after 60 seconds")
```

### Lambda 2: planner-handler

`aws/lambda/planner_handler/handler.py`:

```python
import boto3, json, re, logging, os

log     = logging.getLogger()
log.setLevel(logging.INFO)
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")

SENSITIVE_TOOLS = {"run_terminal", "compose_email", "delete_file", "open_setting"}

SYSTEM_PROMPT = """You are DesktopPilot AI, an autonomous Windows desktop agent.

Convert the user's natural language command into a structured JSON execution plan.

Available tools (use ONLY these exact names):
- open_application   params: name
- open_project       params: project
- run_terminal       params: command, project (optional)
- wait_for_server    params: url
- open_browser       params: url
- search_web         params: query
- open_file          params: name
- open_setting       params: name  [wifi|bluetooth|display|sound|apps|updates]
- compose_email      params: to, subject, body

Rules:
1. Return ONLY valid JSON. No explanation, no markdown.
2. Include ALL steps for multi-step commands in order.
3. Use wait_for_server after run_terminal when starting a web server.

Output format:
{"intent": "...", "tasks": [{"tool": "...", "param": "value"}]}"""


def lambda_handler(event, context):
    transcript     = event["transcript"]
    memory_context = event.get("memory_context", "")

    prompt = f"{SYSTEM_PROMPT}\n\nContext:\n{memory_context}\n\nCommand: {transcript}"

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}]
    }

    log.info(json.dumps({"event": "bedrock_invoke", "command": transcript[:100]}))

    response  = bedrock.invoke_model(
        modelId=MODEL_ID, body=json.dumps(body),
        contentType="application/json", accept="application/json"
    )
    result    = json.loads(response["body"].read())
    plan_text = result["content"][0]["text"].strip()

    plan = _parse_plan(plan_text)
    plan["requires_approval"] = any(
        t.get("tool") in SENSITIVE_TOOLS for t in plan.get("tasks", [])
    )

    log.info(json.dumps({"event": "plan_generated", "tasks": len(plan.get("tasks", []))}))
    return {"plan": plan, "transcript": transcript}


def _parse_plan(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {"intent": "unknown", "tasks": []}
```

### Lambda 3: memory-handler

`aws/lambda/memory_handler/handler.py`:

```python
import boto3, json, logging, os
from datetime import datetime, timezone

log      = logging.getLogger()
log.setLevel(logging.INFO)
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

MEM_TABLE = os.environ.get("DYNAMODB_TABLE_MEMORY",   "DesktopPilotMemory")
CMD_TABLE = os.environ.get("DYNAMODB_TABLE_COMMANDS",  "DesktopPilotCommands")


def lambda_handler(event, context):
    action  = event.get("action")
    user_id = event.get("user_id", "default")

    log.info(json.dumps({"event": "memory_action", "action": action, "user_id": user_id}))

    if action == "get":
        table    = dynamodb.Table(MEM_TABLE)
        response = table.get_item(Key={"user_id": user_id})
        return response.get("Item", {"user_id": user_id, "credits_remaining": 100})

    elif action == "save_command":
        table = dynamodb.Table(CMD_TABLE)
        table.put_item(Item={
            "user_id":      user_id,
            "timestamp":    datetime.now(timezone.utc).isoformat(),
            "command":      event.get("command", ""),
            "intent":       event.get("intent", ""),
            "status":       event.get("status", "completed"),
            "duration_ms":  event.get("duration_ms", 0),
            "credits_used": event.get("credits_used", 1),
        })
        return {"status": "saved"}

    elif action == "save_project":
        table = dynamodb.Table(MEM_TABLE)
        table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET last_project = :p, last_updated = :t",
            ExpressionAttributeValues={
                ":p": event.get("project"),
                ":t": datetime.now(timezone.utc).isoformat(),
            }
        )
        return {"status": "saved"}

    elif action == "deduct_credits":
        table = dynamodb.Table(MEM_TABLE)
        try:
            response = table.update_item(
                Key={"user_id": user_id},
                UpdateExpression="SET credits_remaining = credits_remaining - :n",
                ConditionExpression="credits_remaining >= :n",
                ExpressionAttributeValues={":n": event.get("amount", 1)},
                ReturnValues="UPDATED_NEW",
            )
            return {"credits_remaining": int(response["Attributes"]["credits_remaining"])}
        except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
            return {"error": "insufficient_credits", "credits_remaining": 0}

    return {"error": f"Unknown action: {action}"}
```

### Lambda 4: executor-handler

`aws/lambda/executor_handler/handler.py`:

```python
import json, logging, urllib.request, urllib.error, os

log = logging.getLogger()
log.setLevel(logging.INFO)

# The local FastAPI agent URL — set via environment variable
# In production this would be a fixed IP or ngrok tunnel
AGENT_URL = os.environ.get("LOCAL_AGENT_URL", "http://localhost:8000")


def lambda_handler(event, context):
    plan = event.get("plan", {})

    log.info(json.dumps({"event": "execute_start", "tasks": len(plan.get("tasks", []))}))

    payload = json.dumps({"plan": plan}).encode()
    req     = urllib.request.Request(
        f"{AGENT_URL}/execute",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            log.info(json.dumps({"event": "execute_complete", "result": result}))
            return result
    except urllib.error.URLError as e:
        log.error(json.dumps({"event": "execute_failed", "error": str(e)}))
        raise RuntimeError(f"Could not reach local agent: {e}")
```

---

## Step 4 — Step Functions State Machine

`aws/stepfunctions/workflow.json`:

```json
{
  "Comment": "DesktopPilot AI — Full Execution Pipeline",
  "StartAt": "TranscribeVoice",
  "States": {
    "TranscribeVoice": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:ACCOUNT:function:dp-voice-handler",
      "ResultPath": "$.voice_result",
      "Next": "FetchMemory",
      "Retry": [{"ErrorEquals": ["States.TaskFailed"], "MaxAttempts": 2, "IntervalSeconds": 3}],
      "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "HandleError", "ResultPath": "$.error"}]
    },
    "FetchMemory": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:ACCOUNT:function:dp-memory-handler",
      "Parameters": {"action": "get", "user_id.$": "$.user_id"},
      "ResultPath": "$.memory",
      "Next": "GeneratePlan"
    },
    "GeneratePlan": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:ACCOUNT:function:dp-planner-handler",
      "Parameters": {
        "transcript.$":     "$.voice_result.transcript",
        "memory_context.$": "$.memory"
      },
      "ResultPath": "$.plan_result",
      "Next": "CheckApproval",
      "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "HandleError", "ResultPath": "$.error"}]
    },
    "CheckApproval": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.plan_result.plan.requires_approval",
          "BooleanEquals": true,
          "Next": "WaitForApproval"
        }
      ],
      "Default": "ExecutePlan"
    },
    "WaitForApproval": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke.waitForTaskToken",
      "Parameters": {
        "FunctionName": "dp-approval-notifier",
        "Payload": {
          "plan.$":       "$.plan_result.plan",
          "taskToken.$":  "$$.Task.Token",
          "user_id.$":    "$.user_id"
        }
      },
      "HeartbeatSeconds": 300,
      "Next": "ExecutePlan",
      "Catch": [{"ErrorEquals": ["States.HeartbeatTimeout"], "Next": "HandleError"}]
    },
    "ExecutePlan": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:ACCOUNT:function:dp-executor-handler",
      "Parameters": {"plan.$": "$.plan_result.plan"},
      "ResultPath": "$.exec_result",
      "Next": "SaveMemory",
      "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "HandleError", "ResultPath": "$.error"}]
    },
    "SaveMemory": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:ACCOUNT:function:dp-memory-handler",
      "Parameters": {
        "action":       "save_command",
        "user_id.$":    "$.user_id",
        "command.$":    "$.voice_result.transcript",
        "intent.$":     "$.plan_result.plan.intent",
        "status":       "completed",
        "credits_used": 1
      },
      "Next": "Done"
    },
    "Done": {
      "Type": "Succeed"
    },
    "HandleError": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:ACCOUNT:function:dp-memory-handler",
      "Parameters": {
        "action":    "save_command",
        "user_id.$": "$.user_id",
        "status":    "failed"
      },
      "Next": "Fail"
    },
    "Fail": {
      "Type": "Fail",
      "Error": "PipelineError",
      "Cause": "DesktopPilot pipeline failed"
    }
  }
}
```

Deploy:
```bash
aws stepfunctions create-state-machine \
  --name DesktopPilotWorkflow \
  --definition file://aws/stepfunctions/workflow.json \
  --role-arn arn:aws:iam::ACCOUNT:role/DesktopPilotLambdaRole \
  --region us-east-1
```

---

## Step 5 — S3 Audio Upload from Electron

Update `electron-app/electron/main.js` to upload audio to S3 before calling the pipeline:

```javascript
const { S3Client, PutObjectCommand } = require('@aws-sdk/client-s3')

const s3 = new S3Client({ region: process.env.AWS_DEFAULT_REGION || 'us-east-1' })

async function uploadAudioToS3(audioBuffer) {
  const key = `audio/${Date.now()}-${require('crypto').randomBytes(4).toString('hex')}.wav`

  await s3.send(new PutObjectCommand({
    Bucket:      process.env.S3_BUCKET_NAME || 'desktoppilot-audio',
    Key:         key,
    Body:        audioBuffer,
    ContentType: 'audio/wav',
  }))

  return `s3://${process.env.S3_BUCKET_NAME}/${key}`
}
```

Add `@aws-sdk/client-s3` to `electron-app/package.json` dependencies.

---

## Step 6 — CloudWatch Logging

Add a CloudWatch metrics helper used by all Lambda functions:

`aws/lambda/shared/metrics.py`:

```python
import boto3, json, logging, os
from datetime import datetime, timezone

log = logging.getLogger()
cw  = boto3.client("cloudwatch", region_name="us-east-1")

NAMESPACE = "DesktopPilotAI"

def put_metric(name: str, value: float, unit: str = "Count"):
    try:
        cw.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[{
                "MetricName": name,
                "Value":      value,
                "Unit":       unit,
                "Timestamp":  datetime.now(timezone.utc),
            }]
        )
    except Exception as e:
        log.warning(f"CloudWatch metric failed: {e}")

# Usage in Lambda handlers:
# put_metric("CommandsProcessed", 1)
# put_metric("PlanGenerationLatency", elapsed_ms, "Milliseconds")
# put_metric("ExecutionSuccess", 1)
# put_metric("ExecutionFailure", 1)
# put_metric("CreditsDeducted", 1)
```

### CloudWatch Dashboard Metrics

| Metric | Unit | Description |
|---|---|---|
| `CommandsProcessed` | Count | Total voice commands handled |
| `PlanGenerationLatency` | Milliseconds | Bedrock response time |
| `ExecutionSuccess` | Count | Plans completed successfully |
| `ExecutionFailure` | Count | Plans that failed |
| `ApprovalRequired` | Count | Plans needing user approval |
| `CreditsDeducted` | Count | Credits consumed |

---

## Step 7 — Build .exe Installer

### Configure electron-builder

`electron-app/package.json` build section is already configured. Run:

```bash
cd DesktopPilot/electron-app
npm run build:win
```

This produces `dist-electron/DesktopPilot AI Setup 1.0.0.exe`.

### Upload to S3

```bash
aws s3 cp "dist-electron/DesktopPilot AI Setup 1.0.0.exe" \
  s3://desktoppilot-audio/releases/DesktopPilot-Setup.exe \
  --acl public-read \
  --region us-east-1
```

The public URL will be:
```
https://desktoppilot-audio.s3.amazonaws.com/releases/DesktopPilot-Setup.exe
```

---

## Step 8 — Vercel Production Deployment

Set environment variables in Vercel dashboard or `.env.production`:

```env
VITE_API_URL=http://localhost:8000
VITE_DOWNLOAD_URL=https://desktoppilot-audio.s3.amazonaws.com/releases/DesktopPilot-Setup.exe
```

Deploy:
```bash
cd DesktopPilot/web
npx vercel --prod
```

The landing page download button now points to the real `.exe` on S3.

---

## Phase 3 Deliverables Checklist

### DynamoDB
- [ ] `DesktopPilotMemory` table created with `user_id` PK
- [ ] `DesktopPilotCommands` table created with `user_id` PK + `timestamp` SK
- [ ] Default user seeded with 100 credits
- [ ] Web dashboard history tab shows real DynamoDB data

### Lambda
- [ ] `dp-voice-handler` deployed and tested with a sample S3 audio URI
- [ ] `dp-planner-handler` deployed and returns valid JSON plan
- [ ] `dp-memory-handler` deployed — get/save_command/save_project/deduct_credits all work
- [ ] `dp-executor-handler` deployed and can reach local FastAPI

### Step Functions
- [ ] State machine deployed and visible in AWS console
- [ ] Full pipeline executes end-to-end from audio URI to execution result
- [ ] Approval wait token works — Electron app sends `SendTaskSuccess`
- [ ] Error state saves failed command to DynamoDB

### S3 + Audio Pipeline
- [ ] S3 bucket `desktoppilot-audio` exists with correct CORS policy
- [ ] Electron uploads audio to S3 before calling pipeline
- [ ] Lambda voice-handler reads from S3 URI successfully

### CloudWatch
- [ ] All Lambda functions log structured JSON
- [ ] Custom metrics visible in CloudWatch console
- [ ] CloudWatch dashboard created with 6 metric widgets

### Production Build
- [ ] `npm run build:win` produces `.exe` without errors
- [ ] Installer runs on a clean Windows machine
- [ ] FastAPI backend bundled with installer (or setup instructions clear)
- [ ] `.exe` uploaded to S3 with public-read ACL

### Vercel
- [ ] `VITE_DOWNLOAD_URL` set to S3 `.exe` URL
- [ ] Landing page download button downloads the real installer
- [ ] Web dashboard credits tab shows real DynamoDB balance
- [ ] Web dashboard history tab shows real command history

---

## Hackathon Demo Script

### Demo 1 — Full Developer Workflow (2 minutes)

> *"Prepare my EduPulse development environment."*

```
1. User clicks mic in Electron app
2. Audio recorded → uploaded to S3
3. Lambda voice-handler → Transcribe → "Prepare my EduPulse development environment"
4. Lambda planner-handler → Bedrock → JSON plan (5 steps)
5. Step Functions: requires_approval=true → WaitForApproval
6. Approval gate shown in Electron app
7. User clicks Approve
8. Step Functions resumes → executor-handler → local FastAPI
9. open_project(EduPulse) → VS Code opens
10. run_terminal(python manage.py runserver) → CMD opens
11. wait_for_server(localhost:8000) → polls until ready
12. open_browser(localhost:8000) → Chrome opens
13. DynamoDB saves command + deducts 1 credit
14. CloudWatch logs execution
15. Windows toast: "Done — 4/4 steps completed"
```

### Demo 2 — Context Memory (30 seconds)

> *"Open my project."*

```
1. Bedrock prompt enriched with: "User's last project: EduPulse at D:/Projects/EduPulse"
2. Plan: open_project(EduPulse) — no clarification needed
3. VS Code opens EduPulse automatically
```

### Demo 3 — Email Automation (1 minute)

> *"Open Gmail and draft a project status update to the team."*

```
1. Plan: compose_email(to="team@...", subject="Project Status Update")
2. requires_approval=true → approval gate shown
3. User approves
4. Playwright opens Gmail → clicks Compose → fills fields
5. User reviews and sends manually
```

### Demo 4 — Web Dashboard (30 seconds)

```
1. Open desktoppilot.vercel.app
2. Show landing page with download button
3. Navigate to /dashboard
4. Show credits balance (real from DynamoDB)
5. Show command history (real from DynamoDB)
6. Show pricing plans
```

---

## Future Enhancements (Post-Hackathon)

| Feature | Description | Effort |
|---|---|---|
| Android Control | ADB-based Android device automation | High |
| Cross-Platform | macOS + Linux desktop controllers | High |
| WhatsApp Automation | Send messages via WhatsApp Web + Playwright | Medium |
| Calendar Integration | Google Calendar API — create/read events | Medium |
| Email Summarization | Bedrock summarizes inbox on command | Low |
| AI Workflow Recommendations | Suggest workflows based on usage patterns | Medium |
| Multi-Device Sync | One DynamoDB account, multiple machines | Medium |
| Voice Profiles | Per-user voice recognition + preferences | High |
| Stripe Billing | Real payment processing for credits | Medium |
| Team Accounts | Shared credits pool, team command history | High |

---

## Final Stack Summary

| Component | Technology | Status |
|---|---|---|
| Vercel Website | React 18 + Vite + JSX | ✅ Phase 1 |
| Desktop App | Electron 31 + React + JSX | ✅ Phase 1 |
| Local Backend | Python 3.11 + FastAPI | ✅ Phase 1 |
| Voice Input | Amazon Transcribe | ✅ Phase 1 |
| AI Planning | Amazon Bedrock (Claude 3 Sonnet) | ✅ Phase 1 |
| Browser Automation | Playwright | Phase 2 |
| File Watcher | Watchdog | Phase 2 |
| Cloud Memory | Amazon DynamoDB | Phase 2/3 |
| Credits System | DynamoDB + FastAPI | Phase 2/3 |
| Orchestration | AWS Step Functions | Phase 3 |
| Serverless | AWS Lambda (4 functions) | Phase 3 |
| Monitoring | Amazon CloudWatch | Phase 3 |
| File Storage | Amazon S3 | Phase 3 |
| Installer | electron-builder NSIS .exe | Phase 3 |
