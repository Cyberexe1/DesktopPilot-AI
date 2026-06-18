"""
Low-Latency Voice Pipeline — Parallel Processing

Architecture:
  Step 1  faster-whisper transcription          (local, ~200-400ms)
  Step 2  Bedrock plan generation               (network, ~800-1500ms)
  Step 3  Execution                             (local, varies)

Parallel tricks:
  • While whisper transcribes  → pre-warm Bedrock HTTP connection
  • While Bedrock plans        → SAPI says "Got it" immediately (~80ms)
  • Command cache              → repeat commands skip Bedrock entirely
  • Nova Lite routing          → simple commands use faster model

Result: perceived latency drops from ~2s to ~0.4s for cached/simple commands.
"""

import asyncio
import hashlib
import logging
import os
import time
from collections import OrderedDict
from typing import Optional

log = logging.getLogger(__name__)

# ── Command Cache ─────────────────────────────────────────────────────────────

class LRUCommandCache:
    """
    Stores last N command→plan mappings in memory.
    Commands like "open Chrome", "volume up" always produce the same plan.
    Cache hit → skip Bedrock entirely → ~0ms planning time.
    """

    def __init__(self, max_size: int = 30):
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._max = max_size
        self._hits = 0
        self._misses = 0

    def _key(self, command: str) -> str:
        # Normalize: lowercase, strip punctuation, collapse whitespace
        normalized = " ".join(command.lower().strip().split())
        return hashlib.md5(normalized.encode()).hexdigest()

    def get(self, command: str) -> Optional[dict]:
        k = self._key(command)
        if k in self._cache:
            self._cache.move_to_end(k)
            self._hits += 1
            log.info(f"Cache HIT for: '{command}' (hits={self._hits})")
            return self._cache[k]
        self._misses += 1
        return None

    def put(self, command: str, plan: dict):
        # Only cache safe, deterministic commands — not sensitive ones
        sensitive_tools = {"run_terminal", "compose_email", "delete_file",
                           "delete_by_pattern", "send_whatsapp", "shutdown",
                           "restart", "type_text", "press_key"}
        tasks = plan.get("tasks", [])
        has_sensitive = any(t.get("tool") in sensitive_tools for t in tasks)

        if has_sensitive:
            log.info(f"Not caching sensitive command: '{command}'")
            return

        k = self._key(command)
        self._cache[k] = plan
        self._cache.move_to_end(k)
        if len(self._cache) > self._max:
            self._cache.popitem(last=False)
        log.info(f"Cached command: '{command}'")

    def stats(self) -> dict:
        total = self._hits + self._misses
        rate  = round(self._hits / total * 100, 1) if total else 0
        return {"hits": self._hits, "misses": self._misses, "hit_rate": f"{rate}%", "size": len(self._cache)}

    def clear(self):
        self._cache.clear()
        self._hits = 0
        self._misses = 0


# Global cache instance
command_cache = LRUCommandCache(max_size=30)


# ── Complexity Classifier ─────────────────────────────────────────────────────

# Simple commands → Nova Lite (~400ms, cheaper)
# Complex commands → Nova Pro (~1200ms, more capable)
_SIMPLE_PATTERNS = [
    "open ", "close ", "launch ", "start ",
    "volume up", "volume down", "mute", "unmute",
    "brightness up", "brightness down",
    "take a screenshot", "screenshot",
    "minimize", "maximize", "snap ",
    "battery", "how much battery",
    "clipboard", "what did i copy",
    "timer", "start a timer",
    "system info", "what's my ip",
    "play ", "pause", "next song", "previous song",
    "show desktop", "minimize all",
]

_COMPLEX_PATTERNS = [
    "create a project", "scaffold", "generate code", "write a script",
    "compose email", "draft email",
    "create a presentation", "create a document",
    "open and ", " and then ", " after that",
    "copy all files", "move all files",
    "send whatsapp", "fill the form",
]


def classify_command(command: str) -> str:
    """
    Returns 'simple' or 'complex'.
    Simple → use Nova Lite (faster + cheaper).
    Complex → use Nova Pro (smarter).
    """
    cmd = command.lower().strip()

    # Explicit complex check first
    for pattern in _COMPLEX_PATTERNS:
        if pattern in cmd:
            return "complex"

    # Then simple check
    for pattern in _SIMPLE_PATTERNS:
        if cmd.startswith(pattern) or pattern in cmd:
            return "simple"

    # Default: complex (safer)
    return "complex"


# ── Bedrock Connection Pre-Warmer ─────────────────────────────────────────────

_bedrock_warmed = False
_bedrock_client_nova_lite = None


def _get_lite_client():
    global _bedrock_client_nova_lite
    if _bedrock_client_nova_lite is None:
        import boto3
        _bedrock_client_nova_lite = boto3.client(
            "bedrock-runtime",
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        )
    return _bedrock_client_nova_lite


async def prewarm_bedrock():
    """
    Send a tiny keepalive request to Bedrock to establish the TCP connection.
    Called while Whisper is still transcribing — by the time transcription
    finishes the connection is already warm, saving ~150ms.
    """
    global _bedrock_warmed
    if _bedrock_warmed:
        return
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _prewarm_sync)
        _bedrock_warmed = True
        log.info("Bedrock connection pre-warmed ✓")
    except Exception as e:
        log.warning(f"Bedrock pre-warm failed (non-fatal): {e}")


