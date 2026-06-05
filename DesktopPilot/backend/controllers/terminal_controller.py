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

SHELL_METACHARACTERS = set('|;`$(){}[]!><')

# These compound patterns are safe (cd + command)
SAFE_COMPOUND_PATTERNS = [
    "cd /d ",    # cd into directory then run something
    "cd ",       # same
]


def _is_safe_command(command: str) -> bool:
    """Check command against blocklist and dangerous patterns."""
    lower = command.lower().strip()
    if any(blocked in lower for blocked in BLOCKED_PATTERNS):
        return False

    # Allow '&' and '&&' ONLY for safe compound commands (cd + npm/pip/python)
    if '&' in command:
        # Split on && and check each part
        parts = [p.strip() for p in command.split('&&')]
        for part in parts:
            part_lower = part.lower()
            # Allow: cd commands, npm/npx/pip/python/node commands
            safe_prefixes = ('cd ', 'cd/d ', 'npm ', 'npx ', 'pip ', 'python ',
                            'node ', 'git ', 'uvicorn ', 'vite ', 'yarn ')
            if not any(part_lower.startswith(p) for p in safe_prefixes):
                # Check for other metacharacters in this part
                if any(c in part for c in set('|;`$(){}[]!><')):
                    log.warning(f"Command contains unsafe metacharacters: {command}")
                    return False
        return True

    # Block commands with dangerous shell metacharacters (not &)
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
        # Build the full command to run in visible terminal
        if working_dir and os.path.exists(working_dir):
            full_cmd = f'cd /d "{working_dir}" && {command}'
        else:
            full_cmd = command

        # Open a new CMD window with the command
        args = ["cmd", "/c", "start", "cmd", "/k", full_cmd]
        subprocess.Popen(args, shell=True)
        msg = f"Running in terminal: {command}"
        if working_dir:
            msg += f" (in {working_dir})"
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
