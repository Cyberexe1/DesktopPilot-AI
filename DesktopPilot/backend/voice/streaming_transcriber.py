"""
Low-latency transcription via Amazon Transcribe Streaming.

Unlike the batch API, this streams audio over a live connection — no S3 upload,
no polling, and results come back in ~1s. Credentials come from the default
chain (the App Runner instance role provides them automatically).
"""

import asyncio
import io
import logging

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000


def _to_pcm16(audio_bytes: bytes) -> bytes:
    """Decode any input audio to raw 16 kHz mono PCM s16le using PyAV."""
    import av

    inp = av.open(io.BytesIO(audio_bytes))
    resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    out = bytearray()

    for frame in inp.decode(audio=0):
        for rframe in resampler.resample(frame):
            out += rframe.to_ndarray().tobytes()
    # Flush the resampler
    for rframe in resampler.resample(None):
        out += rframe.to_ndarray().tobytes()

    inp.close()
    return bytes(out)


async def transcribe_stream(audio_bytes: bytes, region: str = "us-east-1") -> str:
    """
    Transcribe audio bytes using Amazon Transcribe Streaming.
    Returns the final transcript text. Raises on failure (caller may fall back).
    """
    from amazon_transcribe.client import TranscribeStreamingClient
    from amazon_transcribe.handlers import TranscriptResultStreamHandler

    pcm = _to_pcm16(audio_bytes)
    if not pcm:
        raise RuntimeError("No audio data after decoding")

    client = TranscribeStreamingClient(region=region)
    stream = await client.start_stream_transcription(
        language_code="en-US",
        media_sample_rate_hz=SAMPLE_RATE,
        media_encoding="pcm",
    )

    final_parts: list[str] = []

    class _Handler(TranscriptResultStreamHandler):
        async def handle_transcript_event(self, transcript_event):
            for result in transcript_event.transcript.results:
                if not result.is_partial and result.alternatives:
                    final_parts.append(result.alternatives[0].transcript)

    handler = _Handler(stream.output_stream)

    async def _write_chunks():
        chunk = 1024 * 8  # ~8KB per event
        for i in range(0, len(pcm), chunk):
            await stream.input_stream.send_audio_event(audio_chunk=pcm[i:i + chunk])
            await asyncio.sleep(0.005)
        await stream.input_stream.end_stream()

    await asyncio.gather(_write_chunks(), handler.handle_events())

    text = " ".join(p.strip() for p in final_parts if p.strip()).strip()
    log.info(f"Streaming transcript: '{text}'")
    return text
