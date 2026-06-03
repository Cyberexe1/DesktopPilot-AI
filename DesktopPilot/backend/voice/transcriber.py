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
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")

s3_client         = boto3.client("s3", region_name=REGION)
transcribe_client = boto3.client("transcribe", region_name=REGION)

# Lazy-load Whisper model (loads on first use)
_whisper_model = None


def _get_whisper_model():
    """Load Faster Whisper model on first use (takes 2-3 seconds first time)."""
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            log.info(f"Loading Faster Whisper model: {WHISPER_MODEL}...")
            _whisper_model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
            log.info("Faster Whisper model loaded ✓")
        except Exception as e:
            log.warning(f"Faster Whisper unavailable: {e}")
            _whisper_model = None
    return _whisper_model


async def transcribe_audio_bytes(audio_bytes: bytes) -> str:
    """
    Transcribe audio bytes to text.
    Strategy: Faster Whisper (local, fast) → Amazon Transcribe (fallback)
    """
    loop = asyncio.get_event_loop()

    # Try Faster Whisper first (local, instant)
    try:
        text = await loop.run_in_executor(None, _whisper_transcribe, audio_bytes)
        if text and len(text.strip()) > 0:
            return text
    except Exception as e:
        log.warning(f"Faster Whisper failed: {e}, falling back to Amazon Transcribe")

    # Fallback: Amazon Transcribe
    log.info("Using Amazon Transcribe fallback...")
    return await loop.run_in_executor(None, _transcribe_aws, audio_bytes)


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

        # Transcribe
        segments, info = model.transcribe(
            temp_path,
            language="en",
            beam_size=5,
            vad_filter=True,  # Filter out silence
        )

        # Collect all text segments
        text = " ".join(segment.text.strip() for segment in segments)

        elapsed = time.time() - start
        log.info(f"Whisper transcribed in {elapsed:.1f}s: {text[:80]}")
        return text.strip()

    finally:
        # Clean up temp file
        try:
            os.unlink(temp_path)
        except Exception:
            pass


def _transcribe_aws(audio_bytes: bytes) -> str:
    """Fallback: Amazon Transcribe (requires internet + AWS credentials)."""
    job_name = f"dp-{uuid.uuid4().hex[:12]}"
    s3_key   = f"audio/{job_name}.webm"

    # Upload to S3
    log.info(f"Uploading audio to S3...")
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=audio_bytes,
        ContentType="audio/webm",
    )

    audio_uri = f"s3://{S3_BUCKET}/{s3_key}"

    # Start transcription job
    log.info(f"Starting Transcribe job: {job_name}")
    transcribe_client.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": audio_uri},
        MediaFormat="webm",
        LanguageCode="en-US",
    )

    # Poll until complete (max 60s)
    for _ in range(30):
        time.sleep(2)
        response = transcribe_client.get_transcription_job(
            TranscriptionJobName=job_name
        )
        status = response["TranscriptionJob"]["TranscriptionJobStatus"]

        if status == "COMPLETED":
            transcript_uri = response["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
            with urllib.request.urlopen(transcript_uri) as f:
                result = json.loads(f.read())
            text = result["results"]["transcripts"][0]["transcript"]
            log.info(f"Transcribe result: {text}")
            return text

        if status == "FAILED":
            reason = response["TranscriptionJob"].get("FailureReason", "Unknown")
            raise RuntimeError(f"Transcription failed: {reason}")

    raise TimeoutError("Transcription timed out after 60 seconds")
