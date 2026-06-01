"""
Test script — verifies Claude Opus 4.1 on Amazon Bedrock.
Supports both IAM credentials and Bedrock long-term API key.
Run from backend/ directory:  python tests/test_bedrock.py
"""

import json
import os
import sys
import urllib.request
import urllib.error

from dotenv import load_dotenv
load_dotenv()

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

REGION        = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
MODEL_ID      = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-opus-4-1-20250805-v1:0")
BEDROCK_KEY   = os.getenv("AWS_BEARER_TOKEN_BEDROCK")

PAYLOAD = {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 50,
    "messages": [
        {"role": "user", "content": 'Reply with exactly: {"status":"ok"}'}
    ]
}

def print_header():
    print(f"\n{'='*55}")
    print("  DesktopPilot AI — Bedrock Connection Test")
    print(f"{'='*55}")
    print(f"  Region   : {REGION}")
    print(f"  Model ID : {MODEL_ID}")
    print(f"  Auth     : {'Bedrock API Key' if BEDROCK_KEY else 'IAM Credentials'}")
    print(f"{'='*55}\n")


def test_with_api_key():
    """Test using Bedrock long-term API key (bearer token)."""
    print("  Using Bedrock long-term API key...")
    url     = f"https://bedrock-runtime.{REGION}.amazonaws.com/model/{MODEL_ID}/invoke"
    payload = json.dumps(PAYLOAD).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Accept":        "application/json",
            "Authorization": f"Bearer {BEDROCK_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            text   = result["content"][0]["text"].strip()
            tokens = result.get("usage", {})
            print(f"  ✓ Response     : {text}")
            print(f"  ✓ Input tokens : {tokens.get('input_tokens', 'N/A')}")
            print(f"  ✓ Output tokens: {tokens.get('output_tokens', 'N/A')}")
            print(f"\n  RESULT: PASS — Bedrock API key is working\n")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"\n  ✗ HTTP {e.code}: {body[:200]}")
        if e.code == 401:
            print("\n  FIX: API key is invalid or expired.")
            print("  → Go to Bedrock Console → API keys → Create new long-term key")
        elif e.code == 403:
            print("\n  FIX: API key doesn't have access to this model.")
            print("  → Go to Bedrock Console → Model catalog → Enable Claude Opus 4.1")
        print(f"\n  RESULT: FAIL\n")
        return False
    except Exception as e:
        print(f"\n  ✗ Error: {type(e).__name__}: {e}")
        print(f"\n  RESULT: FAIL\n")
        return False


def test_with_iam():
    """Test using IAM credentials (standard boto3)."""
    print("  Using IAM credentials (boto3)...")
    client = boto3.client("bedrock-runtime", region_name=REGION)

    try:
        response = client.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(PAYLOAD),
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        text   = result["content"][0]["text"].strip()
        tokens = result.get("usage", {})
        print(f"  ✓ Response     : {text}")
        print(f"  ✓ Input tokens : {tokens.get('input_tokens', 'N/A')}")
        print(f"  ✓ Output tokens: {tokens.get('output_tokens', 'N/A')}")
        print(f"\n  RESULT: PASS — IAM + Bedrock is working\n")
        return True

    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg  = e.response["Error"]["Message"]
        print(f"\n  ✗ {code}: {msg[:150]}")

        if "INVALID_PAYMENT_INSTRUMENT" in msg:
            print("\n  FIX: AWS Marketplace needs a Visa/Mastercard card on file.")
            print("  UPI autopay is NOT accepted by AWS Marketplace.")
            print("  → Add a Visa/Mastercard debit card at:")
            print("    https://console.aws.amazon.com/billing/home#/paymentmethods")
            print("\n  ALTERNATIVE: Use a Bedrock long-term API key instead:")
            print("  → Bedrock Console → API keys → Create long-term key")
            print("  → Add to .env:  AWS_BEARER_TOKEN_BEDROCK=bedrock-your-key")
        elif "ResourceNotFoundException" in code:
            print("\n  FIX: Model not enabled.")
            print("  → Bedrock Console → Model catalog → Enable Claude Opus 4.1")
        elif "AccessDeniedException" in code:
            print("\n  FIX: IAM user missing AmazonBedrockFullAccess policy.")

        print(f"\n  RESULT: FAIL\n")
        return False

    except NoCredentialsError:
        print("\n  ✗ No AWS credentials in .env")
        print(f"\n  RESULT: FAIL\n")
        return False


if __name__ == "__main__":
    print_header()
    if BEDROCK_KEY:
        ok = test_with_api_key()
    else:
        ok = test_with_iam()
        if not ok:
            print("  TIP: You can bypass the payment issue by using a Bedrock API key.")
            print("  → Bedrock Console → API keys → Create long-term key")
            print("  → Add to .env:  AWS_BEARER_TOKEN_BEDROCK=bedrock-your-key-here\n")
    sys.exit(0 if ok else 1)
