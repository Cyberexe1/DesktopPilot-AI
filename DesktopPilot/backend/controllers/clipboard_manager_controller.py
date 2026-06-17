"""
AI Clipboard Manager — smart clipboard history with AI tagging.
Monitors clipboard changes, classifies content via Bedrock,
stores in SQLite, and answers natural language queries.
"""

import json
import logging
import os
import re
import threading
import time
from datetime import datetime

import boto3
import pyperclip

log = logging.getLogger(__name__)

REGION   = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")

# ── In-memory store (persisted to SQLite) ────────────────────────────────────

_history: list[dict] = []          # {id, text, tag, source, timestamp, preview}
_monitor_thread = None
_monitor_active = False
_last_clip = ""

MAX_HISTORY = 50

TAG_COLORS = {
    "code":    "#e8441a",
    "email":   "#ff5544",
    "url":     "#ff3322",
    "phone":   "#cc2200",
    "address": "#ff4433",
    "number":  "#ee3322",
    "text":    "#888888",
    "other":   "#555555",
}


# ── Start / Stop monitoring ──────────────────────────────────────────────────

def start_clipboard_monitor() -> str:
    """Start background clipboard monitoring thread."""
    global _monitor_thread, _monitor_active, _last_clip

    if _monitor_active:
        return "Clipboard monitor already running"

    _monitor_active = True
    _last_clip = _safe_paste()

    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    _monitor_thread.start()

    log.info("Clipboard monitor started")
    return "Clipboard monitor started — tracking all copies"


def stop_clipboard_monitor() -> str:
    """Stop background monitoring."""
    global _monitor_active
    _monitor_active = False
    log.info("Clipboard monitor stopped")
    return "Clipboard monitor stopped"


def get_monitor_status() -> dict:
    return {
        "active":  _monitor_active,
        "entries": len(_history),
    }


def _monitor_loop():
    """Poll clipboard every 600ms, detect changes."""
    global _last_clip

    while _monitor_active:
        try:
            current = _safe_paste()
            if current and current != _last_clip and len(current.strip()) > 1:
                _last_clip = current
                _add_entry(current)
        except Exception:
            pass
        time.sleep(0.6)


# ── Add & tag entries ─────────────────────────────────────────────────────────

def _add_entry(text: str):
    """Add new clipboard entry with AI tag."""
    tag     = _classify_fast(text)
    preview = text[:80] + "..." if len(text) > 80 else text
    entry   = {
        "id":        len(_history) + 1,
        "text":      text,
        "tag":       tag,
        "preview":   preview,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "date":      datetime.now().strftime("%Y-%m-%d"),
        "length":    len(text),
    }
    _history.insert(0, entry)

    # Cap history
    if len(_history) > MAX_HISTORY:
        _history.pop()

    log.info(f"Clipboard entry added [{tag}]: {preview[:40]}")


def _classify_fast(text: str) -> str:
    """Fast rule-based classification — no API call needed."""
    t = text.strip()

    # URL
    if re.match(r'^https?://', t) or re.match(r'^www\.', t):
        return "url"

    # Email address
    if re.match(r'^[\w.+-]+@[\w-]+\.\w+$', t):
        return "email"

    # Phone number
    if re.match(r'^[\+\d\s\-\(\)]{7,15}$', t.replace(" ", "")):
        return "phone"

    # Code — check for common code patterns
    code_signals = [
        r'def ', r'function ', r'class ', r'import ', r'from .+ import',
        r'const ', r'let ', r'var ', r'=>', r'return ', r'if \(',
        r'for \(', r'while \(', r'#include', r'public class',
        r'SELECT ', r'INSERT ', r'UPDATE ', r'DELETE ', r'FROM ',
        r'<html', r'<div', r'<script', r'\{.*\}', r'\[.*\]',
    ]
    if any(re.search(p, t, re.IGNORECASE) for p in code_signals):
        return "code"

    # Number / measurement
    if re.match(r'^[\d,.\s%$£€]+$', t):
        return "number"

    # Address (contains street, road, avenue etc)
    address_words = ['street', 'avenue', 'road', 'lane', 'drive', 'blvd', 'floor', 'suite', 'apt']
    if any(w in t.lower() for w in address_words):
        return "address"

    # Multi-line = likely document/text
    if '\n' in t and len(t) > 100:
        return "text"

    return "other"


