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
