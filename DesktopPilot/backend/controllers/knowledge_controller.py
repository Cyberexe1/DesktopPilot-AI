"""
Knowledge Controller — answers questions using AI (Bedrock Llama).
Used when the user asks a knowledge question instead of giving a task command.
"""

import json
import logging
import os

import boto3

log = logging.getLogger(__name__)

REGION   = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")

bedrock = boto3.client("bedrock-runtime", region_name=REGION)


def answer_question(question: str) -> str:
    """
    Answer a knowledge question using Bedrock Llama.
    Returns a concise, spoken-friendly answer.
    """
    if not question:
        return "No question provided."

    prompt = f"""You are Cipher, a helpful AI assistant. Answer the following question concisely and clearly.

Rules:
- Keep your answer to 2-4 sentences maximum.
- Be factual and accurate.
- Speak naturally as if talking to someone (this will be read aloud).
- Do NOT use markdown, bullet points, or formatting.
- Do NOT say "Here's the answer" or "Let me explain". Just answer directly.

Question: {question}

Answer:"""

    try:
        if "meta" in MODEL_ID.lower() or "llama" in MODEL_ID.lower():
            body = {"prompt": prompt, "max_gen_len": 300, "temperature": 0.3}
        elif "nova" in MODEL_ID.lower() or "amazon" in MODEL_ID.lower():
            body = {
                "schemaVersion": "messages-v1",
                "messages": [
                    {"role": "user", "content": [{"text": prompt}]}
                ],
                "inferenceConfig": {
                    "maxTokens": 300,
                    "temperature": 0.3,
                }
            }
        else:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            }

        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())

        if "generation" in result:
            answer = result["generation"].strip()
        elif "output" in result and "message" in result["output"]:
            # Amazon Nova format
            content = result["output"]["message"].get("content", [])
            answer = content[0].get("text", "").strip() if content else "I'm not sure about that."
        elif "content" in result:
            answer = result["content"][0]["text"].strip()
        else:
            answer = "I'm not sure about that."

        # Clean up — remove any leftover prompt artifacts
        if answer.startswith("Answer:"):
            answer = answer[7:].strip()

        # Truncate if too long
        if len(answer) > 500:
            # Cut at last sentence within 500 chars
            cut = answer[:500].rfind('.')
            if cut > 100:
                answer = answer[:cut+1]
            else:
                answer = answer[:500] + "..."

        log.info(f"Knowledge answer: {answer[:80]}")
        return answer

    except Exception as e:
        log.error(f"Knowledge answer failed: {e}")
        return f"Sorry Sir, I couldn't find the answer right now."
