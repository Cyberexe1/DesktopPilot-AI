"""
Browser Controller — Playwright-based web automation.
Falls back to subprocess if Playwright is not available or fails.
"""

import asyncio
import logging
import subprocess
import urllib.parse

log = logging.getLogger(__name__)

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
    """Open a URL. Uses Playwright if available, else default browser."""
    if PLAYWRIGHT_AVAILABLE:
        result = await _playwright_open(url)
        if result:
            return result
    return _subprocess_open(url)


async def search_web(query: str) -> str:
    """Open a Google search."""
    encoded = urllib.parse.quote_plus(query)
    return await open_url(f"https://www.google.com/search?q={encoded}")


async def open_gmail_compose(to: str = "", subject: str = "", body: str = "") -> str:
    """Open Gmail compose with pre-filled fields.
    Uses URL method first. If fields aren't filled (common issue), 
    falls back to keyboard automation after the compose window opens."""
    import subprocess
    import time

    params = urllib.parse.urlencode({
        "view": "cm",
        "to":   to,
        "su":   subject,
        "body": body,
    })
    url = f"https://mail.google.com/mail/?{params}"

    # Open the compose URL
    subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)

    # Wait for Gmail to load
    time.sleep(5)

    # Now use keyboard to fill fields as backup
    # Gmail compose opens with cursor in "To" field
    import pyautogui

    try:
        # Fill To field (if not already filled by URL)
        if to:
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.2)
            pyautogui.typewrite(to, interval=0.02) if to.isascii() else _clipboard_paste(to)
            time.sleep(0.3)

        # Tab to Subject
        pyautogui.press('tab')
        time.sleep(0.3)

        # Fill Subject
        if subject:
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            _clipboard_paste(subject)
            time.sleep(0.3)

        # Tab to Body
        pyautogui.press('tab')
        time.sleep(0.3)

        # Fill Body
        if body:
            _clipboard_paste(body)

        return f"Gmail compose filled — to: {to}, subject: {subject}"

    except Exception as e:
        log.warning(f"Gmail keyboard fill failed: {e}")
        return f"Gmail compose opened (URL method) — to: {to}, subject: {subject}"


def _clipboard_paste(text: str):
    """Paste text via clipboard (handles unicode)."""
    import pyperclip
    import pyautogui
    pyperclip.copy(text)
    pyautogui.hotkey('ctrl', 'v')


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
    """Open URL in default browser via Windows shell."""
    try:
        subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)
        msg = f"Opened browser: {url}"
        log.info(msg)
        return msg
    except Exception as e:
        msg = f"Failed to open browser: {e}"
        log.error(msg)
        return msg
