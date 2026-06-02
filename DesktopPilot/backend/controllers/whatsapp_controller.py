"""
WhatsApp Controller — sends messages via WhatsApp Web using Playwright.
Requires: user must be logged into WhatsApp Web in Chrome already.
"""

import asyncio
import logging
import time
import urllib.parse

log = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_OK = True
except ImportError:
    PLAYWRIGHT_OK = False
    log.warning("Playwright not installed — WhatsApp automation disabled")


async def send_whatsapp_message(contact: str, message: str) -> str:
    """
    Send a WhatsApp message to a contact.
    First tries the desktop app (if installed), then falls back to WhatsApp Web.
    
    Args:
        contact: Name of the contact (as it appears in WhatsApp)
        message: Text message to send
    """
    if not contact:
        return "No contact specified"
    if not message:
        return "No message specified"

    log.info(f"WhatsApp: sending to '{contact}': {message[:50]}...")

    # Try desktop app first (using keyboard automation)
    result = await _send_via_desktop_app(contact, message)
    if result:
        return result

    # Fallback to Playwright + WhatsApp Web
    if PLAYWRIGHT_OK:
        try:
            return await _send_via_playwright(contact, message)
        except Exception as e:
            log.warning(f"Playwright WhatsApp failed: {e}")

    # Last fallback: wa.me URL
    return _send_via_url(contact, message)


async def _send_via_desktop_app(contact: str, message: str) -> str | None:
    """Send message using the WhatsApp desktop app + keyboard automation."""
    import subprocess
    import time
    import pyautogui

    # Check if WhatsApp desktop is installed (Microsoft Store)
    app_path = "shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"

    try:
        # Open WhatsApp desktop app
        subprocess.Popen(["cmd", "/c", "start", "", app_path], shell=False)
        time.sleep(3)  # Wait for app to open

        # Use Ctrl+N or search to find contact
        # WhatsApp desktop: Ctrl+F opens search
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(1)

        # Type contact name to search
        pyautogui.typewrite(contact, interval=0.03) if contact.isascii() else _clipboard_type(contact)
        time.sleep(2)  # Wait for search results

        # Press Enter to select first result
        pyautogui.press('enter')
        time.sleep(1)

        # Now cursor should be in the message input
        # Type the message
        _clipboard_type(message)
        time.sleep(0.5)

        # Press Enter to send
        pyautogui.press('enter')
        time.sleep(0.5)

        log.info(f"WhatsApp desktop: sent to {contact}")
        return f"WhatsApp message sent to {contact}: '{message[:50]}...'" if len(message) > 50 else f"WhatsApp message sent to {contact}: '{message}'"

    except Exception as e:
        log.warning(f"WhatsApp desktop app failed: {e}")
        return None


def _clipboard_type(text: str):
    """Type text via clipboard paste (handles all characters)."""
    import pyperclip
    import pyautogui
    pyperclip.copy(text)
    pyautogui.hotkey('ctrl', 'v')


async def _send_via_playwright(contact: str, message: str) -> str:
    """Send message using Playwright browser automation."""
    async with async_playwright() as p:
        # Launch Chrome with user data so WhatsApp Web session is preserved
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=_get_chrome_profile_path(),
            headless=False,
            channel="chrome",
            args=["--start-maximized"],
        )

        page = browser.pages[0] if browser.pages else await browser.new_page()

        # Navigate to WhatsApp Web
        log.info("Opening WhatsApp Web...")
        await page.goto("https://web.whatsapp.com", wait_until="networkidle", timeout=30000)

        # Wait for WhatsApp to load (check for search box)
        try:
            search_box = page.locator('[contenteditable="true"][data-tab="3"]')
            await search_box.wait_for(state="visible", timeout=20000)
        except Exception:
            # Try alternative selector
            search_box = page.locator('[title="Search input textbox"]')
            try:
                await search_box.wait_for(state="visible", timeout=10000)
            except Exception:
                return "WhatsApp Web not loaded. Please scan QR code first and try again."

        # Search for contact
        log.info(f"Searching for contact: {contact}")
        await search_box.click()
        await search_box.fill(contact)
        await page.wait_for_timeout(2000)

        # Click on the contact from search results
        contact_result = page.locator(f'span[title*="{contact}"]').first
        try:
            await contact_result.wait_for(state="visible", timeout=5000)
            await contact_result.click()
        except Exception:
            # Try clicking any matching result
            results = page.locator('[data-testid="cell-frame-container"]').first
            try:
                await results.wait_for(state="visible", timeout=3000)
                await results.click()
            except Exception:
                return f"Contact '{contact}' not found in WhatsApp"

        await page.wait_for_timeout(1000)

        # Find message input box and type message
        log.info("Typing message...")
        msg_box = page.locator('[contenteditable="true"][data-tab="10"]')
        try:
            await msg_box.wait_for(state="visible", timeout=5000)
        except Exception:
            msg_box = page.locator('footer [contenteditable="true"]').first
            await msg_box.wait_for(state="visible", timeout=5000)

        await msg_box.click()
        await msg_box.fill(message)
        await page.wait_for_timeout(500)

        # Press Enter to send
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(1000)

        log.info(f"WhatsApp message sent to {contact}")
        return f"WhatsApp message sent to {contact}: '{message[:50]}...'" if len(message) > 50 else f"WhatsApp message sent to {contact}: '{message}'"


def _send_via_url(contact: str, message: str) -> str:
    """Fallback: open WhatsApp Web URL with pre-filled message (requires phone number)."""
    import subprocess

    # If contact looks like a phone number, use wa.me
    phone = "".join(c for c in contact if c.isdigit())
    if len(phone) >= 10:
        encoded_msg = urllib.parse.quote(message)
        url = f"https://wa.me/{phone}?text={encoded_msg}"
        subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)
        return f"Opened WhatsApp for {phone} with message (click Send to confirm)"
    else:
        # Open WhatsApp Web and let user find contact manually
        encoded_msg = urllib.parse.quote(message)
        url = f"https://web.whatsapp.com"
        subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)
        return f"Opened WhatsApp Web — search for '{contact}' and paste message manually"


def _get_chrome_profile_path() -> str:
    """Get Chrome user data directory for persistent login."""
    import os
    user = os.environ.get("USERNAME", "User")
    # Use a dedicated profile for WhatsApp to avoid conflicts
    profile_dir = rf"C:\Users\{user}\AppData\Local\DesktopPilot\WhatsAppProfile"
    os.makedirs(profile_dir, exist_ok=True)
    return profile_dir


async def open_whatsapp() -> str:
    """Just open WhatsApp Web without sending a message."""
    if PLAYWRIGHT_OK:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch_persistent_context(
                    user_data_dir=_get_chrome_profile_path(),
                    headless=False,
                    channel="chrome",
                )
                page = browser.pages[0] if browser.pages else await browser.new_page()
                await page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=20000)
                return "WhatsApp Web opened"
        except Exception as e:
            log.warning(f"Playwright failed: {e}")

    import subprocess
    subprocess.Popen(["cmd", "/c", "start", "", "https://web.whatsapp.com"], shell=False)
    return "WhatsApp Web opened in browser"
