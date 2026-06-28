"""
Memory layer — Phase 2.
Reads/writes DynamoDB for cloud sync, falls back to SQLite when AWS unavailable.
"""

import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, EndpointResolutionError

from boto3.dynamodb.conditions import Key

from database.sqlite_manager import get_last_project, get_recent_commands

log = logging.getLogger(__name__)

REGION    = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
MEM_TABLE = os.getenv("DYNAMODB_TABLE_MEMORY",   "DesktopPilotMemory")
CMD_TABLE = os.getenv("DYNAMODB_TABLE_COMMANDS",  "DesktopPilotCommands")

_dynamo = None


def _get_dynamo():
    global _dynamo
    if _dynamo is None:
        _dynamo = boto3.resource("dynamodb", region_name=REGION)
    return _dynamo


# ── Context ───────────────────────────────────────────────────────────────────

def get_context(user_id: str = "default") -> dict:
    """
    Return memory context for the user.
    Tries DynamoDB first, falls back to local SQLite.
    """
    last_project    = get_last_project()
    recent_commands = [c["command"] for c in get_recent_commands(limit=5)]
    credits         = 100  # default

    try:
        table    = _get_dynamo().Table(MEM_TABLE)
        response = table.get_item(Key={"user_id": user_id})
        item     = response.get("Item", {})

        if item.get("last_project"):
            last_project = item["last_project"]

        credits = int(item.get("credits_remaining", 100))

        return {
            "last_project":     last_project,
            "recent_commands":  recent_commands,
            "credits_remaining": credits,
            "source":           "dynamodb",
        }

    except (ClientError, NoCredentialsError, EndpointResolutionError, Exception) as e:
        log.warning(f"DynamoDB unavailable, using local memory: {type(e).__name__}")
        return {
            "last_project":     last_project,
            "recent_commands":  recent_commands,
            "credits_remaining": credits,
            "source":           "local",
        }


# ── Command history ───────────────────────────────────────────────────────────

def get_commands(user_id: str = "default", limit: int = 25) -> list[dict]:
    """
    Return recent command history for the user.
    Tries DynamoDB (DesktopPilotCommands) first, falls back to local SQLite.
    """
    try:
        table    = _get_dynamo().Table(CMD_TABLE)
        response = table.query(
            KeyConditionExpression=Key("user_id").eq(user_id),
            ScanIndexForward=False,  # newest first
            Limit=limit,
        )
        items = response.get("Items", [])
        commands = [{
            "command":      i.get("command", ""),
            "intent":       i.get("intent", ""),
            "status":       i.get("status", ""),
            "timestamp":    i.get("timestamp", ""),
            "duration_ms":  int(i.get("duration_ms", 0)),
            "credits_used": int(i.get("credits_used", 0)),
        } for i in items]
        return commands

    except (ClientError, NoCredentialsError, EndpointResolutionError, Exception) as e:
        log.warning(f"DynamoDB unavailable for commands, using local: {type(e).__name__}")
        return [{
            "command":   c.get("command", ""),
            "intent":    "",
            "status":    "",
            "timestamp": c.get("timestamp", ""),
        } for c in get_recent_commands(limit=limit)]


# ── Save command ──────────────────────────────────────────────────────────────

def save_command_cloud(user_id: str, command: str, intent: str = "",
                       status: str = "completed", duration_ms: int = 0,
                       credits_used: int = 1):
    """Save a completed command to DynamoDB. Silently skips if unavailable."""
    try:
        table = _get_dynamo().Table(CMD_TABLE)
        table.put_item(Item={
            "user_id":      user_id,
            "timestamp":    datetime.now(timezone.utc).isoformat(),
            "command":      command,
            "intent":       intent,
            "status":       status,
            "duration_ms":  duration_ms,
            "credits_used": credits_used,
        })
        log.info(f"Command saved to DynamoDB: {command[:60]}")
    except (ClientError, NoCredentialsError, Exception) as e:
        log.warning(f"Could not save command to DynamoDB: {type(e).__name__}")