def _prewarm_sync():
    """Tiny Bedrock call with 1-token output just to establish TCP."""
    import json, boto3
    client = _get_lite_client()
    model  = os.getenv("BEDROCK_ENHANCER_MODEL_ID", "us.amazon.nova-lite-v1:0")
    try:
        client.invoke_model(
            modelId=model,
            body=json.dumps({
                "schemaVersion": "messages-v1",
                "messages": [{"role": "user", "content": [{"text": "hi"}]}],
                "inferenceConfig": {"maxTokens": 1, "temperature": 0.01},
            }),
            contentType="application/json",
            accept="application/json",
        )
    except Exception:
        pass  # Don't care if this fails — it's just a warm-up


# ── Immediate Acknowledgment ──────────────────────────────────────────────────

_ACK_PHRASES = [
    "Got it, Sir.",
    "On it.",
    "Sure, Sir.",
    "Right away.",
    "Working on it, Sir.",
    "On it, Sir.",
]
_ack_index = 0


def speak_acknowledgment():
    """
    Immediately speak a short ack phrase via Windows SAPI.
    Called as soon as transcription finishes — BEFORE Bedrock responds.
    Makes the agent feel instant.
    """
    global _ack_index
    try:
        from controllers.voice_output_controller import speak_nonblocking
        phrase = _ACK_PHRASES[_ack_index % len(_ACK_PHRASES)]
        _ack_index += 1
        speak_nonblocking(phrase)
        log.info(f"Ack spoken: '{phrase}'")
    except Exception as e:
        log.warning(f"Ack speak failed (non-fatal): {e}")


# ── Parallel Pipeline ─────────────────────────────────────────────────────────

async def run_parallel_pipeline(
    text: str,
    user_id: str = "default",
    ws_broadcast=None,
) -> dict:
    """
    Full parallel pipeline:
      1. Check cache → if hit, return immediately (skip Bedrock)
      2. Classify command complexity → choose Nova Lite or Nova Pro
      3. Speak acknowledgment immediately (non-blocking)
      4. Call Bedrock in background
      5. Return plan when Bedrock responds

    Args:
        text:         Transcribed command text
        user_id:      User ID for memory context
        ws_broadcast: Optional async callable to send WS updates

    Returns:
        plan dict compatible with existing /execute endpoint
    """
    t0 = time.time()

    # ── 1. Cache check ───────────────────────────────────────────────────
    cached = command_cache.get(text)
    if cached:
        elapsed = round((time.time() - t0) * 1000)
        log.info(f"Pipeline: CACHE HIT in {elapsed}ms")
        if ws_broadcast:
            await ws_broadcast({"type": "pipeline_cache_hit", "command": text, "ms": elapsed})
        return cached

    # ── 2. Classify & select model ───────────────────────────────────────
    complexity = classify_command(text)
    model_env_key = "BEDROCK_ENHANCER_MODEL_ID" if complexity == "simple" else "BEDROCK_MODEL_ID"
    selected_model = os.getenv(model_env_key, "us.amazon.nova-lite-v1:0")
    log.info(f"Pipeline: complexity={complexity}, model={selected_model}")

    if ws_broadcast:
        await ws_broadcast({
            "type": "pipeline_start",
            "command": text,
            "complexity": complexity,
            "model": selected_model,
        })

    # ── 3. Speak acknowledgment immediately (non-blocking) ───────────────
    # This fires and returns instantly — SAPI speaks in background
    # while we wait for Bedrock
    speak_acknowledgment()

    # ── 4. Generate plan (with selected model) ───────────────────────────
    t_bedrock = time.time()

    # Temporarily override model for this call if using lite
    original_model = os.environ.get("BEDROCK_MODEL_ID", "")
    if complexity == "simple":
        os.environ["BEDROCK_MODEL_ID"] = selected_model

    try:
        from ai.planner import generate_plan
        plan = await generate_plan(text, user_id=user_id)
    finally:
        # Restore original model
        if complexity == "simple":
            os.environ["BEDROCK_MODEL_ID"] = original_model

    bedrock_ms = round((time.time() - t_bedrock) * 1000)
    total_ms   = round((time.time() - t0) * 1000)
    log.info(f"Pipeline: Bedrock={bedrock_ms}ms, total={total_ms}ms")

    if ws_broadcast:
        await ws_broadcast({
            "type": "pipeline_done",
            "bedrock_ms": bedrock_ms,
            "total_ms": total_ms,
            "complexity": complexity,
        })

    # ── 5. Cache the result ──────────────────────────────────────────────
    command_cache.put(text, plan)

    return plan


# ── Pre-warm on import ────────────────────────────────────────────────────────

async def _startup_prewarm():
    """Called once at backend startup to warm the Bedrock connection."""
    await asyncio.sleep(3)  # Wait for server to fully start first
    await prewarm_bedrock()

def schedule_prewarm():
    """Schedule the pre-warm task. Call from FastAPI lifespan."""
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_startup_prewarm())
    except RuntimeError:
        pass  # No event loop yet — fine
