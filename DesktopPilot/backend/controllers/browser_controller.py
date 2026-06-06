"""
Browser Controller — Playwright-based web automation.
Falls back to subprocess if Playwright is not available or fails.
"""

import asyncio
import logging
import os
import subprocess
import urllib.parse

log = logging.getLogger(__name__)

_USER = os.environ.get("USERNAME", "User")

# Detect Playwright availability once at import time
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
    log.info("Playwright available — full browser automation enabled")
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    log.warning("Playwright not installed — using subprocess fallback")


# ── Public API (all async) ────────────────────────────────────────────────────

async def open_url(url: str) -> str:
    """Open a URL in the user's Chrome (their logged-in profile)."""
    return _subprocess_open(url)


async def search_web(query: str) -> str:
    """Open a Google search in the user's Chrome."""
    encoded = urllib.parse.quote_plus(query)
    return _subprocess_open(f"https://www.google.com/search?q={encoded}")


async def search_youtube(query: str) -> str:
    """Search YouTube directly in the user's Chrome."""
    encoded = urllib.parse.quote_plus(query)
    return _subprocess_open(f"https://www.youtube.com/results?search_query={encoded}")


async def open_gmail_compose(to: str = "", subject: str = "", body: str = "") -> str:
    """Open Gmail compose with pre-filled fields.
    Uses two-call approach for body content + keyboard automation."""
    import subprocess
    import time
    import pyautogui
    import pyperclip

    # ── Step 1: Generate email body if empty/short ──
    if not body or len(body) < 30:
        try:
            from ai.content_generator import generate_content
            topic = subject if subject else f"email to {to}"
            generated = generate_content(
                topic=topic,
                content_type="letter",
                extra_instructions=f"To: {to}. Subject: {subject}. Write only the email body text."
            )
            if generated and len(generated) > 20:
                body = generated.strip()
                log.info(f"Email body generated: {len(body)} chars")
        except Exception as e:
            log.warning(f"Email content generation failed: {e}")
            body = body or f"I am writing regarding {subject}.\n\nPlease let me know if you need any further information.\n\nThank you.\n\nBest regards"

    if not subject:
        subject = f"Email to {to}"

    # Post-process body: ensure proper line breaks for email formatting
    body = _format_email_body(body)

    # ── Step 2: Open Gmail compose with URL params ──
    # Use the compose URL format that Gmail reliably supports
    # Format: https://mail.google.com/mail/?view=cm&fs=1&to=...&su=...&body=...
    params = urllib.parse.urlencode({
        "view": "cm",
        "fs":   "1",       # Full screen compose
        "to":   to,
        "su":   subject,
        "body": body,
    })
    url = f"https://mail.google.com/mail/?{params}"
    # Open specifically in Chrome
    chrome_paths = [
        rf"C:\Program Files\Google\Chrome\Application\chrome.exe",
        rf"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        rf"C:\Users\{_USER}\AppData\Local\Google\Chrome\Application\chrome.exe",
    ]
    chrome_exe = next((p for p in chrome_paths if os.path.exists(p)), None)
    if chrome_exe:
        subprocess.Popen([chrome_exe, url], shell=False)
    else:
        subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)

    # Wait for Chrome/Gmail to fully load
    log.info("Waiting for Gmail compose to load...")
    time.sleep(8)

    # ── Step 3: Verify Chrome is in focus ──
    try:
        import pygetwindow as gw
        # Find Chrome window and activate it
        chrome_windows = [w for w in gw.getAllWindows() if 'chrome' in w.title.lower() or 'gmail' in w.title.lower()]
        if chrome_windows:
            win = chrome_windows[0]
            if win.isMinimized:
                win.restore()
            win.activate()
            time.sleep(1)
            log.info(f"Focused: {win.title}")
        else:
            log.warning("Chrome/Gmail window not found — trying anyway")
            time.sleep(2)
    except Exception as e:
        log.warning(f"Window focus failed: {e}")
        time.sleep(2)

    # ── Step 4: Fill fields — cursor is already in To field, just type ──
    try:
        import pygetwindow as gw

        # Focus Chrome/Gmail window
        chrome_wins = [w for w in gw.getAllWindows() 
                       if any(k in w.title.lower() for k in ['chrome', 'gmail', 'mail', 'compose'])]
        if chrome_wins:
            chrome_wins[0].activate()
            time.sleep(1)

        # Cursor is already in "To" field when Gmail compose opens.
        # Just type → Tab → type → Tab → type

        # 1. Type email in To field (cursor already here)
        if to:
            pyperclip.copy(to)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)

        # 2. Tab → Subject
        pyautogui.press('tab')
        time.sleep(0.5)

        # 3. Type Subject
        if subject:
            pyperclip.copy(subject)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)

        # 4. Tab → Body
        pyautogui.press('tab')
        time.sleep(0.5)

        # 5. Type Body
        if body:
            pyperclip.copy(body)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.3)

        log.info(f"Gmail filled — to: {to}, subject: {subject}, body: {len(body)} chars")
        return f"Gmail compose filled — to: {to}, subject: {subject}"

    except Exception as e:
        log.warning(f"Gmail fill failed: {e}")
        pyperclip.copy(body)
        return f"Gmail opened. Body in clipboard — Ctrl+V to paste."


# ── Playwright implementations ────────────────────────────────────────────────

