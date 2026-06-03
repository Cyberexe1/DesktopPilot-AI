"""
Smart Reply Controller — reads content on screen and generates a reply.
Use case: read an email → generate professional reply → type it.
"""

import logging
import time

import pyautogui
import pyperclip

from controllers.screen_reader_controller import read_screen
from ai.content_generator import generate_content

log = logging.getLogger(__name__)


def smart_reply(context: str = "", tone: str = "professional") -> str:
    """
    Read what's on screen (email/message), generate a reply, and type it.
    
    Args:
        context: Additional context for the reply (e.g., "accept the meeting")
        tone: Reply tone — professional, casual, friendly, formal
    """
    # Step 1: Read the screen to understand what we're replying to
    log.info("Reading screen for smart reply...")
    screen_text = read_screen("window")

    if not screen_text or screen_text == "No text detected on screen":
        return "Could not read screen content. Make sure the email/message is visible."

    # Step 2: Generate a reply using AI
    log.info(f"Generating {tone} reply...")
    prompt_context = f"Original message/email on screen:\n{screen_text[:800]}"
    if context:
        prompt_context += f"\n\nUser wants to: {context}"

    reply = generate_content(
        topic=prompt_context,
        content_type="reply",
        extra_instructions=f"Tone: {tone}. Write a concise reply (3-5 sentences max). "
                           f"Do NOT include subject line. Just the reply body. "
                           f"Start directly with the response, no 'Dear' if it's a chat/message."
    )

    if not reply or len(reply) < 10:
        return "Could not generate a reply"

    # Clean up the reply
    reply = reply.strip()
    # Remove any "Reply:" or "Response:" prefix the AI might add
    for prefix in ["Reply:", "Response:", "Here's", "Here is"]:
        if reply.lower().startswith(prefix.lower()):
            reply = reply[len(prefix):].strip()

    # Step 3: Copy to clipboard and optionally type it
    pyperclip.copy(reply)
    log.info(f"Smart reply generated: {len(reply)} chars")

    return f"Reply generated and copied to clipboard:\n\n{reply}\n\n(Press Ctrl+V to paste)"


def smart_reply_and_type(context: str = "", tone: str = "professional") -> str:
    """Generate a reply AND type it into the active window."""
    # Step 1: Read screen
    screen_text = read_screen("window")
    if not screen_text or screen_text == "No text detected on screen":
        return "Could not read screen. Make sure the email/message is visible."

    # Step 2: Generate reply
    prompt_context = f"Original message:\n{screen_text[:800]}"
    if context:
        prompt_context += f"\n\nUser instruction: {context}"

    reply = generate_content(
        topic=prompt_context,
        content_type="reply",
        extra_instructions=f"Tone: {tone}. Write 3-5 sentences. Direct reply only."
    )

    if not reply or len(reply) < 10:
        return "Could not generate reply"

    reply = reply.strip()
    for prefix in ["Reply:", "Response:", "Here's", "Here is"]:
        if reply.lower().startswith(prefix.lower()):
            reply = reply[len(prefix):].strip()

    # Step 3: Type the reply
    time.sleep(0.5)
    pyperclip.copy(reply)
    pyautogui.hotkey('ctrl', 'v')

    return f"Replied: {reply[:80]}..."
