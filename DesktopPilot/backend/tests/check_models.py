"""Quick check: list all active Anthropic models and try invoking one."""
import boto3
import json
import os
from dotenv import load_dotenv
load_dotenv()

REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
client = boto3.client("bedrock", region_name=REGION)
runtime = boto3.client("bedrock-runtime", region_name=REGION)

# List active models
r = client.list_foundation_models(byProvider="Anthropic")
active = [m for m in r["modelSummaries"] if m.get("modelLifecycle", {}).get("status") == "ACTIVE"]

print(f"\nActive Anthropic models ({len(active)}):")
for m in active:
    print(f"  {m['modelId']}")

# Try invoking the cheapest/smallest active model first
test_models = [
    "us.amazon.nova-pro-v1:0",
    "us.amazon.nova-lite-v1:0",
]

payload = json.dumps({
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 10,
    "messages": [{"role": "user", "content": "Say hi"}]
})

print("\nTrying to invoke models:")
for model_id in test_models:
    print(f"\n  Trying: {model_id}...", end=" ")
    try:
        resp = runtime.invoke_model(
            modelId=model_id,
            body=payload,
            contentType="application/json",
            accept="application/json",
        )
        body = json.loads(resp["body"].read())
        text = body["content"][0]["text"]
        print(f"SUCCESS -> {text}")
        break
    except Exception as e:
        err_msg = str(e)[:120]
        print(f"FAILED -> {err_msg}")