# ── Query clipboard history ──────────────────────────────────────────────────

def get_clipboard_history_smart(limit: int = 20) -> list[dict]:
    """Return recent clipboard entries."""
    return _history[:limit]


def find_clip_by_type(tag: str) -> list[dict]:
    """Filter history by tag: code, email, url, phone, address, text."""
    return [e for e in _history if e["tag"] == tag.lower()][:10]


def find_clip_by_query(query: str) -> list[dict]:
    """Search clipboard history by content."""
    q = query.lower()
    return [e for e in _history if q in e["text"].lower()][:10]


def paste_clip(entry_id: int) -> str:
    """Copy a historical entry back to clipboard and return it."""
    for entry in _history:
        if entry["id"] == entry_id:
            pyperclip.copy(entry["text"])
            return f"Pasted: {entry['preview']}"
    return f"Clip #{entry_id} not found"


def clear_clipboard_history() -> str:
    """Clear all history."""
    _history.clear()
    return "Clipboard history cleared"


# ── AI-powered clipboard queries ─────────────────────────────────────────────

def ai_clipboard_query(query: str) -> str:
    """
    Answer natural language queries about clipboard history.
    Examples:
    - "paste my last code snippet"
    - "what email address did I copy?"
    - "find the URL I copied earlier"
    - "summarize what I copied today"
    """
    q = query.lower()

    # Fast paths — no AI needed
    if "last" in q and ("code" in q or "snippet" in q):
        clips = find_clip_by_type("code")
        if clips:
            pyperclip.copy(clips[0]["text"])
            return f"Pasted last code snippet:\n{clips[0]['preview']}"
        return "No code snippets in clipboard history"

    if "email" in q and ("address" in q or "what" in q):
        clips = find_clip_by_type("email")
        if clips:
            return f"Email addresses copied: {', '.join(e['text'] for e in clips[:3])}"
        return "No email addresses in clipboard history"

    if "url" in q or "link" in q:
        clips = find_clip_by_type("url")
        if clips:
            return f"URLs copied:\n" + "\n".join(e["text"] for e in clips[:5])
        return "No URLs in clipboard history"

    if "phone" in q:
        clips = find_clip_by_type("phone")
        if clips:
            return f"Phone numbers copied: {', '.join(e['text'] for e in clips[:3])}"
        return "No phone numbers in clipboard history"

    if "history" in q or "all" in q or "list" in q:
        if not _history:
            return "Clipboard history is empty"
        lines = [f"[{e['tag'].upper()}] {e['preview']} ({e['timestamp']})" for e in _history[:10]]
        return "Recent clipboard history:\n" + "\n".join(lines)

    # AI query for complex requests
    if not _history:
        return "Clipboard history is empty"

    try:
        history_text = "\n".join([
            f"[{e['tag']}] {e['preview']} (at {e['timestamp']})"
            for e in _history[:20]
        ])

        client = boto3.client("bedrock-runtime", region_name=REGION)
        prompt = f"""User query about clipboard history: "{query}"

Recent clipboard history:
{history_text}

Answer the user's query concisely (1-3 sentences). If they want to paste something, say which item to paste."""

        body = {
            "schemaVersion": "messages-v1",
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": 256, "temperature": 0.1},
        }
        resp   = client.invoke_model(modelId=MODEL_ID, body=json.dumps(body),
                                     contentType="application/json", accept="application/json")
        result = json.loads(resp["body"].read())
        return result["output"]["message"]["content"][0]["text"].strip()

    except Exception as e:
        log.error(f"AI clipboard query failed: {e}")
        return f"Found {len(_history)} clipboard entries. Try: 'show clipboard history'"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_paste() -> str:
    try:
        return pyperclip.paste() or ""
    except Exception:
        return ""
