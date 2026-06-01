"""
Application Controller — opens Windows applications via subprocess.
"""

import logging
import os
import subprocess

log = logging.getLogger(__name__)

# Registry of known applications.
# Paths use environment variables so they work across different user accounts.
_USER = os.environ.get("USERNAME", "User")

APP_REGISTRY: dict[str, str] = {
    "chrome":    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "vscode":    rf"C:\Users\{_USER}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "vs code":   rf"C:\Users\{_USER}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "visual studio code": rf"C:\Users\{_USER}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "notepad":   "notepad.exe",
    "word":      r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    "excel":     r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    "powerpoint":r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
    "explorer":  "explorer.exe",
    "file explorer": "explorer.exe",
    "calculator":"calc.exe",
    "paint":     "mspaint.exe",
    "cmd":       "cmd.exe",
    "terminal":  "cmd.exe",
    "powershell":"powershell.exe",
    "task manager": "taskmgr.exe",
    "spotify":   rf"C:\Users\{_USER}\AppData\Roaming\Spotify\Spotify.exe",
    "discord":   rf"C:\Users\{_USER}\AppData\Local\Discord\Update.exe",
    "slack":     rf"C:\Users\{_USER}\AppData\Local\slack\slack.exe",
    "zoom":      rf"C:\Users\{_USER}\AppData\Roaming\Zoom\bin\Zoom.exe",
}


def open_application(name: str) -> str:
    """Open a registered application by name."""
    key  = name.lower().strip()
    path = APP_REGISTRY.get(key)

    if not path:
        # Fuzzy fallback — check if any key contains the query
        for reg_key, reg_path in APP_REGISTRY.items():
            if key in reg_key or reg_key in key:
                path = reg_path
                break

    if not path:
        msg = f"Application '{name}' not found in registry"
        log.warning(msg)
        return msg

    if not os.path.exists(path) and path not in ("notepad.exe", "calc.exe",
                                                   "mspaint.exe", "cmd.exe",
                                                   "powershell.exe", "explorer.exe",
                                                   "taskmgr.exe"):
        msg = f"Application path not found: {path}"
        log.warning(msg)
        return msg

    try:
        subprocess.Popen([path], shell=False)
        msg = f"Opened {name}"
        log.info(msg)
        return msg
    except Exception as e:
        msg = f"Failed to open {name}: {e}"
        log.error(msg)
        return msg
