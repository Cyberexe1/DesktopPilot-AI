"""
Voice transcription — Amazon Transcribe Streaming only.

The old local Faster-Whisper path and the batch Amazon Transcribe path
(S3 upload + polling) have been removed. Transcription now streams audio
directly to Amazon Transcribe — no S3 storage, low latency.

`transcribe_audio_bytes` is kept as the public entry point so existing
callers (e.g. the local agent's /transcribe route) continue to work.
"""

import logging
import os

from voice.streaming_transcriber import transcribe_stream

log = logging.getLogger(__name__)

REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")


async def transcribe_audio_bytes(audio_bytes: bytes) -> str:
    """Transcribe audio bytes via Amazon Transcribe Streaming."""
    return await transcribe_stream(audio_bytes, region=REGION)
