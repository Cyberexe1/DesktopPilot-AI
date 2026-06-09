"""
Keyboard Controller — types text into the active window using PyAutoGUI.
Enables commands like "Open Notepad and write a letter".
"""

import logging
import time

import pyautogui

log = logging.getLogger(__name__)

# Safety: PyAutoGUI failsafe — move mouse to corner to abort
pyautogui.FAILSAFE = True
# Typing speed (seconds between keystrokes) — 0.04 = human-like speed
pyautogui.PAUSE = 0.01

# Default typing interval (adjustable)
DEFAULT_TYPING_SPEED = 0.04  # 40ms per character — looks natural


def type_text(text: str, interval: float = DEFAULT_TYPING_SPEED) -> str:
    """
    Type text into the currently focused window.
    Waits 1 second before typing to let the target app gain focus.
    """
    if not text:
        return "No text to type"

    try:
        # Wait for the target app to be ready
        time.sleep(1.0)

        # Type the text character by character
        pyautogui.typewrite(text, interval=interval) if text.isascii() else _type_unicode(text)

        msg = f"Typed {len(text)} characters"
        log.info(msg)
        return msg
    except Exception as e:
        msg = f"Typing failed: {e}"
        log.error(msg)
        return msg


def _type_unicode(text: str):
    """Handle unicode text (non-ASCII) using pyperclip + paste."""
    import pyperclip
    pyperclip.copy(text)
    pyautogui.hotkey('ctrl', 'v')
    log.info("Pasted unicode text via clipboard")


def press_key(key: str) -> str:
    """Press a single key or key combination (e.g., 'enter', 'ctrl+s')."""
    try:
        time.sleep(0.3)
        if '+' in key:
            keys = [k.strip() for k in key.split('+')]
            pyautogui.hotkey(*keys)
        else:
            pyautogui.press(key)
        msg = f"Pressed: {key}"
        log.info(msg)
        return msg
    except Exception as e:
        msg = f"Key press failed: {e}"
        log.error(msg)
        return msg


def click_at(x: int, y: int) -> str:
    """Click at specific screen coordinates."""
    try:
        pyautogui.click(x, y)
        msg = f"Clicked at ({x}, {y})"
        log.info(msg)
        return msg
    except Exception as e:
        msg = f"Click failed: {e}"
        log.error(msg)
        return msg


# ── Mouse Controls ────────────────────────────────────────────────────────────

def right_click_at(x: int = None, y: int = None) -> str:
    """Right-click at coordinates, or at current cursor position if none given."""
    try:
        if x is not None and y is not None:
            pyautogui.rightClick(x, y)
            msg = f"Right-clicked at ({x}, {y})"
        else:
            pyautogui.rightClick()
            msg = "Right-clicked at current position"
        log.info(msg)
        return msg
    except Exception as e:
        return f"Right-click failed: {e}"


def double_click_at(x: int = None, y: int = None) -> str:
    """Double-click at coordinates, or at current cursor position."""
    try:
        if x is not None and y is not None:
            pyautogui.doubleClick(x, y)
            msg = f"Double-clicked at ({x}, {y})"
        else:
            pyautogui.doubleClick()
            msg = "Double-clicked at current position"
        log.info(msg)
        return msg
    except Exception as e:
        return f"Double-click failed: {e}"


def move_mouse(x: int, y: int, duration: float = 0.3) -> str:
    """Move mouse to coordinates smoothly."""
    try:
        pyautogui.moveTo(x, y, duration=duration)
        msg = f"Mouse moved to ({x}, {y})"
        log.info(msg)
        return msg
    except Exception as e:
        return f"Mouse move failed: {e}"


def move_mouse_relative(dx: int, dy: int) -> str:
    """Move mouse relative to its current position."""
    try:
        pyautogui.moveRel(dx, dy, duration=0.2)
        msg = f"Mouse moved by ({dx}, {dy})"
        log.info(msg)
        return msg
    except Exception as e:
        return f"Mouse move failed: {e}"


def scroll_at(x: int = None, y: int = None, amount: int = 3, direction: str = "down") -> str:
    """Scroll up or down at a position."""
    try:
        clicks = -amount if direction == "down" else amount
        if x is not None and y is not None:
            pyautogui.scroll(clicks, x=x, y=y)
        else:
            pyautogui.scroll(clicks)
        msg = f"Scrolled {direction} {amount} times"
        log.info(msg)
        return msg
    except Exception as e:
        return f"Scroll failed: {e}"


