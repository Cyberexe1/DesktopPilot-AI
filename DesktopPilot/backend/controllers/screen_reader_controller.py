"""
Screen Reader Controller — captures screen and extracts text using Amazon Textract.
Enables commands like "Read what's on my screen" or "What does this page say?"
"""

import io
import logging
import os
import time

import boto3
import pyautogui
from PIL import Image

log = logging.getLogger(__name__)

REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "desktoppilot-audio")

textract_client = boto3.client("textract", region_name=REGION)
s3_client = boto3.client("s3", region_name=REGION)


def capture_screen() -> bytes:
    """Take a screenshot and return as PNG bytes."""
    screenshot = pyautogui.screenshot()
    buffer = io.BytesIO()
    screenshot.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


def capture_region(x: int, y: int, width: int, height: int) -> bytes:
    """Capture a specific region of the screen."""
    screenshot = pyautogui.screenshot(region=(x, y, width, height))
    buffer = io.BytesIO()
    screenshot.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


def capture_active_window() -> bytes:
    """Capture only the active/focused window."""
    try:
        import pygetwindow as gw
        active = gw.getActiveWindow()
        if active:
            screenshot = pyautogui.screenshot(region=(
                active.left, active.top, active.width, active.height
            ))
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer.getvalue()
    except Exception as e:
        log.warning(f"Could not capture active window: {e}")

    # Fallback to full screen
    return capture_screen()


def read_screen(mode: str = "full") -> str:
    """
    Capture screen and extract text using Amazon Textract.
    mode: "full" (entire screen), "window" (active window only)
    Returns extracted text.
    """
    log.info(f"Capturing screen (mode: {mode})...")

    if mode == "window":
        image_bytes = capture_active_window()
    else:
        image_bytes = capture_screen()

    log.info(f"Screenshot captured: {len(image_bytes)} bytes")

    # Use Textract synchronous API (for images under 5MB)
    if len(image_bytes) < 5 * 1024 * 1024:
        return _textract_sync(image_bytes)
    else:
        # For larger images, upload to S3 first
        return _textract_via_s3(image_bytes)


def read_screen_region(x: int, y: int, width: int, height: int) -> str:
    """Capture a specific screen region and extract text."""
    image_bytes = capture_region(x, y, width, height)
    return _textract_sync(image_bytes)


def _textract_sync(image_bytes: bytes) -> str:
    """Call Textract synchronously with image bytes (under 5MB)."""
    try:
        response = textract_client.detect_document_text(
            Document={"Bytes": image_bytes}
        )

        lines = []
        for block in response.get("Blocks", []):
            if block["BlockType"] == "LINE":
                lines.append(block["Text"])

        text = "\n".join(lines)
        log.info(f"Textract extracted {len(lines)} lines of text")
        return text if text else "No text detected on screen"

    except Exception as e:
        log.error(f"Textract error: {e}")
        return f"Screen reading failed: {e}"


def _textract_via_s3(image_bytes: bytes) -> str:
    """Upload to S3 then call Textract (for images over 5MB)."""
    key = f"screenshots/screen-{int(time.time())}.png"

    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=image_bytes,
            ContentType="image/png",
        )

        response = textract_client.detect_document_text(
            Document={
                "S3Object": {
                    "Bucket": S3_BUCKET,
                    "Name": key,
                }
            }
        )

        lines = []
        for block in response.get("Blocks", []):
            if block["BlockType"] == "LINE":
                lines.append(block["Text"])

        # Clean up
        s3_client.delete_object(Bucket=S3_BUCKET, Key=key)

        text = "\n".join(lines)
        log.info(f"Textract (S3) extracted {len(lines)} lines")
        return text if text else "No text detected on screen"

    except Exception as e:
        log.error(f"Textract S3 error: {e}")
        return f"Screen reading failed: {e}"


def analyze_screen() -> dict:
    """
    Full screen analysis — returns structured data with text, tables, and forms.
    Uses Textract AnalyzeDocument for richer extraction.
    """
    image_bytes = capture_screen()

    try:
        response = textract_client.analyze_document(
            Document={"Bytes": image_bytes},
            FeatureTypes=["TABLES", "FORMS"]
        )

        text_lines = []
        key_values = {}
        tables = []

        for block in response.get("Blocks", []):
            if block["BlockType"] == "LINE":
                text_lines.append(block["Text"])
            elif block["BlockType"] == "KEY_VALUE_SET":
                # Extract form key-value pairs
                if block.get("EntityTypes") and "KEY" in block["EntityTypes"]:
                    key_text = _get_text_from_block(block, response["Blocks"])
                    val_block = _find_value_block(block, response["Blocks"])
                    if val_block:
                        val_text = _get_text_from_block(val_block, response["Blocks"])
                        if key_text and val_text:
                            key_values[key_text] = val_text

        return {
            "text": "\n".join(text_lines),
            "line_count": len(text_lines),
            "forms": key_values,
            "has_tables": any(b["BlockType"] == "TABLE" for b in response.get("Blocks", [])),
        }

    except Exception as e:
        log.error(f"Textract analyze error: {e}")
        return {"text": f"Analysis failed: {e}", "line_count": 0, "forms": {}, "has_tables": False}


def _get_text_from_block(block: dict, all_blocks: list) -> str:
    """Extract text from a block's child relationships."""
    text = ""
    if "Relationships" in block:
        for rel in block["Relationships"]:
            if rel["Type"] == "CHILD":
                for child_id in rel["Ids"]:
                    child = next((b for b in all_blocks if b["Id"] == child_id), None)
                    if child and child["BlockType"] == "WORD":
                        text += child.get("Text", "") + " "
    return text.strip()


def _find_value_block(key_block: dict, all_blocks: list) -> dict | None:
    """Find the VALUE block associated with a KEY block."""
    if "Relationships" in key_block:
        for rel in key_block["Relationships"]:
            if rel["Type"] == "VALUE":
                for val_id in rel["Ids"]:
                    val = next((b for b in all_blocks if b["Id"] == val_id), None)
                    if val:
                        return val
    return None
