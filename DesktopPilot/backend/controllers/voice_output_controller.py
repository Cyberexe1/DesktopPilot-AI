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
                    engine.setProperty("rate", 175)
                    engine.setProperty("volume", 0.92)
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
    """Blocking speech — waits until SAPI finishes speaking."""
    if not text or not text.strip():
        return "Nothing to speak"
    text = text.strip()
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
    Always uses PowerShell SAPI to avoid pyttsx3 run-loop conflicts
    when the main thread engine is already active.
    """
    if not text or not text.strip():
        return

    def _speak_thread():
        _fallback_speak(text)

    t = threading.Thread(target=_speak_thread, daemon=True)
    t.start()
    log.info(f"Non-blocking speak queued: '{text.strip()[:60]}'")


def _fallback_speak(text: str):
    """Windows SAPI via PowerShell — no Python dependency, no loop conflicts."""
    import subprocess
    try:
        ps_script = (
            'Add-Type -AssemblyName System.Speech; '
            '$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
            f'$s.Speak("{text[:200]}")'
        )
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
    except Exception as e:
        log.error(f"Fallback speak also failed: {e}")
