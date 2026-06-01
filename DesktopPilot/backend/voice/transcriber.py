"""
Voice transcription via Amazon Transcribe.
Uploads audio to S3, starts a transcription job, polls for result.
"""

import asyncio
import json
import logging
import os
import time
import uuid
import urllib.request

import boto3

log = logging.getLogger(__name__)

S3_BUCKET   = os.getenv("S3_BUCKET_NAME", "desktoppilot-audio")
REGION      = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

s3_client         = boto3.client("s3", region_name=REGION)
transcribe_client = boto3.client("transcribe", region_name=REGION)


async def transcribe_audio_bytes(audio_bytes: bytes) -> str:
    """
    Upload raw audio bytes to S3, run a Transcribe job, return transcript text.
    Runs the blocking boto3 calls in a thread pool to stay async-friendly.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _transcribe_sync, audio_bytes)


def _transcribe_sync(audio_bytes: bytes) -> str:
    job_name = f"dp-{uuid.uuid4().hex[:12]}"
    s3_key   = f"audio/{job_name}.webm"

    # Upload to S3
    log.info(f"Uploading audio to s3://{S3_BUCKET}/{s3_key}")
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=audio_bytes,
        ContentType="audio/webm",
    )

    audio_uri = f"s3://{S3_BUCKET}/{s3_key}"

    # Start transcription job — use webm format
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
        log.info(f"Transcribe status: {status}")

        if status == "COMPLETED":
            transcript_uri = response["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
            with urllib.request.urlopen(transcript_uri) as f:
                result = json.loads(f.read())
            text = result["results"]["transcripts"][0]["transcript"]
            log.info(f"Transcript result: {text}")
            return text

        if status == "FAILED":
            reason = response["TranscriptionJob"].get("FailureReason", "Unknown")
            raise RuntimeError(f"Transcription failed: {reason}")

    raise TimeoutError("Transcription job timed out after 60 seconds")
