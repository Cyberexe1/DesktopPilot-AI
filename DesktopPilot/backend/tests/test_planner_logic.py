"""
Unit tests for the planner's pure logic:
  - _needs_approval : decides whether a plan hits the approval gate
  - _parse_plan     : extracts a JSON plan from a raw model response

These don't call Bedrock — they exercise the parsing/approval logic only.

Run:  pytest backend/tests/test_planner_logic.py -v   (from project root)
  or: pytest tests/test_planner_logic.py -v           (from backend/ folder)
"""

import pytest

from ai.planner import _needs_approval, _parse_plan, SENSITIVE_TOOLS


# ── Approval gate ─────────────────────────────────────────────────────────────

def test_safe_only_plan_needs_no_approval():
    plan = {"intent": "open chrome", "tasks": [
        {"tool": "open_application", "name": "chrome"},
        {"tool": "open_browser", "url": "https://example.com"},
    ]}
    assert _needs_approval(plan) is False


def test_plan_with_terminal_needs_approval():
    plan = {"tasks": [
        {"tool": "open_application", "name": "vscode"},
        {"tool": "run_terminal", "command": "npm run dev"},
    ]}
    assert _needs_approval(plan) is True


@pytest.mark.parametrize("tool", sorted(SENSITIVE_TOOLS))
def test_every_sensitive_tool_triggers_approval(tool):
    plan = {"tasks": [{"tool": tool}]}
    assert _needs_approval(plan) is True


def test_empty_plan_needs_no_approval():
    assert _needs_approval({"tasks": []}) is False
    assert _needs_approval({}) is False


# ── Plan parsing ──────────────────────────────────────────────────────────────

def test_parse_clean_json():
    raw = '{"intent": "test", "tasks": [{"tool": "open_browser", "url": "https://x.com"}]}'
    plan = _parse_plan(raw)
    assert plan["intent"] == "test"
    assert plan["tasks"][0]["tool"] == "open_browser"


def test_parse_json_wrapped_in_prose():
    raw = (
        "Sure! Here is the plan you asked for:\n"
        '{"intent": "open app", "tasks": [{"tool": "open_application", "name": "notepad"}]}\n'
        "Let me know if you need anything else."
    )
    plan = _parse_plan(raw)
    assert plan["tasks"][0]["name"] == "notepad"


def test_parse_garbage_returns_empty_plan():
    plan = _parse_plan("I cannot help with that.")
    assert plan == {"intent": "unknown", "tasks": []}


# ── Post-processing: questions / greetings survive an empty model plan ────────

from ai.planner import _post_process_plan


def test_question_with_empty_plan_forces_answer_question():
    # Model returned nothing usable, but it's a knowledge question — we must
    # still produce an answer_question task (this was the bug: the empty-tasks
    # guard returned before the question logic ran).
    plan = _post_process_plan({"intent": "unknown", "tasks": []}, "what is machine learning")
    assert plan["tasks"] == [{"tool": "answer_question", "question": "what is machine learning"}]
    assert plan["intent"] == "knowledge question"


def test_question_with_wrong_tool_is_replaced():
    plan = _post_process_plan(
        {"intent": "x", "tasks": [{"tool": "search_web", "query": "cybersecurity"}]},
        "what is cybersecurity",
    )
    assert plan["tasks"][0]["tool"] == "answer_question"


def test_answer_question_with_empty_question_is_backfilled():
    # Model emitted answer_question but left the question blank → must backfill
    # from the user command, otherwise the controller says "No question provided".
    plan = _post_process_plan(
        {"intent": "x", "tasks": [{"tool": "answer_question"}]},
        "what is machine learning",
    )
    assert plan["tasks"][0]["question"] == "what is machine learning"


def test_greeting_with_empty_plan_forces_speak():
    plan = _post_process_plan({"intent": "unknown", "tasks": []}, "hello")
    assert len(plan["tasks"]) == 1
    assert plan["tasks"][0]["tool"] == "speak"
    assert plan["intent"] == "greeting"


def test_system_info_question_is_not_treated_as_knowledge():
    # "what is my battery" must NOT become answer_question — it's a system query.
    plan = _post_process_plan(
        {"intent": "battery", "tasks": [{"tool": "system_info", "query": "battery"}]},
        "what is my battery",
    )
    assert plan["tasks"][0]["tool"] == "system_info"
