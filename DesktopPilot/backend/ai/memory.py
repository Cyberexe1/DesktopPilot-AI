"""
Memory layer — Phase 2.
Reads/writes DynamoDB for cloud sync, falls back to SQLite when AWS unavailable.
"""

import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, EndpointResolutionError

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

def enrich_prompt(user_command: str, user_id: str = "default") -> str:
    """Inject memory context into the Bedrock prompt."""
    context = get_context(user_id)
    lines   = []

    if context["last_project"]:
        p = context["last_project"]
        lines.append(f"User's last project: {p.get('name')} at {p.get('path')}")

    if context["recent_commands"]:
        lines.append(f"Recent commands: {', '.join(context['recent_commands'])}")

    memory_block = "\n".join(lines)
    if memory_block:
        return f"Context:\n{memory_block}\n\nCommand: {user_command}"
    return f"Command: {user_command}"
