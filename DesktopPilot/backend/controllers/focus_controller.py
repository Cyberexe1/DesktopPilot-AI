"""
Focus Mode / Pomodoro Controller
- Blocks distracting apps/sites, sets DND, runs Pomodoro cycles
- Tracks sessions in SQLite
- Speaks announcements via Polly
- Generates productivity report at session end
"""

import json
import logging
import os
import subprocess
import threading
import time
from datetime import datetime

import boto3

log = logging.getLogger(__name__)

REGION   = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")

# ── Distraction list ─────────────────────────────────────────────────────────

DISTRACTING_APPS = [
    "Discord", "Slack", "Spotify", "WhatsApp",
    "Telegram", "Teams", "zoom",
]

DISTRACTING_DOMAINS = [
    "youtube.com", "reddit.com", "twitter.com", "x.com",
    "facebook.com", "instagram.com", "tiktok.com", "netflix.com",
    "twitch.tv", "9gag.com",
]

# ── Focus state ──────────────────────────────────────────────────────────────

_focus_state = {
    "active":          False,
    "mode":            "focus",       # "focus" | "break"
    "cycle":           0,             # current pomodoro cycle number
    "total_cycles":    4,             # default 4 cycles
    "focus_minutes":   25,
    "break_minutes":   5,
    "long_break_min":  15,
    "session_start":   None,
    "cycle_start":     None,
    "thread":          None,
    "stop_flag":       False,
    "commands_run":    0,
    "blocked_apps":    [],
    "session_goal":    "",
}

# Completed sessions history
_sessions: list[dict] = []


# ── Start / Stop ─────────────────────────────────────────────────────────────

def start_focus_mode(
    duration_hours: float = 2.0,
    goal: str = "",
    focus_min: int = 25,
    break_min: int = 5,
) -> str:
    """Start focus mode with Pomodoro cycles."""
    if _focus_state["active"]:
        return "Focus mode is already active"

    total_cycles = max(1, int((duration_hours * 60) / (focus_min + break_min)))

    _focus_state.update({
        "active":        True,
        "mode":          "focus",
        "cycle":         1,
        "total_cycles":  total_cycles,
        "focus_minutes": focus_min,
        "break_minutes": break_min,
        "session_start": datetime.now(),
        "cycle_start":   datetime.now(),
        "stop_flag":     False,
        "commands_run":  0,
        "blocked_apps":  [],
        "session_goal":  goal,
    })

    # Close distracting apps
    closed = _close_distracting_apps()

    # Set Windows Do Not Disturb (Focus Assist)
    _set_dnd(True)

    # Start Pomodoro thread
    t = threading.Thread(target=_pomodoro_loop, daemon=True)
    _focus_state["thread"] = t
    t.start()

    goal_msg = f" Goal: {goal}." if goal else ""
    closed_msg = f" Closed: {', '.join(closed)}." if closed else ""

    _speak(f"Focus mode started. {focus_min} minutes to work, then {break_min} minutes break, for {total_cycles} cycles.{goal_msg}{closed_msg} Let's get it, Sir.")

    return (
        f"Focus mode started — {total_cycles} Pomodoro cycles "
        f"({focus_min}m work / {break_min}m break). "
        f"Duration: {duration_hours}h.{closed_msg}"
    )


def stop_focus_mode() -> dict:
    """End focus mode early and generate report."""
    if not _focus_state["active"]:
        return {"error": "Focus mode is not active"}

    _focus_state["stop_flag"] = True
    _focus_state["active"]    = False

    # Re-enable DND off
    _set_dnd(False)

    report = _generate_report()
    _sessions.append(report)

    _speak(f"Focus mode ended. You completed {report['cycles_completed']} cycles. Great work, Sir!")

    return report


def get_focus_status() -> dict:
    """Return current focus mode status."""
    if not _focus_state["active"]:
        return {
            "active":    False,
            "sessions":  len(_sessions),
        }

    elapsed_cycle = int((datetime.now() - _focus_state["cycle_start"]).total_seconds())
    total_seconds = (
        _focus_state["focus_minutes"] * 60
        if _focus_state["mode"] == "focus"
        else _focus_state["break_minutes"] * 60
    )
    remaining = max(0, total_seconds - elapsed_cycle)

    return {
        "active":        True,
        "mode":          _focus_state["mode"],
        "cycle":         _focus_state["cycle"],
        "total_cycles":  _focus_state["total_cycles"],
        "remaining_sec": remaining,
        "goal":          _focus_state["session_goal"],
    }


def get_focus_sessions() -> list[dict]:
    """Return all completed focus sessions."""
    return _sessions


# ── Pomodoro loop ─────────────────────────────────────────────────────────────

