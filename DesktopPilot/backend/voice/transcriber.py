"""
Voice transcription — Faster Whisper (local, instant) with Amazon Transcribe fallback.

Primary: Faster Whisper (small model) — runs locally, 1-3 seconds, free
Fallback: Amazon Transcribe — used if Whisper fails or is unavailable
"""

import asyncio
import io
import json
import logging
import os
import tempfile
import time
import uuid
import urllib.request

import boto3

log = logging.getLogger(__name__)

S3_BUCKET = os.getenv("S3_BUCKET_NAME", "desktoppilot-audio")
REGION    = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium")

s3_client         = boto3.client("s3", region_name=REGION)
transcribe_client = boto3.client("transcribe", region_name=REGION)

# Lazy-load Whisper model (loads on first use)
_whisper_model = None


def _get_whisper_model():
    """Load Faster Whisper model on first use (takes 2-3 seconds first time)."""
    global _whisper_model
    if _whisper_model is None:
        try:
            if WHISPER_MODEL == "disabled":
                return None
            from faster_whisper import WhisperModel
            log.info(f"Loading Faster Whisper model: {WHISPER_MODEL}...")
            _whisper_model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
            log.info("Faster Whisper model loaded ✓")
        except Exception as e:
            log.warning(f"Faster Whisper unavailable: {e}")
            _whisper_model = None
    return _whisper_model


def _convert_to_wav(audio_bytes: bytes) -> bytes:
    """
    Convert any audio format (webm, ogg, mp4, etc.) to 16kHz mono WAV.
    WAV is the format Whisper and Transcribe both work best with.
    Fast — typically 0.1-0.2 seconds.
    """
    import av
    import io
    import array

    try:
        # Read input audio
        input_buf = io.BytesIO(audio_bytes)
        output_buf = io.BytesIO()

        input_container = av.open(input_buf)
        output_container = av.open(output_buf, mode='w', format='wav')

        # Create output stream: 16kHz mono PCM s16
        output_stream = output_container.add_stream('pcm_s16le', rate=16000, layout='mono')

        for frame in input_container.decode(audio=0):
            frame.pts = None
            # Resample to 16kHz mono
            for packet in output_stream.encode(frame.reformat(
                sample_rate=16000,
                format='s16',
                layout='mono'
            )):
                output_container.mux(packet)

        # Flush remaining
        for packet in output_stream.encode(None):
            output_container.mux(packet)

        output_container.close()
        input_container.close()

        wav_bytes = output_buf.getvalue()
        log.info(f"Audio converted to WAV: {len(audio_bytes)} → {len(wav_bytes)} bytes")
        return wav_bytes

    except Exception as e:
        log.warning(f"WAV conversion failed: {e} — using original audio")
        return audio_bytes


async def transcribe_audio_bytes(audio_bytes: bytes) -> str:
    """
    Transcribe audio bytes to text.
    Strategy: Convert to WAV → Faster Whisper (local) → Amazon Transcribe (fallback)
    """
    loop = asyncio.get_event_loop()

    # Convert to clean 16kHz mono WAV for best accuracy
    wav_bytes = await loop.run_in_executor(None, _convert_to_wav, audio_bytes)

    # Try Faster Whisper first (local, instant)
    try:
        text = await loop.run_in_executor(None, _whisper_transcribe, wav_bytes)
        if text and len(text.strip()) > 2:
            return text
        else:
            log.warning("Whisper returned empty/short result — falling back to Transcribe")
    except Exception as e:
        log.warning(f"Faster Whisper failed: {e}, falling back to Amazon Transcribe")

    # Fallback: Amazon Transcribe (send WAV — more reliable than webm)
    log.info("Using Amazon Transcribe fallback...")
    return await loop.run_in_executor(None, _transcribe_aws, wav_bytes, "wav")


def _whisper_transcribe(audio_bytes: bytes) -> str:
    """Transcribe using Faster Whisper (local model)."""
    model = _get_whisper_model()
    if model is None:
        raise RuntimeError("Whisper model not available")

    start = time.time()

    # Save audio to temp file (Whisper needs a file path)
    temp_path = os.path.join(tempfile.gettempdir(), f"whisper_{uuid.uuid4().hex[:8]}.webm")
    try:
        with open(temp_path, "wb") as f:
            f.write(audio_bytes)

        # Transcribe with improved settings for short commands
        segments, info = model.transcribe(
            temp_path,
            language="en",
            beam_size=5,
            best_of=5,
            temperature=0.0,       # Deterministic — no random sampling
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=300,   # More aggressive silence detection
                threshold=0.3,                 # Lower threshold = more sensitive
            ),
            condition_on_previous_text=False,  # Each command is independent
            initial_prompt="Open Chrome. Open YouTube. Volume up. Brightness down. Take a screenshot. Open VS Code. Search for Python tutorials.",  # Primes model with app commands
        )

        # Collect all text segments
        text = " ".join(segment.text.strip() for segment in segments)

        # Clean up common Whisper artifacts
        text = text.strip()
        text = text.strip(".")  # Remove trailing periods Whisper often adds
        text = text.strip()

        elapsed = time.time() - start
        log.info(f"Whisper transcribed in {elapsed:.1f}s: '{text}'")

        if not text:
            raise RuntimeError("Whisper returned empty transcript")

        return text

    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


def _transcribe_aws(audio_bytes: bytes, audio_format: str = "webm") -> str:
    """Fallback: Amazon Transcribe (requires internet + AWS credentials)."""
    job_name = f"dp-{uuid.uuid4().hex[:12]}"
    s3_key   = f"audio/{job_name}.{audio_format}"

    # Upload to S3 with retry on connection errors
    log.info(f"Uploading audio to S3...")
    content_types = {"wav": "audio/wav", "webm": "audio/webm", "mp3": "audio/mpeg"}
    for attempt in range(3):
        try:
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=audio_bytes,
                ContentType=content_types.get(audio_format, "audio/wav"),
            )
            break
        except Exception as e:
            if attempt < 2:
                log.warning(f"S3 upload attempt {attempt+1} failed: {e} — retrying in 2s")
                time.sleep(2)
            else:
                raise RuntimeError(f"S3 upload failed after 3 attempts: {e}")

    audio_uri = f"s3://{S3_BUCKET}/{s3_key}"

    # Start transcription job
    log.info(f"Starting Transcribe job: {job_name}")
    transcribe_client.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": audio_uri},
        MediaFormat=audio_format,
        LanguageCode="en-US",
    )

    # Poll until complete (max 60s)
    for _ in range(30):
        time.sleep(2)
        try:
            response = transcribe_client.get_transcription_job(
                TranscriptionJobName=job_name
            )
        except Exception as e:
            log.warning(f"Poll error: {e} — retrying")
            continue

        status = response["TranscriptionJob"]["TranscriptionJobStatus"]

        if status == "COMPLETED":
            transcript_uri = response["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
            with urllib.request.urlopen(transcript_uri) as f:
                result = json.loads(f.read())
            text = result["results"]["transcripts"][0]["transcript"]
            log.info(f"Transcribe result: {text}")
            # Clean up S3 audio file after transcription
            try:
                s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
            except Exception:
                pass
            return text

        if status == "FAILED":
            reason = response["TranscriptionJob"].get("FailureReason", "Unknown")
            raise RuntimeError(f"Transcription failed: {reason}")

    raise TimeoutError("Transcription timed out after 60 seconds")
