"""
Wake Word Listener — openwakeword (fully free, no API key, 100% local)

Detects "Hey Jarvis" (used as "Hey Cipher" proxy) or any built-in model.
Runs as a background process spawned by Electron main.js.

Install:
    pip install openwakeword pyaudio

Output (stdout — IPC to Electron):
    WAKE_READY
    WAKE_DETECTED
    WAKE_ERROR:<message>
"""

import sys
import os
import time
import struct
import logging

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)


def _signal(msg: str):
    """Send IPC signal to Electron via stdout."""
    print(msg, flush=True)


def run():
    # ── Check dependencies ────────────────────────────────────────────────
    try:
        import pyaudio
    except ImportError:
        _signal("WAKE_ERROR:pyaudio not installed. Run: pip install pyaudio")
        sys.exit(1)

    try:
        from openwakeword.model import Model
    except ImportError:
        _signal("WAKE_ERROR:openwakeword not installed. Run: pip install openwakeword")
        sys.exit(1)

    # ── Load model ────────────────────────────────────────────────────────
    # Built-in models (no download needed after first run):
    #   "hey_jarvis"   — closest to "Hey Cipher" acoustically
    #   "alexa"        — very reliable, good for demos
    #   "hey_mycroft"  — another option
    #
    # To train a custom "Hey Cipher" model (free):
    #   https://github.com/dscripka/openWakeWord#training-new-models
    #
    # Set WAKE_WORD_MODEL in .env to override (e.g. "alexa" or path to .tflite)
    model_name = os.getenv("WAKE_WORD_MODEL", "hey_jarvis")

    # Check if it's a custom model file path
    if os.path.exists(model_name):
        # Custom .tflite model file
        try:
            oww_model = Model(
                wakeword_models=[model_name],
                inference_framework="tflite",
            )
            display_name = os.path.basename(model_name).replace(".tflite", "")
        except Exception as e:
            _signal(f"WAKE_ERROR:Failed to load custom model '{model_name}': {e}")
            sys.exit(1)
    else:
        # Built-in model by name
        try:
            oww_model = Model(
                wakeword_models=[model_name],
                inference_framework="tflite",
            )
            display_name = model_name
        except Exception as e:
            _signal(f"WAKE_ERROR:Failed to load model '{model_name}': {e}. Try: hey_jarvis, alexa, hey_mycroft")
            sys.exit(1)

    # ── Open microphone ───────────────────────────────────────────────────
    SAMPLE_RATE   = 16000
    FRAME_SIZE    = 1280   # openwakeword expects 80ms chunks at 16kHz
    CHANNELS      = 1
    FORMAT        = pyaudio.paInt16

    pa = pyaudio.PyAudio()
    try:
        stream = pa.open(
            rate=SAMPLE_RATE,
            channels=CHANNELS,
            format=FORMAT,
            input=True,
            frames_per_buffer=FRAME_SIZE,
        )
    except Exception as e:
        _signal(f"WAKE_ERROR:Cannot open microphone: {e}")
        pa.terminate()
        sys.exit(1)

    # Sensitivity — 0.0 (very sensitive, many false positives) to 1.0 (strict)
    THRESHOLD = float(os.getenv("WAKE_WORD_THRESHOLD", "0.5"))

    _signal("WAKE_READY")
    log.warning(f"Wake word listener ready — model: {display_name}, threshold: {THRESHOLD}")

    # Cooldown to prevent double-triggers
    last_trigger = 0.0
    COOLDOWN_SEC = 2.0

    try:
        while True:
            # Read audio chunk
            try:
                pcm = stream.read(FRAME_SIZE, exception_on_overflow=False)
            except OSError:
                time.sleep(0.1)
                continue

            # Convert bytes to int16 array
            audio_data = struct.unpack(f"{FRAME_SIZE}h", pcm)

            # Run wake word detection
            prediction = oww_model.predict(list(audio_data))

            # Check all models in the prediction dict
            for model_key, score in prediction.items():
                if score >= THRESHOLD:
                    now = time.time()
                    if now - last_trigger >= COOLDOWN_SEC:
                        last_trigger = now
                        _signal("WAKE_DETECTED")
                        log.warning(f"Wake word detected! model={model_key}, score={score:.3f}")
                        # Reset model state to avoid repeated triggers
                        oww_model.reset()
                        break

    except KeyboardInterrupt:
        pass
    except Exception as e:
        _signal(f"WAKE_ERROR:{e}")
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


if __name__ == "__main__":
    run()
