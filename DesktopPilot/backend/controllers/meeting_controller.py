"""
Meeting Controller — Real-time meeting transcription + AI action items.
Records system audio/mic, transcribes via AWS Transcribe, extracts action items
via Bedrock, generates a .docx meeting notes file, and optionally emails summary.
"""

import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime

import boto3
import pyaudio
import wave
import pyperclip

log = logging.getLogger(__name__)

REGION     = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
MODEL_ID   = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")
S3_BUCKET  = os.getenv("S3_BUCKET_NAME", "desktoppilot-audio")
DESKTOP    = os.path.join(os.path.expanduser("~"), "Desktop")

# ── Recording state ──────────────────────────────────────────────────────────

_meeting_state = {
    "active":     False,
    "start_time": None,
    "title":      "",
    "chunks":     [],       # raw audio chunks
    "thread":     None,
    "stop_flag":  False,
}

# ── Start/Stop recording ─────────────────────────────────────────────────────

def start_meeting(title: str = "") -> str:
    """Start recording microphone audio for the meeting."""
    if _meeting_state["active"]:
        return "Meeting recording is already active"

    _meeting_state["active"]     = True
    _meeting_state["start_time"] = datetime.now()
    _meeting_state["title"]      = title or f"Meeting_{datetime.now().strftime('%Y%m%d_%H%M')}"
    _meeting_state["chunks"]     = []
    _meeting_state["stop_flag"]  = False

    t = threading.Thread(target=_record_loop, daemon=True)
    _meeting_state["thread"] = t
    t.start()

    log.info(f"Meeting recording started: {_meeting_state['title']}")
    return f"Meeting recording started — '{_meeting_state['title']}'. Say 'end meeting' when done."


def stop_meeting() -> dict:
    """Stop recording and return the saved audio path + duration."""
    if not _meeting_state["active"]:
        return {"error": "No active meeting recording"}

    _meeting_state["stop_flag"] = True
    _meeting_state["active"]    = False

    # Wait for thread to finish
    if _meeting_state["thread"]:
        _meeting_state["thread"].join(timeout=5)

    duration = int((datetime.now() - _meeting_state["start_time"]).total_seconds())
    title    = _meeting_state["title"]

    # Save WAV file
    wav_path = _save_wav(title)
    log.info(f"Meeting stopped: {duration}s — saved to {wav_path}")

    return {
        "title":    title,
        "duration": duration,
        "wav_path": wav_path,
    }


def get_meeting_status() -> dict:
    """Return current recording status."""
    if not _meeting_state["active"]:
        return {"active": False}

    elapsed = int((datetime.now() - _meeting_state["start_time"]).total_seconds())
    return {
        "active":   True,
        "title":    _meeting_state["title"],
        "elapsed":  elapsed,
        "chunks":   len(_meeting_state["chunks"]),
    }


# ── Process meeting: transcribe → summarize → create notes ──────────────────

