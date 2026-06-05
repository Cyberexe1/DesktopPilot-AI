"""
Prompt Enhancer — rewrites vague/short user commands into clear, actionable instructions.

Uses a fast Bedrock model (Llama 3 8B) to interpret ambiguous commands and produce
explicit step-by-step instructions that the main planner can easily convert to tools.

Examples:
  "open gmail in chrome"  →  "Open the browser and navigate to https://mail.google.com"
  "setup vite project"    →  "Create a new Vite React project called my-app on Desktop"
  "bluetooth"             →  "Open Bluetooth settings"
  "resume"                →  "Open my latest resume file"
"""

import json
import logging
import os
import re

import boto3

log = logging.getLogger(__name__)

REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# Use a fast model for enhancement — same model works fine for short rewrites
ENHANCER_MODEL_ID = os.getenv(
    "BEDROCK_ENHANCER_MODEL_ID",
    os.getenv("BEDROCK_MODEL_ID", "us.meta.llama3-3-70b-instruct-v1:0")
)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=REGION)
    return _client


# ── Commands that are already clear enough — skip enhancement ─────────────────

SKIP_PATTERNS = [
    # Greetings
    r"^(hello|hi|hey|good morning|good evening|good night|thank you|thanks|bye|goodbye|how are you)",
    # Already explicit tool commands
    r"^(open|close|kill|snap|minimize|maximize|switch to|mute|volume|brightness)",
    # System info
    r"^(battery|ram|cpu|ip|disk|how much|what's my)",
    # Knowledge questions
    r"^(what is|what are|explain|who is|why|how does|define|tell me about|who invented)",
    # Already has URL
    r"https?://",
]

# Commands that need enhancement — vague, short, or missing details
NEEDS_ENHANCEMENT_PATTERNS = [
    r"(in chrome|in browser|in firefox|in edge)",   # "open X in chrome"
    r"(setup|set up|create|scaffold|build).*(project|app|site|website)",  # project creation
    r"(prepare|launch|start).*(environment|dev|development)",  # dev workflows
    r"(copy|move|transfer).*(file|folder|drive)",  # file operations
    r"(send|draft|compose|write).*(email|mail|message)",  # communication
    r"(open.*drive|d drive|e drive|f drive).*(create|setup|make|folder)",  # drive + project ops
]

# Single words that map to settings or actions (not greetings)
SINGLE_WORD_ENHANCE = {
    "bluetooth", "wifi", "display", "sound", "updates", "storage",
    "accounts", "privacy", "network", "battery", "power", "mouse",
    "keyboard", "printer", "camera", "microphone",
}


ENHANCER_PROMPT = """You are a command clarifier for a Windows desktop AI agent called Cipher.

Your job: Take a vague or short user command and rewrite it as a CLEAR, EXPLICIT instruction.
Keep it as a single sentence. Do NOT add extra steps the user didn't ask for.

Rules:
1. If user says "open X in chrome/browser" → rewrite as "Open browser and navigate to [correct URL]"
2. If user says "setup/create [framework] project [name]" → rewrite clearly with framework and name
3. If user says a single word like "bluetooth" → rewrite as "Open Bluetooth settings"
4. If user says "open gmail" → "Open browser and navigate to https://mail.google.com"
5. If user says "copy X from A to B" → rewrite with full paths if possible
6. If user says "prepare my dev environment" → list what apps/servers to open
7. Keep it SHORT — one or two sentences max
8. Do NOT change the intent. Only CLARIFY it.
9. Return ONLY the rewritten command — no explanation, no quotes, no prefixes.

Common URL mappings:
- Gmail = https://mail.google.com
- YouTube = https://www.youtube.com
- GitHub = https://github.com
- Google = https://www.google.com
- LinkedIn = https://www.linkedin.com
- Google Docs = https://docs.google.com
- Google Drive = https://drive.google.com
- AWS Console = https://console.aws.amazon.com
- Stack Overflow = https://stackoverflow.com
- ChatGPT = https://chat.openai.com
- WhatsApp Web = https://web.whatsapp.com
- Twitter/X = https://x.com
- Netflix = https://www.netflix.com
- Reddit = https://www.reddit.com

Single-word to setting mappings:
- bluetooth = Open Bluetooth settings
- wifi = Open WiFi settings
- display = Open Display settings
- sound = Open Sound settings
- updates = Check for Windows updates

Examples:
Input: "gmail in chrome"
Output: Open browser and navigate to https://mail.google.com

Input: "setup a vite react project called dashboard"
Output: Create a new Vite React project called dashboard on Desktop

Input: "bluetooth"
Output: Open Bluetooth settings

Input: "copy resume to D drive"
Output: Copy the most recent resume file from Documents to D: drive

Input: "prepare my EduPulse development environment"
Output: Open the EduPulse project in VS Code, run the development server, and open localhost in browser

Input: "youtube in chrome"
Output: Open browser and navigate to https://www.youtube.com

Input: "send email to john about meeting"
Output: Compose an email to john with subject about a meeting

Input: "open d drive and create a folder name Vikas and setup a react vite project"
Output: Create a Vite React project called Vikas on D:/ drive

Input: "setup a django project called mysite on D drive"
Output: Create a Django project called mysite on D:/ drive

Input: "create a fastapi project in D:/Projects"
Output: Create a FastAPI project on D:/Projects drive

Now rewrite this command:
Input: """


