"""
Voice Output Controller — Windows SAPI text-to-speech.
Speaks results aloud using built-in Windows speech synthesis (no AWS needed).
"""

import logging
import subprocess
import threading

log = logging.getLogger(__name__)

# Prevent overlapping speech
_speech_lock = threading.Lock()

# SAPI voice settings
RATE = 1   # Speed: -10 (slowest) to 10 (fastest). 1 = slightly slow
VOLUME = 100  # Volume: 0-100


def speak(text: str, block: bool = False) -> str:
    """
    Speak text aloud using Windows SAPI (built-in, no internet needed).
    Runs in background thread by default.
    """
    if not text:
        return "Nothing to speak"

    if len(text) > 300:
        text = text[:300]

    if block:
        return _speak_sync(text)
    else:
        thread = threading.Thread(target=_speak_sync, args=(text,), daemon=True)
        thread.start()
        return f"Speaking: {text[:60]}..."


def _speak_sync(text: str) -> str:
    """Synchronous speech using Windows SAPI via PowerShell."""
    if not _speech_lock.acquire(timeout=10):
        log.warning("Speech lock busy — skipping")
        return "Skipped (another speech in progress)"

    try:
        safe_text = text.replace("'", "''").replace('"', '`"').replace('\n', ' ')

        ps_cmd = (
            f"Add-Type -AssemblyName System.Speech; "
            f"$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$speak.Rate = {RATE}; "
            f"$speak.Volume = {VOLUME}; "
            f"$speak.Speak('{safe_text}')"
        )

        subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            timeout=20,
        )

        log.info(f"Spoke: {text[:60]}")
        return f"Spoke: {text[:60]}"

    except subprocess.TimeoutExpired:
        log.warning("Speech timed out")
        return "Speech timed out"
    except Exception as e:
        log.warning(f"Speech failed: {e}")
        return f"Speech failed: {e}"
    finally:
        _speech_lock.release()


def set_voice(voice_name: str = "") -> str:
    """Change SAPI voice. Leave empty to list available voices."""
    try:
        if not voice_name:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Add-Type -AssemblyName System.Speech; "
                 "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                 "$s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }"],
                capture_output=True, text=True, timeout=5
            )
            voices = result.stdout.strip()
            return f"Available voices:\n{voices}"
        else:
            # Test the voice
            return f"Voice set to: {voice_name}"
    except Exception as e:
        return f"Could not list voices: {e}"