async def process_meeting(wav_path: str, title: str, send_email_to: str = "") -> dict:
    """
    Full pipeline:
    1. Upload WAV to S3
    2. Transcribe via AWS Transcribe
    3. Extract action items via Bedrock
    4. Create .docx notes file
    5. Optionally email summary
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _process_sync, wav_path, title, send_email_to)
    return result


def _process_sync(wav_path: str, title: str, send_email_to: str) -> dict:
    # Step 1: Transcribe
    log.info("Transcribing meeting audio...")
    transcript = _transcribe_wav(wav_path)
    if not transcript:
        return {"error": "Transcription returned empty — check audio quality"}

    log.info(f"Transcript length: {len(transcript)} chars")

    # Step 2: Extract action items via Bedrock
    log.info("Extracting action items via Bedrock...")
    analysis = _analyze_with_bedrock(transcript, title)

    # Step 3: Create .docx notes
    log.info("Creating meeting notes document...")
    doc_path = _create_docx(title, transcript, analysis)

    # Step 4: Copy summary to clipboard
    summary_text = _format_summary(title, analysis)
    pyperclip.copy(summary_text)

    # Step 5: Optional email
    email_result = ""
    if send_email_to:
        try:
            from controllers.browser_controller import open_gmail_compose
            import asyncio
            asyncio.run(open_gmail_compose(
                to=send_email_to,
                subject=f"Meeting Notes: {title}",
                body=summary_text,
            ))
            email_result = f"Summary email opened for {send_email_to}"
        except Exception as e:
            email_result = f"Email failed: {e}"

    log.info(f"Meeting processed: {doc_path}")

    return {
        "title":        title,
        "transcript":   transcript[:500] + "..." if len(transcript) > 500 else transcript,
        "summary":      analysis.get("summary", ""),
        "action_items": analysis.get("action_items", []),
        "decisions":    analysis.get("decisions", []),
        "attendees":    analysis.get("attendees", []),
        "doc_path":     doc_path,
        "email":        email_result,
    }


# ── Audio recording loop ─────────────────────────────────────────────────────

RATE    = 16000
CHUNK   = 1024
FORMAT  = pyaudio.paInt16
CHANNELS = 1

def _record_loop():
    """Record microphone audio in a background thread."""
    try:
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )
        log.info("Audio recording started")

        while not _meeting_state["stop_flag"]:
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                _meeting_state["chunks"].append(data)
            except Exception:
                break

        stream.stop_stream()
        stream.close()
        pa.terminate()
        log.info(f"Audio recording stopped — {len(_meeting_state['chunks'])} chunks")
    except Exception as e:
        log.error(f"Audio recording failed: {e}")
        _meeting_state["active"] = False


def _save_wav(title: str) -> str:
    """Save recorded chunks to a WAV file on Desktop."""
    os.makedirs(DESKTOP, exist_ok=True)
    filename = f"{title}.wav"
    filepath = os.path.join(DESKTOP, filename)

    try:
        pa = pyaudio.PyAudio()
        with wave.open(filepath, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(pa.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b"".join(_meeting_state["chunks"]))
        pa.terminate()
        log.info(f"WAV saved: {filepath}")
        return filepath
    except Exception as e:
        log.error(f"Failed to save WAV: {e}")
        return ""


# ── Transcription ─────────────────────────────────────────────────────────────

def _transcribe_wav(wav_path: str) -> str:
    """Upload WAV to S3 → start Transcribe job → poll → return text."""
    if not os.path.exists(wav_path):
        return ""

    s3    = boto3.client("s3", region_name=REGION)
    tc    = boto3.client("transcribe", region_name=REGION)
    key   = f"meetings/{os.path.basename(wav_path)}"
    job   = f"meeting_{int(time.time())}"

    try:
        # Upload to S3
        s3.upload_file(wav_path, S3_BUCKET, key)
        s3_uri = f"s3://{S3_BUCKET}/{key}"
        log.info(f"Uploaded to S3: {s3_uri}")

        # Start transcription job
        tc.start_transcription_job(
            TranscriptionJobName=job,
            Media={"MediaFileUri": s3_uri},
            MediaFormat="wav",
            LanguageCode="en-US",
        )

        # Poll until complete (max 5 minutes)
        for _ in range(150):
            time.sleep(2)
            resp   = tc.get_transcription_job(TranscriptionJobName=job)
            status = resp["TranscriptionJob"]["TranscriptionJobStatus"]
            if status == "COMPLETED":
                uri  = resp["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
                import requests
                text = requests.get(uri).json()["results"]["transcripts"][0]["transcript"]
                log.info(f"Transcription complete: {len(text)} chars")
                return text
            elif status == "FAILED":
                reason = resp["TranscriptionJob"].get("FailureReason", "Unknown")
                log.error(f"Transcription failed: {reason}")
                return ""

        return ""
    except Exception as e:
        log.error(f"Transcription error: {e}")
        return ""


# ── Bedrock analysis ──────────────────────────────────────────────────────────

def _analyze_with_bedrock(transcript: str, title: str) -> dict:
    """Send transcript to Bedrock → extract structured meeting data."""
    client = boto3.client("bedrock-runtime", region_name=REGION)

    prompt = f"""You are an expert meeting analyst. Analyze this meeting transcript and extract:
