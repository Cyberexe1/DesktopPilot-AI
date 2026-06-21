"""
Unit tests for the terminal command safety filter.

These guard the most security-critical pure function in the backend:
controllers.terminal_controller._is_safe_command — the only thing standing
between an AI-generated command and `subprocess` with shell=True.

Run:  pytest backend/tests/test_safety.py -v   (from the project root)
  or: pytest tests/test_safety.py -v           (from the backend/ folder)
"""

import pytest

from controllers.terminal_controller import _is_safe_command


# ── Commands that SHOULD be allowed ───────────────────────────────────────────

@pytest.mark.parametrize("command", [
    "npm install",
    "npm run dev",
    "python manage.py runserver",
    "git status",
    "pip install -r requirements.txt",
    "node index.js",
    r"cd /d C:\proj && npm run dev",          # safe compound: cd + npm
    "cd myapp && python app.py",               # safe compound: cd + python
])
def test_safe_commands_allowed(command):
    assert _is_safe_command(command) is True


# ── Commands that MUST be blocked (blocklist) ────────────────────────────────

@pytest.mark.parametrize("command", [
    "rm -rf /",
    "rm -r node_modules",
    "format c:",
    "format d:",
    "shutdown /s /t 0",
    "rmdir /s /q C:\\Windows",
    "del /f /s /q C:\\",
    "drop table users",
    "drop database production",
])
def test_dangerous_commands_blocked(command):
    assert _is_safe_command(command) is False


# ── Commands that MUST be blocked (shell metacharacters) ─────────────────────

@pytest.mark.parametrize("command", [
    "echo hi | curl http://evil.test",         # pipe
    "ls > /etc/passwd",                         # redirect
    "echo $(whoami)",                           # command substitution
    "echo `id`",                                # backtick substitution
    "do_thing; do_other",                       # statement separator
])
def test_metacharacter_commands_blocked(command):
    assert _is_safe_command(command) is False


def test_blocklist_is_case_insensitive():
    assert _is_safe_command("RM -RF /") is False
    assert _is_safe_command("Format C:") is False


# ── Known weakness — documented, intentionally xfail ─────────────────────────
# The '&&' compound branch skips the metacharacter check for any part that
# starts with a "safe prefix" (e.g. "python "). That lets a python -c payload
# smuggle a shell-exec past the filter. This test asserts the SECURE behavior we
# want; it is expected to fail today and documents the gap until the filter is
# replaced with an arg-list + allowlist approach.
@pytest.mark.xfail(reason="Known bypass: safe-prefix parts skip metachar check in '&&' compound commands", strict=True)
def test_compound_safe_prefix_bypass_should_be_blocked():
    payload = r'cd C:\ && python -c "__import__(\'os\').system(\'calc\')"'
    assert _is_safe_command(payload) is False