def drag_and_drop(from_x: int, from_y: int, to_x: int, to_y: int, duration: float = 0.5) -> str:
    """Drag from one position and drop at another."""
    try:
        pyautogui.moveTo(from_x, from_y, duration=0.2)
        time.sleep(0.1)
        pyautogui.dragTo(to_x, to_y, duration=duration, button='left')
        msg = f"Dragged from ({from_x}, {from_y}) to ({to_x}, {to_y})"
        log.info(msg)
        return msg
    except Exception as e:
        return f"Drag failed: {e}"


def get_mouse_position() -> str:
    """Get current mouse cursor coordinates."""
    try:
        x, y = pyautogui.position()
        return f"Mouse is at ({x}, {y})"
    except Exception as e:
        return f"Could not get mouse position: {e}"


def get_screen_size() -> str:
    """Get screen resolution."""
    try:
        w, h = pyautogui.size()
        return f"Screen size: {w}x{h}"
    except Exception as e:
        return f"Could not get screen size: {e}"


# ── Smart Click (by text/label — finds element on screen) ────────────────────

def smart_click(text: str, click_type: str = "left") -> str:
    """
    Find text on screen using OCR (Textract) and click on it.
    Works with ANY application — finds button/label by text and clicks it.

    Args:
        text: The text to find and click on (e.g., "Save", "OK", "Submit")
        click_type: "left", "right", or "double"
    """
    try:
        import io
        import boto3
        import os

        # Step 1: Take a screenshot
        screenshot = pyautogui.screenshot()
        buffer = io.BytesIO()
        screenshot.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

        screen_w, screen_h = pyautogui.size()
        log.info(f"Smart click: looking for '{text}' on {screen_w}x{screen_h} screen")

        # Step 2: Call Textract to get text with bounding boxes
        REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        client = boto3.client("textract", region_name=REGION)

        response = client.detect_document_text(
            Document={"Bytes": image_bytes}
        )

        # Step 3: Find the target text in Textract results
        text_lower = text.lower()
        best_block = None
        best_score = 0

        for block in response.get("Blocks", []):
            if block.get("BlockType") != "WORD":
                continue

            block_text = block.get("Text", "").lower()
            confidence = block.get("Confidence", 0)

            # Exact match preferred, then partial match
            if block_text == text_lower and confidence > best_score:
                best_block = block
                best_score = confidence
            elif text_lower in block_text and confidence > best_score * 0.8:
                if best_block is None:
                    best_block = block
                    best_score = confidence * 0.8

        # Also check LINE blocks for multi-word labels
        if best_block is None:
            for block in response.get("Blocks", []):
                if block.get("BlockType") != "LINE":
                    continue

                block_text = block.get("Text", "").lower()
                confidence = block.get("Confidence", 0)

                if text_lower in block_text and confidence > 70:
                    best_block = block
                    best_score = confidence
                    break

        if best_block is None:
            return f"Could not find '{text}' on screen. Try reading the screen first."

        # Step 4: Convert bounding box to screen coordinates
        bbox = best_block["Geometry"]["BoundingBox"]

        # Bounding box is normalized (0-1) — convert to pixels
        center_x = int((bbox["Left"] + bbox["Width"] / 2) * screen_w)
        center_y = int((bbox["Top"] + bbox["Height"] / 2) * screen_h)

        # Add small random offset to look natural
        import random
        center_x += random.randint(-2, 2)
        center_y += random.randint(-2, 2)

        log.info(f"Found '{text}' at ({center_x}, {center_y}), confidence: {best_score:.0f}%")

        # Step 5: Move to element first (natural behavior), then click
        pyautogui.moveTo(center_x, center_y, duration=0.3)
        time.sleep(0.1)

        if click_type == "right":
            pyautogui.rightClick(center_x, center_y)
        elif click_type == "double":
            pyautogui.doubleClick(center_x, center_y)
        else:
            pyautogui.click(center_x, center_y)

        msg = f"Clicked '{text}' at ({center_x}, {center_y})"
        log.info(msg)
        return msg

    except Exception as e:
        log.error(f"Smart click failed: {e}")
        return f"Smart click failed: {e}"


def smart_right_click(text: str) -> str:
    """Find text on screen and right-click it."""
    return smart_click(text, click_type="right")


def smart_double_click(text: str) -> str:
    """Find text on screen and double-click it."""
    return smart_click(text, click_type="double")