1. A 3-sentence summary
2. Action items (who needs to do what, with deadline if mentioned)
3. Key decisions made
4. Attendee names (if mentioned)

Meeting title: {title}
Transcript:
{transcript[:4000]}

Return ONLY valid JSON in this exact format:
{{
  "summary": "3 sentence summary of the meeting",
  "action_items": ["Person: action item by date", "..."],
  "decisions": ["Decision 1", "Decision 2"],
  "attendees": ["Name1", "Name2"]
}}"""

    try:
        body = {
            "schemaVersion": "messages-v1",
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": 1024, "temperature": 0.1},
        }

        resp = client.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(resp["body"].read())
        text   = result["output"]["message"]["content"][0]["text"].strip()

        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        log.error(f"Bedrock analysis failed: {e}")

    return {
        "summary":      "Meeting recorded and transcribed.",
        "action_items": [],
        "decisions":    [],
        "attendees":    [],
    }


# ── Create .docx notes ────────────────────────────────────────────────────────

def _create_docx(title: str, transcript: str, analysis: dict) -> str:
    """Create a properly formatted Word document with meeting notes."""
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()

        # Title
        heading = doc.add_heading(title, 0)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Metadata
        doc.add_paragraph(f"Date: {datetime.now().strftime('%B %d, %Y %I:%M %p')}")
        doc.add_paragraph("")

        # Summary
        doc.add_heading("Executive Summary", level=1)
        doc.add_paragraph(analysis.get("summary", ""))
        doc.add_paragraph("")

        # Attendees
        attendees = analysis.get("attendees", [])
        if attendees:
            doc.add_heading("Attendees", level=1)
            for a in attendees:
                doc.add_paragraph(f"• {a}")
            doc.add_paragraph("")

        # Action Items
        doc.add_heading("Action Items", level=1)
        action_items = analysis.get("action_items", [])
        if action_items:
            for item in action_items:
                p = doc.add_paragraph()
                p.add_run("☐ ").bold = True
                p.add_run(item)
        else:
            doc.add_paragraph("No action items identified.")
        doc.add_paragraph("")

        # Decisions
        doc.add_heading("Key Decisions", level=1)
        decisions = analysis.get("decisions", [])
        if decisions:
            for d in decisions:
                doc.add_paragraph(f"✓ {d}")
        else:
            doc.add_paragraph("No key decisions recorded.")
        doc.add_paragraph("")

        # Full transcript
        doc.add_heading("Full Transcript", level=1)
        # Split into paragraphs for readability
        for para in transcript.split(". "):
            if para.strip():
                doc.add_paragraph(para.strip() + ".")

        # Save
        safe_title = "".join(c for c in title if c.isalnum() or c in " _-")
        filename   = f"{safe_title}_Notes.docx"
        filepath   = os.path.join(DESKTOP, filename)
        doc.save(filepath)

        # Open in Word
        os.startfile(filepath)
        log.info(f"Meeting notes saved: {filepath}")
        return filepath

    except Exception as e:
        log.error(f"Failed to create meeting notes: {e}")
        return ""


def _format_summary(title: str, analysis: dict) -> str:
    """Format plain-text summary for clipboard/email."""
    lines = [
        f"MEETING NOTES: {title}",
        f"Date: {datetime.now().strftime('%B %d, %Y %I:%M %p')}",
        "",
        "SUMMARY",
        analysis.get("summary", ""),
        "",
        "ACTION ITEMS",
    ]
    for item in analysis.get("action_items", ["None identified"]):
        lines.append(f"  □ {item}")
    lines += [
        "",
        "KEY DECISIONS",
    ]
    for d in analysis.get("decisions", ["None recorded"]):
        lines.append(f"  ✓ {d}")
    return "\n".join(lines)