def _should_enhance(command: str) -> bool:
    """Determine if a command needs enhancement or is already clear."""
    cmd = command.lower().strip()

    # HIGH PRIORITY: Check enhancement patterns FIRST — these always need enhancement
    for pattern in NEEDS_ENHANCEMENT_PATTERNS:
        if re.search(pattern, cmd):
            return True

    # Single-word commands that map to settings/actions
    if cmd in SINGLE_WORD_ENHANCE:
        return True

    # Skip if command matches clear patterns (greetings, explicit opens, questions)
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, cmd):
            return False

    # Short commands (< 3 words) that didn't match any pattern — likely need enhancement
    if len(cmd.split()) <= 2:
        return True

    return False


def _is_llama_model(model_id: str) -> bool:
    return "meta" in model_id.lower() or "llama" in model_id.lower()


def _is_nova_model(model_id: str) -> bool:
    return "nova" in model_id.lower() or "amazon" in model_id.lower()


def enhance_prompt(user_command: str) -> str:
    """
    Enhance a vague user command into a clear, actionable instruction.
    Returns the original command if enhancement isn't needed or fails.
    """
    if not _should_enhance(user_command):
        log.info(f"Prompt clear enough, skipping enhancement: {user_command}")
        return user_command

    log.info(f"Enhancing prompt: {user_command}")

    try:
        client = _get_client()
        full_prompt = ENHANCER_PROMPT + f'"{user_command}"\nOutput: '

        if _is_llama_model(ENHANCER_MODEL_ID):
            body = {
                "prompt": full_prompt,
                "max_gen_len": 150,
                "temperature": 0.01,
            }
        elif _is_nova_model(ENHANCER_MODEL_ID):
            body = {
                "schemaVersion": "messages-v1",
                "messages": [
                    {"role": "user", "content": [{"text": full_prompt}]}
                ],
                "inferenceConfig": {
                    "maxTokens": 150,
                    "temperature": 0.01,
                }
            }
        else:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 150,
                "messages": [{"role": "user", "content": full_prompt}],
            }

        response = client.invoke_model(
            modelId=ENHANCER_MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())

        # Extract text from response based on model type
        if "generation" in result:
            # Llama format
            enhanced = result["generation"].strip()
        elif "output" in result and "message" in result["output"]:
            # Amazon Nova format
            content = result["output"]["message"].get("content", [])
            enhanced = content[0].get("text", "").strip() if content else user_command
        elif "content" in result and isinstance(result["content"], list):
            # Anthropic format
            enhanced = result["content"][0]["text"].strip()
        else:
            enhanced = user_command

        # Clean up — remove quotes, "Output:" prefix, etc.
        enhanced = enhanced.strip('"\'')
        enhanced = re.sub(r'^(Output|Result|Rewritten|Enhanced):\s*', '', enhanced, flags=re.IGNORECASE)
        enhanced = enhanced.split('\n')[0].strip()  # Take only first line

        # Sanity check — enhanced shouldn't be empty or way too long
        if not enhanced or len(enhanced) > 500 or len(enhanced) < 3:
            log.warning(f"Enhancement produced bad result, using original: '{enhanced}'")
            return user_command

        log.info(f"Enhanced: '{user_command}' → '{enhanced}'")
        return enhanced

    except Exception as e:
        log.warning(f"Prompt enhancement failed ({type(e).__name__}: {e}), using original command")
        return user_command