# ── Update last project ───────────────────────────────────────────────────────

def update_last_project(user_id: str, project: dict):
    """Update last used project in DynamoDB."""
    try:
        table = _get_dynamo().Table(MEM_TABLE)
        table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET last_project = :p, last_updated = :t",
            ExpressionAttributeValues={
                ":p": project,
                ":t": datetime.now(timezone.utc).isoformat(),
            }
        )
        log.info(f"Last project updated in DynamoDB: {project.get('name')}")
    except (ClientError, NoCredentialsError, Exception) as e:
        log.warning(f"Could not update last project in DynamoDB: {type(e).__name__}")


# ── Credits ───────────────────────────────────────────────────────────────────

def deduct_credits(user_id: str = "default", amount: int = 1) -> int:
    """
    Deduct credits from DynamoDB.
    Returns remaining balance, or -1 if DynamoDB unavailable (allow through).
    Raises ValueError if credits are insufficient.
    """
    try:
        table    = _get_dynamo().Table(MEM_TABLE)
        response = table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET credits_remaining = credits_remaining - :n",
            ConditionExpression="credits_remaining >= :n",
            ExpressionAttributeValues={":n": amount},
            ReturnValues="UPDATED_NEW",
        )
        remaining = int(response["Attributes"]["credits_remaining"])
        log.info(f"Credits deducted: {amount}, remaining: {remaining}")
        return remaining

    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ValueError("Insufficient credits. Please purchase more at desktoppilot.vercel.app/dashboard")
        log.warning(f"DynamoDB credits error: {e}")
        return -1  # Allow through when DynamoDB unavailable

    except (NoCredentialsError, Exception) as e:
        log.warning(f"Credits check skipped (DynamoDB unavailable): {type(e).__name__}")
        return -1  # Allow through


def get_credits(user_id: str = "default") -> int:
    """Return current credit balance. Returns 100 as default if unavailable."""
    try:
        table    = _get_dynamo().Table(MEM_TABLE)
        response = table.get_item(
            Key={"user_id": user_id},
            ProjectionExpression="credits_remaining"
        )
        item = response.get("Item", {})
        return int(item.get("credits_remaining", 100))
    except Exception:
        return 100


# ── Prompt enrichment ─────────────────────────────────────────────────────────

# Conversation history for multi-turn context (in-memory, resets on restart)
_conversation_history: list[dict] = []
MAX_HISTORY = 5  # Keep last 5 exchanges


def add_to_history(user_command: str, result: dict):
    """Store a command + result for multi-turn context."""
    _conversation_history.append({
        "command": user_command,
        "intent": result.get("intent", ""),
        "tasks": [t.get("tool", "") + "(" + str({k: v for k, v in t.items() if k != "tool"}) + ")"
                  for t in result.get("tasks", [])[:3]],
    })
    # Keep only recent history
    if len(_conversation_history) > MAX_HISTORY:
        _conversation_history.pop(0)


def get_history_context() -> str:
    """Get conversation history as context for the AI."""
    if not _conversation_history:
        return ""

    lines = ["Recent conversation (for context — user may refer to previous actions):"]
    for h in _conversation_history[-3:]:  # Last 3 only
        lines.append(f"  User: \"{h['command']}\" → {h['intent']} → {', '.join(h['tasks'][:2])}")
    return "\n".join(lines)


def enrich_prompt(user_command: str, user_id: str = "default") -> str:
    """Inject memory context + conversation history into the Bedrock prompt."""
    context = get_context(user_id)
    lines   = []

    if context["last_project"]:
        p = context["last_project"]
        lines.append(f"User's last project: {p.get('name')} at {p.get('path')}")

    # Add conversation history for multi-turn context
    history = get_history_context()
    if history:
        lines.append(history)

    memory_block = "\n".join(lines)
    if memory_block:
        return f"Background context (for reference only — do NOT repeat previous commands):\n{memory_block}\n\nCurrent command (do ONLY this): {user_command}"
    return f"Command: {user_command}"
