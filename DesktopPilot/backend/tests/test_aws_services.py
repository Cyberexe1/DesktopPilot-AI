"""
Test script — checks all AWS services needed by DesktopPilot AI.
Run from backend/ directory:  python tests/test_aws_services.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

REGION    = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "desktoppilot-audio")
MEM_TABLE = os.getenv("DYNAMODB_TABLE_MEMORY", "DesktopPilotMemory")
CMD_TABLE = os.getenv("DYNAMODB_TABLE_COMMANDS", "DesktopPilotCommands")
MODEL_ID  = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-opus-4-1-20250805-v1:0")

results = {}

def check(name, fn):
    print(f"  Testing {name}...", end=" ", flush=True)
    try:
        fn()
        print("✓ PASS")
        results[name] = True
    except Exception as e:
        print(f"✗ FAIL — {type(e).__name__}: {str(e)[:80]}")
        results[name] = False


# ── 1. AWS Credentials ────────────────────────────────────────────────────────
def check_credentials():
    sts = boto3.client("sts", region_name=REGION)
    identity = sts.get_caller_identity()
    # Don't print account ID or ARN for security

# ── 2. S3 Bucket ──────────────────────────────────────────────────────────────
def check_s3():
    s3 = boto3.client("s3", region_name=REGION)
    s3.head_bucket(Bucket=S3_BUCKET)

# ── 3. S3 Upload ──────────────────────────────────────────────────────────────
def check_s3_upload():
    s3 = boto3.client("s3", region_name=REGION)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key="tests/connection-test.txt",
        Body=b"DesktopPilot connection test",
        ContentType="text/plain",
    )
    # Clean up
    s3.delete_object(Bucket=S3_BUCKET, Key="tests/connection-test.txt")

# ── 4. DynamoDB Memory Table ──────────────────────────────────────────────────
def check_dynamo_memory():
    dynamo = boto3.client("dynamodb", region_name=REGION)
    dynamo.describe_table(TableName=MEM_TABLE)

# ── 5. DynamoDB Commands Table ────────────────────────────────────────────────
def check_dynamo_commands():
    dynamo = boto3.client("dynamodb", region_name=REGION)
    dynamo.describe_table(TableName=CMD_TABLE)

# ── 6. DynamoDB Read/Write ────────────────────────────────────────────────────
def check_dynamo_readwrite():
    dynamo = boto3.resource("dynamodb", region_name=REGION)
    table  = dynamo.Table(MEM_TABLE)
    # Write test item
    table.put_item(Item={"user_id": "_test_", "credits_remaining": 100})
    # Read it back
    resp = table.get_item(Key={"user_id": "_test_"})
    assert resp.get("Item", {}).get("user_id") == "_test_"
    # Clean up
    table.delete_item(Key={"user_id": "_test_"})

# ── 7. Amazon Transcribe ──────────────────────────────────────────────────────
def check_transcribe():
    tc = boto3.client("transcribe", region_name=REGION)
    # Just list jobs — proves permissions work
    tc.list_transcription_jobs(MaxResults=1)

# ── 8. Amazon Bedrock ─────────────────────────────────────────────────────────
def check_bedrock():
    import json
    client = boto3.client("bedrock-runtime", region_name=REGION)
    response = client.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 20,
            "messages": [{"role": "user", "content": "Say: ok"}]
        }),
        contentType="application/json",
        accept="application/json",
    )
    body = json.loads(response["body"].read())
    assert body["content"][0]["text"]


# ── Run all checks ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{'='*55}")
    print("  DesktopPilot AI — Full AWS Services Test")
    print(f"{'='*55}")
    print(f"  Region   : {REGION}")
    print(f"  S3 Bucket: {S3_BUCKET}")
    print(f"  DynamoDB : {MEM_TABLE}, {CMD_TABLE}")
    print(f"  Model    : {MODEL_ID}")
    print(f"{'='*55}\n")

    check("AWS Credentials",        check_credentials)
    check("S3 Bucket exists",       check_s3)
    check("S3 Upload/Delete",       check_s3_upload)
    check("DynamoDB Memory table",  check_dynamo_memory)
    check("DynamoDB Commands table",check_dynamo_commands)
    check("DynamoDB Read/Write",    check_dynamo_readwrite)
    check("Amazon Transcribe",      check_transcribe)
    check("Bedrock Claude (Haiku 4.5)",check_bedrock)

    passed = sum(results.values())
    total  = len(results)

    print(f"\n{'='*55}")
    print(f"  Results: {passed}/{total} passed")
    print(f"{'='*55}")

    if passed == total:
        print("  ✓ All services ready — DesktopPilot AI is fully configured\n")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"  ✗ Failed: {', '.join(failed)}")
        print("  Fix the failed services then re-run this script\n")

    sys.exit(0 if passed == total else 1)
