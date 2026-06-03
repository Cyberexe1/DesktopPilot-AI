"""
Auth Controller — signup, login, user management with DynamoDB.
Stores users in DynamoDB table 'CipherAIUsers'.
New users get 100 credits automatically.
"""

import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

log = logging.getLogger(__name__)

REGION     = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
USER_TABLE = "CipherAIUsers"
MEM_TABLE  = os.getenv("DYNAMODB_TABLE_MEMORY", "DesktopPilotMemory")

_dynamo = None


def _get_dynamo():
    global _dynamo
    if _dynamo is None:
        _dynamo = boto3.resource("dynamodb", region_name=REGION)
    return _dynamo


def _hash_password(password: str) -> str:
    """Hash password with SHA-256 + salt."""
    salt = "cipher_ai_2025"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def signup(name: str, email: str, password: str) -> dict:
    """
    Create a new user account.
    Returns {success, message, user} or {success: False, error}.
    """
    email = email.lower().strip()
    name = name.strip()

    if not name or not email or not password:
        return {"success": False, "error": "Name, email, and password are required"}

    if len(password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters"}

    if "@" not in email:
        return {"success": False, "error": "Invalid email address"}

    try:
        table = _get_dynamo().Table(USER_TABLE)

        # Check if user already exists
        response = table.get_item(Key={"email": email})
        if "Item" in response:
            return {"success": False, "error": "Account already exists with this email"}

        # Create user
        user_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        user_item = {
            "email":        email,
            "user_id":      user_id,
            "name":         name,
            "password_hash": _hash_password(password),
            "plan":         "Free",
            "credits":      100,
            "created_at":   now,
            "last_login":   now,
        }

        table.put_item(Item=user_item)

        # Also create memory entry with 100 credits
        mem_table = _get_dynamo().Table(MEM_TABLE)
        mem_table.put_item(Item={
            "user_id":           user_id,
            "credits_remaining": 100,
            "last_updated":      now,
        })

        log.info(f"New user created: {email} (id: {user_id})")

        return {
            "success": True,
            "message": "Account created successfully",
            "user": {
                "user_id": user_id,
                "email":   email,
                "name":    name,
                "plan":    "Free",
                "credits": 100,
            }
        }

    except (ClientError, NoCredentialsError) as e:
        log.error(f"Signup failed: {e}")
        return {"success": False, "error": "Database error. Please try again."}


def login(email: str, password: str) -> dict:
    """
    Authenticate user.
    Returns {success, user} or {success: False, error}.
    """
    email = email.lower().strip()

    if not email or not password:
        return {"success": False, "error": "Email and password are required"}

    try:
        table = _get_dynamo().Table(USER_TABLE)

        response = table.get_item(Key={"email": email})
        if "Item" not in response:
            return {"success": False, "error": "Account not found"}

        user = response["Item"]

        # Check password
        if user["password_hash"] != _hash_password(password):
            return {"success": False, "error": "Incorrect password"}

        # Update last login
        table.update_item(
            Key={"email": email},
            UpdateExpression="SET last_login = :t",
            ExpressionAttributeValues={":t": datetime.now(timezone.utc).isoformat()}
        )

        log.info(f"User logged in: {email}")

        return {
            "success": True,
            "user": {
                "user_id": user["user_id"],
                "email":   user["email"],
                "name":    user["name"],
                "plan":    user.get("plan", "Free"),
                "credits": int(user.get("credits", 100)),
            }
        }

    except (ClientError, NoCredentialsError) as e:
        log.error(f"Login failed: {e}")
        return {"success": False, "error": "Database error. Please try again."}


def get_user(email: str) -> dict | None:
    """Get user data by email."""
    try:
        table = _get_dynamo().Table(USER_TABLE)
        response = table.get_item(Key={"email": email.lower().strip()})
        if "Item" in response:
            user = response["Item"]
            return {
                "user_id": user["user_id"],
                "email":   user["email"],
                "name":    user["name"],
                "plan":    user.get("plan", "Free"),
                "credits": int(user.get("credits", 100)),
            }
        return None
    except Exception:
        return None
