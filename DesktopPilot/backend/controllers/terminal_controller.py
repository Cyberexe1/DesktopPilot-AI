"""
Terminal Controller — run shell commands safely.
"""

import logging
import os
import subprocess
import shlex

log = logging.getLogger(__name__)

BLOCKED_PATTERNS = [
    "rm -rf", "del /f /s /q", "format c:", "shutdown", "rmdir /s",
    "rd /s", "del /q", "drop table", "drop database", "rm -r",
    "format d:", "format e:", "del *", "erase *",
]

SHELL_METACHARACTERS = set('&|;`$(){}[]!><')


def _is_safe_command(command: str) -> bool:
    """Check command against blocklist and dangerous patterns."""
    lower = command.lower().strip()
    if any(blocked in lower for blocked in BLOCKED_PATTERNS):
        return False
    # Block commands with shell metacharacters that could enable injection
    if any(c in command for c in SHELL_METACHARACTERS):
        log.warning(f"Command contains shell metacharacters: {command}")
        return False
    return True


def run_in_terminal(command: str, working_dir: str = None) -> str:
    """Open a new CMD window and run a command visibly."""
    if not _is_safe_command(command):
        msg = f"Command blocked for safety: {command}"
        log.warning(msg)
        return msg

    try:
        args = ["cmd", "/c", "start", "cmd", "/k"]
        if working_dir and os.path.exists(working_dir):
            args.extend(["cd", "/d", working_dir, "&&", command])
        else:
            args.append(command)

        subprocess.Popen(args, shell=False)
        msg = f"Running in terminal: {command}"
        log.info(msg)
        return msg
    except Exception as e:
        msg = f"Terminal error: {e}"
        log.error(msg)
        return msg


def open_vscode(project_path: str) -> str:
    """Open a folder in VS Code."""
    if not os.path.exists(project_path):
        return f"Project path not found: {project_path}"

    try:
        subprocess.Popen(["code", project_path], shell=False)
        msg = f"Opened VS Code: {project_path}"
        log.info(msg)
        return msg
    except FileNotFoundError:
        _USER = os.environ.get("USERNAME", "User")
        vscode_path = rf"C:\Users\{_USER}\AppData\Local\Programs\Microsoft VS Code\Code.exe"
        try:
            subprocess.Popen([vscode_path, project_path], shell=False)
            return f"Opened VS Code: {project_path}"
        except Exception as e:
            return f"Failed to open VS Code: {e}"