async def _playwright_open(url: str) -> str | None:
    """Open a URL in Chrome via Playwright. Returns None on failure."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                channel="chrome",
                args=["--start-maximized"],
            )
            context = await browser.new_context(no_viewport=True)
            page    = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            log.info(f"Playwright opened: {url}")
            # Leave browser open — user takes over
            return f"Opened browser: {url}"
    except Exception as e:
        log.warning(f"Playwright open_url failed ({e}), falling back to subprocess")
        return None


async def _playwright_gmail(to: str, subject: str, body: str) -> str | None:
    """Open Gmail compose and fill fields via Playwright."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                channel="chrome",
                args=["--start-maximized"],
            )
            context = await browser.new_context(no_viewport=True)
            page    = await context.new_page()

            log.info("Playwright: navigating to Gmail")
            await page.goto("https://mail.google.com", wait_until="networkidle", timeout=25000)

            # Click Compose
            compose_btn = page.locator('[gh="cm"]')
            await compose_btn.wait_for(state="visible", timeout=12000)
            await compose_btn.click()
            await page.wait_for_timeout(800)

            # Fill To
            if to:
                to_field = page.locator('input[name="to"]').first
                await to_field.wait_for(state="visible", timeout=6000)
                await to_field.fill(to)
                await page.keyboard.press("Tab")

            # Fill Subject
            if subject:
                subj = page.locator('input[name="subjectbox"]').first
                await subj.wait_for(state="visible", timeout=4000)
                await subj.fill(subject)

            # Fill Body
            if body:
                body_field = page.locator('[aria-label="Message Body"]').first
                await body_field.wait_for(state="visible", timeout=4000)
                await body_field.fill(body)

            log.info(f"Gmail compose filled — to: {to}, subject: {subject}")
            return f"Gmail compose opened — to: {to}, subject: {subject}"

    except Exception as e:
        log.warning(f"Playwright Gmail failed ({e}), falling back to URL compose")
        return None


# ── Subprocess fallback ───────────────────────────────────────────────────────

def _subprocess_open(url: str) -> str:
    """Open URL in the user's actual Chrome (with their logged-in profile)."""
    try:
        # Try common Chrome paths
        chrome_paths = [
            rf"C:\Program Files\Google\Chrome\Application\chrome.exe",
            rf"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            rf"C:\Users\{_USER}\AppData\Local\Google\Chrome\Application\chrome.exe",
        ]

        chrome_exe = None
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_exe = path
                break

        if chrome_exe:
            # Open in user's existing Chrome profile (the one they're logged into)
            subprocess.Popen([chrome_exe, "--profile-directory=Default", url], shell=False)
        else:
            # Fallback: try "chrome" command (might be in PATH)
            subprocess.Popen(["chrome", url], shell=False)

        msg = f"Opened in Chrome: {url}"
        log.info(msg)
        return msg
    except Exception as e:
        # Final fallback: default browser
        try:
            subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)
            return f"Opened browser: {url}"
        except Exception as e2:
            msg = f"Failed to open browser: {e2}"
            log.error(msg)
            return msg


def _format_email_body(body: str) -> str:
    """
    Force proper professional email formatting regardless of what the AI generated.
    """
    import re

    # Remove any random incomplete sentences ("I am." at the end)
    body = re.sub(r'\.\s*I am\.\s*', '. ', body)
    body = re.sub(r'\s*I am\.\s*$', '', body)

    # Fix "Best. regards" or "Best.\nregards" → "Best regards,"
    body = re.sub(r'Best\.\s*regards', 'Best regards', body, flags=re.IGNORECASE)
    body = re.sub(r'Best\s*regards\.', 'Best regards,', body, flags=re.IGNORECASE)
    body = re.sub(r'Best regards[,.]?\s*', 'Best regards,\n', body, flags=re.IGNORECASE)

    # Remove filler about contact info
    body = re.sub(r'I am providing you with my contact information[^.]*\.?\s*', '', body)
    body = re.sub(r'My email address is[^.]*\.?\s*', '', body)
    body = re.sub(r'My phone number is[^.]*\.?\s*', '', body)
    body = re.sub(r'you can reach me[^.]*\.?\s*', '', body)

    # If no double newlines exist, add structure
    if '\n\n' not in body:
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', body.strip())
        
        if len(sentences) >= 4:
            # Structure: greeting | para1 | para2 | closing
            parts = []
            
            # Check if first sentence is a greeting
            if sentences[0].lower().startswith('dear'):
                parts.append(sentences[0])
                sentences = sentences[1:]
            
            # Split remaining into 2 paragraphs
            mid = len(sentences) // 2
            
            # Find where closing starts
            closing_idx = len(sentences)
            for i, s in enumerate(sentences):
                s_lower = s.lower().strip()
                if any(s_lower.startswith(c) for c in ['thank you', 'thanks', 'i appreciate', 'looking forward', 'i look forward', 'i would appreciate']):
                    closing_idx = i
                    break
            
            # Body paragraphs
            body_sentences = sentences[:closing_idx]
            closing_sentences = sentences[closing_idx:]
            
            if body_sentences:
                mid = max(1, len(body_sentences) // 2)
                parts.append(' '.join(body_sentences[:mid]))
                if len(body_sentences) > mid:
                    parts.append(' '.join(body_sentences[mid:]))
            
            # Closing
            if closing_sentences:
                parts.append(' '.join(closing_sentences))
            
            body = '\n\n'.join(parts)
        else:
            body = '\n\n'.join(sentences)

    # Ensure "Best regards," is on its own line at the end
    body = re.sub(r'\n*Best regards,\n*', '\n\nBest regards,\n', body, flags=re.IGNORECASE)

    # Clean up multiple newlines
    body = re.sub(r'\n{3,}', '\n\n', body)
    body = body.strip()

    return body
