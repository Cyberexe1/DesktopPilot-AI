"""
Window Controller — verifies and manages active windows.
Prevents typing into wrong windows by checking what's actually in focus.
"""

import logging
import time

import pygetwindow as gw

log = logging.getLogger(__name__)


def get_active_window_title() -> str:
    """Get the title of the currently active/focused window."""
    try:
        win = gw.getActiveWindow()
        return win.title if win else ""
    except Exception:
        return ""


def wait_for_window(title_contains: str, timeout: int = 10) -> bool:
    """
    Wait until a window with the given title substring is active.
    Returns True if found within timeout, False otherwise.
    """
    start = time.time()
    title_lower = title_contains.lower()

    while time.time() - start < timeout:
        try:
            active = gw.getActiveWindow()
            if active and title_lower in active.title.lower():
                log.info(f"Window found: '{active.title}'")
                return True
        except Exception:
            pass
        time.sleep(0.5)

    log.warning(f"Window containing '{title_contains}' not found within {timeout}s")
    return False


def find_and_focus_window(title_contains: str) -> bool:
    """
    Find a window by title substring and bring it to focus.
    Returns True if found and focused, False otherwise.
    """
    title_lower = title_contains.lower()

    try:
        all_windows = gw.getAllWindows()
        for win in all_windows:
            if win.title and title_lower in win.title.lower():
                try:
                    if win.isMinimized:
                        win.restore()
                    win.activate()
                    time.sleep(0.5)
                    log.info(f"Focused window: '{win.title}'")
                    return True
                except Exception as e:
                    log.warning(f"Could not focus window '{win.title}': {e}")
    except Exception as e:
        log.warning(f"Window search failed: {e}")

    return False


def is_correct_window_active(expected_app: str) -> bool:
    """
    Check if the currently active window matches the expected application.
    Uses fuzzy matching on window title.
    """
    # Map app names to expected window title keywords
    APP_TITLE_MAP = {
        "notepad":     ["notepad", "untitled"],
        "chrome":      ["chrome", "google chrome", "new tab"],
        "vscode":      ["visual studio code", "code"],
        "vs code":     ["visual studio code", "code"],
        "word":        ["word", "document"],
        "excel":       ["excel", "book"],
        "powerpoint":  ["powerpoint", "presentation"],
        "explorer":    ["file explorer", "explorer"],
        "cmd":         ["cmd", "command prompt"],
        "terminal":    ["terminal", "cmd", "powershell"],
        "gmail":       ["gmail", "mail", "inbox"],
    }

    expected_lower = expected_app.lower().strip()
    keywords = APP_TITLE_MAP.get(expected_lower, [expected_lower])

    try:
        active = gw.getActiveWindow()
        if not active or not active.title:
            return False

        active_title = active.title.lower()
        return any(kw in active_title for kw in keywords)
    except Exception:
        return False


def ensure_app_focused(app_name: str, timeout: int = 5) -> str:
    """
    Ensure the correct app is in focus. If not, try to find and focus it.
    Returns status message.
    """
    # First check if already focused
    if is_correct_window_active(app_name):
        return f"✓ {app_name} is active"

    # Try to find and focus it
    APP_SEARCH_MAP = {
        "notepad":    "notepad",
        "chrome":     "chrome",
        "vscode":     "code",
        "vs code":    "code",
        "word":       "word",
        "excel":      "excel",
        "powerpoint": "powerpoint",
        "gmail":      "gmail",
    }

    search_term = APP_SEARCH_MAP.get(app_name.lower(), app_name)

    if find_and_focus_window(search_term):
        return f"✓ Switched to {app_name}"

    return f"✗ Could not find {app_name} window"


# ── Window Management ─────────────────────────────────────────────────────────

def snap_window(app_name: str, position: str) -> str:
    """
    Snap a window to a position: left, right, maximize, minimize.
    """
    import pyautogui
    import time

    # First, find and focus the window
    if not find_and_focus_window(app_name):
        return f"Window '{app_name}' not found"

    time.sleep(0.5)
    pos = position.lower().strip()

    if pos in ("left", "left half"):
        pyautogui.hotkey('win', 'left')
        return f"Snapped {app_name} to left half"
    elif pos in ("right", "right half"):
        pyautogui.hotkey('win', 'right')
        return f"Snapped {app_name} to right half"
    elif pos in ("maximize", "full", "fullscreen"):
        pyautogui.hotkey('win', 'up')
        return f"Maximized {app_name}"
    elif pos in ("minimize", "min"):
        pyautogui.hotkey('win', 'down')
        return f"Minimized {app_name}"
    elif pos in ("top left", "top-left"):
        pyautogui.hotkey('win', 'left')
        time.sleep(0.3)
        pyautogui.hotkey('win', 'up')
        return f"Snapped {app_name} to top-left"
    elif pos in ("top right", "top-right"):
        pyautogui.hotkey('win', 'right')
        time.sleep(0.3)
        pyautogui.hotkey('win', 'up')
        return f"Snapped {app_name} to top-right"
    elif pos in ("bottom left", "bottom-left"):
        pyautogui.hotkey('win', 'left')
        time.sleep(0.3)
        pyautogui.hotkey('win', 'down')
        return f"Snapped {app_name} to bottom-left"
    elif pos in ("bottom right", "bottom-right"):
        pyautogui.hotkey('win', 'right')
        time.sleep(0.3)
        pyautogui.hotkey('win', 'down')
        return f"Snapped {app_name} to bottom-right"
    else:
        return f"Unknown position: {position}. Use: left, right, maximize, minimize"


def close_window(app_name: str) -> str:
    """Close a specific window."""
    if find_and_focus_window(app_name):
        import pyautogui
        import time
        time.sleep(0.3)
        pyautogui.hotkey('alt', 'F4')
        return f"Closed {app_name}"
    return f"Window '{app_name}' not found"


def close_all_windows(app_name: str) -> str:
    """Close all windows of a specific app."""
    try:
        all_windows = gw.getAllWindows()
        closed = 0
        name_lower = app_name.lower()
        for win in all_windows:
            if win.title and name_lower in win.title.lower():
                try:
                    win.close()
                    closed += 1
                except Exception:
                    pass
        return f"Closed {closed} {app_name} window(s)" if closed > 0 else f"No {app_name} windows found"
    except Exception as e:
        return f"Failed to close {app_name} windows: {e}"


def switch_to_window(app_name: str) -> str:
    """Switch to (focus) a specific window."""
    if find_and_focus_window(app_name):
        return f"Switched to {app_name}"
    return f"Window '{app_name}' not found"


def minimize_all() -> str:
    """Minimize all windows (show desktop)."""
    import pyautogui
    pyautogui.hotkey('win', 'd')
    return "All windows minimized (desktop shown)"


def list_open_windows() -> str:
    """List all currently open windows."""
    try:
        all_windows = gw.getAllWindows()
        visible = [w.title for w in all_windows if w.title and w.title.strip() and w.visible]
        if visible:
            return f"Open windows ({len(visible)}):\n" + "\n".join(f"• {t}" for t in visible[:15])
        return "No visible windows"
    except Exception as e:
        return f"Failed to list windows: {e}"
