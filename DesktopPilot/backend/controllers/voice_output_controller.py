"""
Voice Output Controller — Windows SAPI Text-to-Speech

speak()             — blocking (waits until speech finishes)
speak_nonblocking() — fire-and-forget (returns immediately, speech in background thread)

Used by:
  • speak_acknowledgment() in pipeline.py — fires instantly while Bedrock is working
  • speak tool in executor.py — full blocking speech for final responses
"""

import logging
import threading

log = logging.getLogger(__name__)

# ── SAPI engine (lazy singleton) ──────────────────────────────────────────────

_sapi_lock = threading.Lock()
_sapi_engine = None


def _get_engine():
    global _sapi_engine
    if _sapi_engine is None:
        with _sapi_lock:
            if _sapi_engine is None:
                try:
                    import pyttsx3
                    engine = pyttsx3.init()
                    # Configure voice: slower rate for clarity, female voice preferred
                    engine.setProperty("rate", 175)    # words per minute (default ~200)
                    engine.setProperty("volume", 0.92)
                    # Try to select a natural-sounding voice
                    voices = engine.getProperty("voices")
                    for v in voices:
                        if "zira" in v.name.lower() or "female" in v.name.lower():
                            engine.setProperty("voice", v.id)
                            break
                    _sapi_engine = engine
                    log.info("SAPI engine initialized ✓")
                except Exception as e:
                    log.error(f"SAPI init failed: {e}")
                    return None
    return _sapi_engine


# ── Public API ────────────────────────────────────────────────────────────────

def speak(text: str) -> str:
    """
    Blocking speech — waits until SAPI finishes speaking.
    Use for final responses after task execution.
    """
    if not text or not text.strip():
        return "Nothing to speak"

    text = text.strip()
    # Truncate very long outputs (don't read entire system info aloud)
    if len(text) > 300:
        text = text[:300] + "..."

    try:
        engine = _get_engine()
        if engine is None:
            _fallback_speak(text)
            return f"Spoke (fallback): {text[:60]}"

        with _sapi_lock:
            engine.say(text)
            engine.runAndWait()

        log.info(f"Spoke: '{text[:60]}'")
        return f"Spoke: {text[:60]}"

    except Exception as e:
        log.warning(f"SAPI speak failed: {e} — trying fallback")
        _fallback_speak(text)
        return f"Spoke (fallback): {text[:60]}"


def speak_nonblocking(text: str):
    """
    Fire-and-forget speech — returns IMMEDIATELY.
    SAPI speaks in a background daemon thread.

    Use for:
      • Acknowledgment phrases ("Got it, Sir.") fired while Bedrock is planning
      • Any speech that should not block the main pipeline
    """
    if not text or not text.strip():
        return

    def _speak_thread():
        try:
            # CoInitialize is required for Windows COM (SAPI) in a background thread.
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:
                pass  # pythoncom not available — proceed anyway
            # Non-blocking uses a fresh pyttsx3 instance to avoid lock contention.
            # If pyttsx3's run loop is already active (e.g. main thread is speaking),
            # fall back to the PowerShell SAPI path which spawns a separate process
            # and never conflicts.
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 185)
            engine.setProperty("volume", 0.9)
            voices = engine.getProperty("voices")
            for v in voices:
                if "zira" in v.name.lower() or "female" in v.name.lower():
                    engine.setProperty("voice", v.id)
                    break
            engine.say(text.strip())
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            log.warning(f"Non-blocking speak failed: {e} — using PowerShell fallback")
            _fallback_speak(text)  # spawns its own process, no loop conflicts

    t = threading.Thread(target=_speak_thread, daemon=True)
    t.start()
    log.info(f"Non-blocking speak queued: '{text.strip()[:60]}'")


def _fallback_speak(text: str):
    """
    Windows SAPI via PowerShell — no Python dependency needed.
    Last resort fallback if pyttsx3 fails.
    """
    import subprocess
    try:
        ps_script = f'Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Speak("{text[:200]}")'
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
    except Exception as e:
        log.error(f"Fallback speak also failed: {e}")
