"""
Application Controller — opens any application on Windows.
Uses a known registry for common apps (fast), falls back to Windows Search for unknown apps.
"""

import logging
import os
import subprocess
import time

log = logging.getLogger(__name__)

_USER = os.environ.get("USERNAME", "User")

# Known app paths (fast path — avoids Windows Search delay)
APP_REGISTRY: dict[str, str] = {
    "chrome":         r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome":  r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "vscode":         rf"C:\Users\{_USER}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "vs code":        rf"C:\Users\{_USER}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "notepad":        "notepad.exe",
    "word":           r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    "excel":          r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    "powerpoint":     r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
    "explorer":       "explorer.exe",
    "file explorer":  "explorer.exe",
    "calculator":     "calc.exe",
    "paint":          "mspaint.exe",
    "cmd":            "cmd.exe",
    "terminal":       "cmd.exe",
    "powershell":     "powershell.exe",
    "task manager":   "taskmgr.exe",
    "whatsapp":       "shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
    "telegram":       "https://web.telegram.org",
}

# System executables that don't need full path check
SYSTEM_APPS = {"notepad.exe", "calc.exe", "mspaint.exe", "cmd.exe",
               "powershell.exe", "explorer.exe", "taskmgr.exe"}


def open_application(name: str) -> str:
    """
    Open any application by name.
    1. Check known registry (fast — instant launch)
    2. If not found → use Windows Search (Win key → type → Enter)
    This way ANY installed app can be opened without manual configuration.
    """
    key = name.lower().strip()

    # Try exact match in registry
    path = APP_REGISTRY.get(key)

    # Fuzzy match
    if not path:
        for reg_key, reg_path in APP_REGISTRY.items():
            if key in reg_key or reg_key in key:
                path = reg_path
                break

    # Found in registry — use fast path
    if path:
        result = _launch_from_path(name, path)
        if result:
            return result

    # Not in registry → Use Windows Search (works for ANY app)
    log.info(f"App '{name}' not in registry — using Windows Search")
    return _open_via_windows_search(name)


def _launch_from_path(name: str, path: str) -> str | None:
    """Try to launch app from a known path. Returns None on failure."""
    try:
        # URL-based apps (open in browser)
        if path.startswith("http"):
            subprocess.Popen(["cmd", "/c", "start", "", path], shell=False)
            log.info(f"Opened {name} in browser")
            return f"Opened {name}"

        # Microsoft Store apps
        if path.startswith("shell:"):
            subprocess.Popen(["cmd", "/c", "start", "", path], shell=False)
            log.info(f"Opened {name}")
            return f"Opened {name}"

        # Regular exe
        if os.path.exists(path) or path in SYSTEM_APPS:
            subprocess.Popen([path], shell=False)
            log.info(f"Opened {name}")
            return f"Opened {name}"

        log.warning(f"Path not found: {path}")
        return None

    except Exception as e:
        log.warning(f"Failed to launch {name} from registry: {e}")
        return None


def _open_via_windows_search(name: str) -> str:
    """
    Open ANY application using Windows Start Menu search.
    Presses Win key → types app name → waits for results → presses Enter.
    """
    import pyautogui

    try:
        # Press Windows key to open Start Menu / Search
        pyautogui.press('win')
        time.sleep(1.0)

        # Type the app name
        if name.isascii():
            pyautogui.typewrite(name, interval=0.04)
        else:
            import pyperclip
            pyperclip.copy(name)
            pyautogui.hotkey('ctrl', 'v')

        # Wait for search results to populate
        time.sleep(1.5)

        # Press Enter to launch the top result
        pyautogui.press('enter')
        time.sleep(0.5)

        msg = f"Opened {name} via Windows Search"
        log.info(msg)
        return msg

    except Exception as e:
        msg = f"Failed to open {name}: {e}"
        log.error(msg)
        return msg