def _pomodoro_loop():
    """Run Pomodoro cycles in background thread."""
    while not _focus_state["stop_flag"]:
        cycle  = _focus_state["cycle"]
        total  = _focus_state["total_cycles"]
        f_min  = _focus_state["focus_minutes"]
        b_min  = _focus_state["break_minutes"]
        lb_min = _focus_state["long_break_min"]

        # ── Focus period ──────────────────────────────────────────────────
        _focus_state["mode"]        = "focus"
        _focus_state["cycle_start"] = datetime.now()

        _speak(f"Cycle {cycle} of {total}. Focus time — {f_min} minutes. You've got this, Sir.")
        _send_notification("🎯 Focus Time", f"Cycle {cycle}/{total} — {f_min} minutes. Go!")

        _wait_minutes(f_min)
        if _focus_state["stop_flag"]:
            break

        # ── Break period ──────────────────────────────────────────────────
        is_long_break = (cycle % 4 == 0)
        break_time    = lb_min if is_long_break else b_min
        break_label   = "long break" if is_long_break else "short break"

        _focus_state["mode"]        = "break"
        _focus_state["cycle_start"] = datetime.now()

        _speak(f"Great work, Sir! Time for a {break_label} — {break_time} minutes.")
        _send_notification("☕ Break Time", f"{break_label.title()} — {break_time} minutes. Relax!")

        _wait_minutes(break_time)
        if _focus_state["stop_flag"]:
            break

        # ── Advance cycle ─────────────────────────────────────────────────
        _focus_state["cycle"] += 1
        if _focus_state["cycle"] > total:
            # All cycles done
            _focus_state["active"]    = False
            _focus_state["stop_flag"] = True
            report = _generate_report()
            _sessions.append(report)
            _set_dnd(False)
            _speak(
                f"All {total} Pomodoro cycles complete! "
                f"You focused for {report['total_focus_min']} minutes today. "
                f"Excellent work, Sir!"
            )
            _send_notification("✅ Session Complete!", f"{total} cycles done — {report['total_focus_min']}m focused")
            break


def _wait_minutes(minutes: int):
    """Wait for N minutes, checking stop flag every second."""
    end = time.time() + minutes * 60
    while time.time() < end and not _focus_state["stop_flag"]:
        time.sleep(1)


# ── App blocking ──────────────────────────────────────────────────────────────

def _close_distracting_apps() -> list[str]:
    """Kill distracting apps."""
    closed = []
    for app in DISTRACTING_APPS:
        proc = app.lower().replace(" ", "")
        try:
            result = subprocess.run(
                ["taskkill", "/F", "/IM", f"{proc}.exe"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                closed.append(app)
                log.info(f"Closed: {app}")
        except Exception:
            pass
    _focus_state["blocked_apps"] = closed
    return closed


# ── Windows Do Not Disturb ────────────────────────────────────────────────────

def _set_dnd(enable: bool):
    """Toggle Windows Focus Assist via registry."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current\default$windows.data.notifications.quiethourssettings",
            0, winreg.KEY_WRITE,
        )
        # Focus Assist value: 1 = alarms only, 0 = off
        winreg.SetValueEx(key, "Data", 0, winreg.REG_BINARY, b'\x02' if enable else b'\x00')
        winreg.CloseKey(key)
        log.info(f"DND {'enabled' if enable else 'disabled'}")
    except Exception as e:
        log.warning(f"Could not set DND (registry): {e}")
        # Fallback: just log it
        pass


# ── Report generation ─────────────────────────────────────────────────────────

def _generate_report() -> dict:
    """Generate focus session productivity report."""
    if not _focus_state["session_start"]:
        return {}

    total_elapsed = int((datetime.now() - _focus_state["session_start"]).total_seconds() / 60)
    cycles_done   = max(0, _focus_state["cycle"] - 1)
    focus_min     = cycles_done * _focus_state["focus_minutes"]
    break_min     = max(0, total_elapsed - focus_min)

    report = {
        "date":             datetime.now().strftime("%Y-%m-%d %H:%M"),
        "goal":             _focus_state["session_goal"],
        "cycles_completed": cycles_done,
        "total_cycles":     _focus_state["total_cycles"],
        "total_focus_min":  focus_min,
        "total_break_min":  break_min,
        "total_elapsed_min":total_elapsed,
        "blocked_apps":     _focus_state["blocked_apps"],
        "efficiency":       f"{int((focus_min / max(1, total_elapsed)) * 100)}%",
    }

    # AI insight via Bedrock
    try:
        report["ai_insight"] = _get_ai_insight(report)
    except Exception:
        report["ai_insight"] = ""

    return report


def _get_ai_insight(report: dict) -> str:
    """Get a short motivational/analytical insight from Bedrock."""
    try:
        client = boto3.client("bedrock-runtime", region_name=REGION)
        prompt = f"""Give a 1-sentence motivational productivity insight for this focus session:
Cycles completed: {report['cycles_completed']}/{report['total_cycles']}
Focus time: {report['total_focus_min']} minutes
Goal: {report.get('goal', 'Not set')}
Efficiency: {report['efficiency']}
Keep it encouraging and specific."""

        body = {
            "schemaVersion": "messages-v1",
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": 100, "temperature": 0.7},
        }
        resp   = client.invoke_model(modelId=MODEL_ID, body=json.dumps(body),
                                     contentType="application/json", accept="application/json")
        result = json.loads(resp["body"].read())
        return result["output"]["message"]["content"][0]["text"].strip()
    except Exception:
        return ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _speak(text: str):
    try:
        from controllers.voice_output_controller import speak
        speak(text)
    except Exception as e:
        log.warning(f"Speak failed: {e}")


def _send_notification(title: str, message: str):
    try:
        from controllers.notification_controller import notify
        notify(title, message)
    except Exception as e:
        log.warning(f"Notification failed: {e}")
