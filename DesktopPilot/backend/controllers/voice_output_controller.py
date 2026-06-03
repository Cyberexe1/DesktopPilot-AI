"""
Voice Output Controller — Amazon Polly text-to-speech.
Speaks results aloud after command execution.
"""

import io
import logging
import os
import tempfile
import threading

import boto3

log = logging.getLogger(__name__)

REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# Polly voice settings
VOICE_ID = "Kajal"         # Indian English female (neural — best quality)
ENGINE   = "neural"        # "neural" (better quality) or "standard" (cheaper) or "generative" (best)

polly_client = boto3.client("polly", region_name=REGION)

# Prevent overlapping speech
_speech_lock = threading.Lock()


def speak(text: str, voice: str = VOICE_ID, block: bool = False) -> str:
    """
    Convert text to speech using Amazon Polly and play through speakers.
    Only one speech plays at a time (prevents overlapping voices).
    """
    if not text:
        return "Nothing to speak"

    # Truncate very long text
    if len(text) > 500:
        text = text[:500] + "..."

    if block:
        return _speak_sync(text, voice)
    else:
        thread = threading.Thread(target=_speak_sync, args=(text, voice), daemon=True)
        thread.start()
        return f"Speaking: {text[:60]}..."


def _speak_sync(text: str, voice: str) -> str:
    """Synchronous speech synthesis + playback. Thread-safe."""
    if not _speech_lock.acquire(timeout=10):
        log.warning("Speech lock busy — skipping")
        return "Skipped (another speech in progress)"

    try:
        # Call Amazon Polly — use SSML for speed and volume control
        ssml_text = f'<speak><prosody rate="95%" volume="loud">{text}</prosody></speak>'

        response = polly_client.synthesize_speech(
            Text=ssml_text,
            TextType="ssml",
            OutputFormat="mp3",
            VoiceId=voice,
            Engine=ENGINE,
        )

        # Save audio to temp file
        audio_stream = response["AudioStream"].read()
        temp_file = os.path.join(tempfile.gettempdir(), "desktoppilot_speech.mp3")

        with open(temp_file, "wb") as f:
            f.write(audio_stream)

        # Play the audio
        _play_audio(temp_file)

        log.info(f"Spoke: {text[:60]}")
        return f"Spoke: {text[:60]}"

    except Exception as e:
        log.warning(f"Polly speech failed: {e}")
        # Fallback: use Windows built-in TTS
        result = _fallback_tts(text)
        return result
    finally:
        _speech_lock.release()


def _play_audio(filepath: str):
    """Play MP3 audio silently using pygame (no external player window)."""
    try:
        import pygame

        if not pygame.mixer.get_init():
            pygame.mixer.init()

        pygame.mixer.music.load(filepath)
        pygame.mixer.music.set_volume(1.0)
        pygame.mixer.music.play()

        # Wait until playback finishes
        while pygame.mixer.music.get_busy():
            import time
            time.sleep(0.1)

    except Exception as e:
        log.warning(f"Pygame audio failed: {e}")
        # Last resort fallback: Windows SAPI (no file needed)
        pass


def _fallback_tts(text: str) -> str:
    """Fallback: use Windows SAPI (built-in TTS) if Polly fails."""
    import subprocess

    try:
        # Windows built-in speech synthesis via PowerShell
        safe_text = text.replace("'", "''").replace('"', '`"')
        subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command",
             f"Add-Type -AssemblyName System.Speech; "
             f"$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
             f"$speak.Rate = 1; "
             f"$speak.Speak('{safe_text}')"],
            capture_output=True, timeout=20
        )
        log.info(f"Fallback TTS spoke: {text[:40]}")
        return f"Spoke (fallback): {text[:60]}"
    except Exception as e:
        log.warning(f"Fallback TTS also failed: {e}")
        return f"Could not speak: {text[:60]}"


def set_voice(voice_id: str) -> str:
    """Change the Polly voice. Options: Joanna, Matthew, Amy, Brian, Aditi."""
    global VOICE_ID
    valid = ["Joanna", "Matthew", "Amy", "Brian", "Aditi", "Ivy", "Kendra", "Salli"]
    if voice_id in valid:
        VOICE_ID = voice_id
        return f"Voice changed to {voice_id}"
    return f"Invalid voice. Options: {', '.join(valid)}"
