"""
AI Planning Layer — Amazon Bedrock (Llama 3.3 70B / Claude).
Converts natural language into a structured JSON execution plan.
"""

import asyncio
import json
import logging
import os
import re

import boto3

from ai.memory import enrich_prompt

log = logging.getLogger(__name__)

REGION   = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.meta.llama3-3-70b-instruct-v1:0")

bedrock = boto3.client("bedrock-runtime", region_name=REGION)

SENSITIVE_TOOLS = {"run_terminal", "compose_email", "delete_file", "open_setting", "type_text", "press_key", "create_file", "write_to_file", "create_project"}

SYSTEM_PROMPT = """You are DesktopPilot AI, an autonomous Windows desktop agent.

Convert the user's natural language command into a structured JSON execution plan.

Available tools (use ONLY these exact names):
- open_application   params: name (string)
- open_project       params: project (string)
- run_terminal       params: command (string), project (string, optional)
- wait_for_server    params: url (string)
- open_browser       params: url (string)
- search_web         params: query (string)
- open_file          params: name (string)
- open_setting       params: name (string)  [wifi|bluetooth|display|sound|apps|updates]
- compose_email      params: to (string), subject (string), body (string)
- type_text          params: text (string) — types text into the currently active/focused window
- press_key          params: key (string) — presses a key like "enter", "ctrl+s", "tab", "alt+f4"
- create_file        params: filename (string), content (string), directory (string, optional — defaults to Desktop)
- write_to_file      params: filepath (string), content (string) — writes/overwrites content to an existing file
- create_project     params: name (string), framework (string: vite|nextjs|nodejs|python|html), directory (string, optional)
- read_screen        params: mode (string: "full" or "window") — captures screen and extracts all visible text using OCR
- analyze_screen     params: none — full screen analysis with text, forms, and table detection
- wait               params: seconds (number) — pause between steps (use when next step depends on previous)
- navigate           params: url (string) — navigate to a URL in the already-open browser
- click_element      params: x (number), y (number) — click at screen coordinates

Rules:
1. Return ONLY valid JSON. No explanation, no markdown, no code blocks.
2. For multi-step commands, include ALL steps in the correct order.
3. If the command is ambiguous, choose the most likely intent.
4. Use wait_for_server after run_terminal when starting a web server.
5. Only include tools that are directly requested. Do NOT add extra steps.
6. When asked to write/type something in an app, first open the app, then use type_text.
7. Use press_key for keyboard shortcuts like saving (ctrl+s) or new line (enter).
8. When asked to CREATE a file with content, use create_file. It auto-opens in the correct app (.txt→Notepad, .docx→Word, .pptx→PowerPoint, .html/.js/.py→VS Code).
9. When asked to write to an EXISTING file, use write_to_file.
10. When generating letter/email/document content, write DETAILED and COMPLETE text (at least 5-8 sentences). Include proper greeting, body paragraphs, and closing. Never write just one line.
11. When asked to create a project (vite, next.js, node.js, python), use create_project with the correct framework name.
12. For multi-step browser tasks, use wait between steps that depend on page loading (e.g., open_browser then wait then type_text).
13. The system auto-waits between steps, but add explicit wait(seconds) if a step needs extra time (e.g., waiting for a heavy page to load).

Output format:
{
  "intent": "brief description of what the user wants",
  "tasks": [
    {"tool": "tool_name", "param1": "value1", ...}
  ]
}"""


def _is_llama_model() -> bool:
    return "meta" in MODEL_ID.lower() or "llama" in MODEL_ID.lower()


async def generate_plan(user_command: str, user_id: str = "default") -> dict:
    """Call Bedrock and return a parsed plan dict."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _plan_sync, user_command, user_id)


def _plan_sync(user_command: str, user_id: str) -> dict:
    enriched = enrich_prompt(user_command, user_id)
    full_prompt = f"{SYSTEM_PROMPT}\n\n{enriched}"

    log.info(f"Calling Bedrock ({MODEL_ID}) for: {user_command}")

    body = _build_request_body(full_prompt)

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )

    result = json.loads(response["body"].read())
    plan_text = _extract_text(result)
    log.info(f"Bedrock response: {plan_text[:200]}")

    plan = _parse_plan(plan_text)
    plan["requires_approval"] = _needs_approval(plan)
    return plan


def _build_request_body(prompt: str) -> dict:
    """Build request body based on model type."""
    if _is_llama_model():
        return {"prompt": prompt, "max_gen_len": 1024, "temperature": 0.1}
    else:
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }


def _extract_text(result: dict) -> str:
    """Extract generated text from model response."""
    if "generation" in result:
        return result["generation"].strip()
    if "content" in result and isinstance(result["content"], list):
        return result["content"][0]["text"].strip()
    return json.dumps(result)


def _parse_plan(text: str) -> dict:
    """Extract JSON from model response."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r'\{[^{}]*"tasks"\s*:\s*\[.*?\]\s*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    log.warning(f"Could not parse response as JSON: {text[:100]}")
    return {"intent": "unknown", "tasks": []}


def _needs_approval(plan: dict) -> bool:
    return any(
        task.get("tool") in SENSITIVE_TOOLS
        for task in plan.get("tasks", [])
    )
