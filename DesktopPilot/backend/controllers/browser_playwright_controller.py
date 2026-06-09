"""
Browser Playwright Controller — full browser automation.
Provides click, type, navigate, read page, fill forms, take page screenshots.
Uses a PERSISTENT browser profile (stays logged in between sessions).
"""

import asyncio
import logging
import os
import time
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

log = logging.getLogger(__name__)

# ── Persistent browser state ─────────────────────────────────────────────────

_playwright = None
_context: Optional[BrowserContext] = None
_page: Optional[Page] = None

_USER = os.environ.get("USERNAME", "User")
BROWSER_PROFILE = os.path.join(os.path.expanduser("~"), ".desktoppilot", "browser_data")


async def _get_page() -> Page:
    """
    Get or create the persistent browser page.
    Uses Chrome with a dedicated DesktopPilot profile folder.
    Logins persist across restarts — log in once, stay logged in forever.
    """
    global _playwright, _context, _page

    # Check if existing page is still valid
    if _page:
        try:
            await _page.title()
            return _page
        except Exception:
            log.info("Page stale — relaunching browser")
            _page = None
            try:
                if _context:
                    await _context.close()
            except Exception:
                pass
            _context = None

    if not _playwright:
        _playwright = await async_playwright().start()

    if not _context:
        os.makedirs(BROWSER_PROFILE, exist_ok=True)

        # Find Chrome executable
        chrome_paths = [
            rf"C:\Program Files\Google\Chrome\Application\chrome.exe",
            rf"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            rf"C:\Users\{_USER}\AppData\Local\Google\Chrome\Application\chrome.exe",
        ]
        chrome_exe = next((p for p in chrome_paths if os.path.exists(p)), None)

        launch_args = {
            "user_data_dir": BROWSER_PROFILE,
            "headless": False,
            "args": [
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            "no_viewport": True,
            "ignore_default_args": ["--enable-automation"],
        }

        if chrome_exe:
            launch_args["executable_path"] = chrome_exe

        _context = await _playwright.chromium.launch_persistent_context(**launch_args)
        log.info(f"Playwright browser launched (profile: {BROWSER_PROFILE})")

    # Get or create the page
    if not _page or _page.is_closed():
        if _context.pages:
            _page = _context.pages[-1]
        else:
            _page = await _context.new_page()

    return _page



async def close_browser():
    """Close the Playwright browser."""
    global _playwright, _context, _page
    try:
        if _context:
            await _context.close()
        if _playwright:
            await _playwright.stop()
    except Exception:
        pass
    _playwright = None
    _context = None
    _page = None
    log.info("Playwright browser closed")


# ── Navigation ────────────────────────────────────────────────────────────────

async def goto(url: str) -> str:
    """Navigate to a URL."""
    page = await _get_page()
    try:
        if not url.startswith("http"):
            url = "https://" + url
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        title = await page.title()
        log.info(f"Navigated to: {url} — {title}")
        return f"Opened: {title} ({url})"
    except Exception as e:
        return f"Navigation failed: {e}"


async def go_back() -> str:
    """Go back to previous page."""
    page = await _get_page()
    try:
        await page.go_back(wait_until="domcontentloaded", timeout=15000)
        title = await page.title()
        return f"Went back to: {title}"
    except Exception as e:
        return f"Back navigation failed: {e}"


async def refresh_page() -> str:
    """Refresh current page."""
    page = await _get_page()
    try:
        await page.reload(wait_until="domcontentloaded", timeout=15000)
        return "Page refreshed"
    except Exception as e:
        return f"Refresh failed: {e}"


# ── Clicking ──────────────────────────────────────────────────────────────────

async def click_text(text: str) -> str:
    """Click on an element containing the given text."""
    page = await _get_page()
    try:
        # Try multiple selectors
        selectors = [
            f'text="{text}"',
            f'a:has-text("{text}")',
            f'button:has-text("{text}")',
            f'[aria-label="{text}"]',
            f'input[value="{text}"]',
        ]

        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if await locator.is_visible(timeout=2000):
                    await locator.click(timeout=5000)
                    log.info(f"Clicked: '{text}'")
                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    return f"Clicked: '{text}'"
            except Exception:
                continue

        return f"Could not find clickable element with text: '{text}'"
    except Exception as e:
        return f"Click failed: {e}"


async def click_selector(selector: str) -> str:
    """Click on an element by CSS selector."""
    page = await _get_page()
    try:
        await page.click(selector, timeout=10000)
        log.info(f"Clicked selector: {selector}")
        return f"Clicked: {selector}"
    except Exception as e:
        return f"Click selector failed: {e}"


async def click_link(link_text: str) -> str:
    """Click a link by its text content."""
    page = await _get_page()
    try:
        await page.get_by_role("link", name=link_text).first.click(timeout=10000)
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
        title = await page.title()
        return f"Clicked link '{link_text}' — now on: {title}"
    except Exception as e:
        # Fallback to text matching
        try:
            await page.locator(f'a:has-text("{link_text}")').first.click(timeout=5000)
            return f"Clicked link: '{link_text}'"
        except Exception:
            return f"Link not found: '{link_text}' — {e}"


async def click_button(button_text: str) -> str:
    """Click a button by its text."""
    page = await _get_page()
    try:
        await page.get_by_role("button", name=button_text).first.click(timeout=10000)
        log.info(f"Clicked button: '{button_text}'")
        return f"Clicked button: '{button_text}'"
    except Exception as e:
        try:
            await page.locator(f'button:has-text("{button_text}")').first.click(timeout=5000)
            return f"Clicked button: '{button_text}'"
        except Exception:
            return f"Button not found: '{button_text}' — {e}"


# ── Typing & Forms ───────────────────────────────────────────────────────────

async def type_in_field(text: str, selector: str = "", placeholder: str = "", label: str = "") -> str:
    """Type text into a form field. Finds field by selector, placeholder, or label."""
    page = await _get_page()
    try:
        if selector:
            await page.fill(selector, text, timeout=5000)
        elif placeholder:
            await page.get_by_placeholder(placeholder).first.fill(text, timeout=5000)
        elif label:
            await page.get_by_label(label).first.fill(text, timeout=5000)
        else:
            # Try common input selectors
            for sel in ['input[type="text"]:visible', 'input[type="search"]:visible',
                       'textarea:visible', 'input:not([type]):visible',
                       '[contenteditable="true"]:visible']:
                try:
                    locator = page.locator(sel).first
                    if await locator.is_visible(timeout=1000):
                        await locator.fill(text, timeout=3000)
                        return f"Typed: '{text}'"
                except Exception:
                    continue
            return "No visible input field found"

        log.info(f"Typed in field: '{text[:30]}...'")
        return f"Typed: '{text}'"
    except Exception as e:
        return f"Type failed: {e}"


async def search_on_page(query: str, site_url: str = "") -> str:
    """Find and use the search box on the current page. If site_url provided, navigates there first."""
    page = await _get_page()
    try:
        # If a site URL is given, navigate there first
        if site_url:
            await page.goto(site_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)  # Wait for page to fully render

        # Common search selectors
        search_selectors = [
            'input[type="search"]',
            'input[name="q"]',
            'input[name="search"]',
            'input[aria-label*="earch"]',
            'input[placeholder*="earch"]',
            'input[placeholder*="Search"]',
            '#search-input',
            '.search-input',
            'input[name="search_query"]',  # YouTube
            'input[name="query"]',
        ]

        for sel in search_selectors:
            try:
                locator = page.locator(sel).first
                if await locator.is_visible(timeout=2000):
                    await locator.click(timeout=3000)
                    await locator.fill(query, timeout=3000)
                    await page.keyboard.press("Enter")
                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    log.info(f"Searched for: '{query}'")
                    return f"Searched for: '{query}'"
            except Exception:
                continue

        # Fallback: try Ctrl+F or just click first input
        return f"Could not find search box on this page"
    except Exception as e:
        return f"Search failed: {e}"


async def fill_web_form(fields: dict) -> str:
    """Fill multiple form fields. fields = {"label_or_placeholder": "value"}"""
    page = await _get_page()
    filled = []
    for key, value in fields.items():
        try:
            # Try by placeholder first
            try:
                await page.get_by_placeholder(key).first.fill(value, timeout=2000)
                filled.append(key)
                continue
            except Exception:
                pass
            # Try by label
            try:
                await page.get_by_label(key).first.fill(value, timeout=2000)
                filled.append(key)
                continue
            except Exception:
                pass
            # Try by name attribute
            try:
                await page.fill(f'[name="{key}"]', value, timeout=2000)
                filled.append(key)
                continue
            except Exception:
                pass
        except Exception:
            pass

    if filled:
        return f"Filled {len(filled)} fields: {', '.join(filled)}"
    return "Could not find form fields to fill"


async def submit_form() -> str:
    """Submit the current form (press Enter or click submit button)."""
    page = await _get_page()
    try:
        # Try clicking a submit button
        for sel in ['button[type="submit"]', 'input[type="submit"]',
                   'button:has-text("Submit")', 'button:has-text("Sign in")',
                   'button:has-text("Log in")', 'button:has-text("Search")']:
            try:
                locator = page.locator(sel).first
                if await locator.is_visible(timeout=1000):
                    await locator.click(timeout=3000)
                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    return "Form submitted"
            except Exception:
                continue

        # Fallback: press Enter
        await page.keyboard.press("Enter")
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
        return "Pressed Enter to submit"
    except Exception as e:
        return f"Submit failed: {e}"


# ── Reading Page Content ──────────────────────────────────────────────────────

async def get_page_text() -> str:
    """Get all visible text from the current page."""
    page = await _get_page()
    try:
        text = await page.inner_text("body", timeout=5000)
        # Trim to reasonable length
        if len(text) > 3000:
            text = text[:3000] + "\n... (truncated)"
        return f"Page text:\n{text}"
    except Exception as e:
        return f"Could not read page: {e}"


async def get_page_title() -> str:
    """Get the current page title and URL."""
    page = await _get_page()
    try:
        title = await page.title()
        url = page.url
        return f"Current page: {title} — {url}"
    except Exception as e:
        return f"Could not get page info: {e}"


async def get_page_links() -> str:
    """Get all links on the current page."""
    page = await _get_page()
    try:
        links = await page.eval_on_selector_all(
            "a[href]",
            "elements => elements.slice(0, 30).map(e => ({text: e.innerText.trim().substring(0, 50), href: e.href}))"
        )
        if not links:
            return "No links found on page"

        result = "Links on page:\n"
        for link in links:
            if link["text"]:
                result += f"  • {link['text']} → {link['href'][:80]}\n"

        return result
    except Exception as e:
        return f"Could not get links: {e}"


# ── Page Screenshots ──────────────────────────────────────────────────────────

async def screenshot_page(name: str = "") -> str:
    """Take a screenshot of the current browser page."""
    page = await _get_page()
    try:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{name or 'page'}_{timestamp}.png"
        filepath = os.path.join(os.path.expanduser("~/Desktop"), filename)
        await page.screenshot(path=filepath, full_page=False)
        log.info(f"Page screenshot: {filepath}")
        return f"Page screenshot saved: {filepath}"
    except Exception as e:
        return f"Screenshot failed: {e}"


# ── Scrolling ─────────────────────────────────────────────────────────────────

async def scroll_down(amount: int = 500) -> str:
    """Scroll down on the page."""
    page = await _get_page()
    try:
        await page.mouse.wheel(0, amount)
        return f"Scrolled down {amount}px"
    except Exception as e:
        return f"Scroll failed: {e}"


async def scroll_up(amount: int = 500) -> str:
    """Scroll up on the page."""
    page = await _get_page()
    try:
        await page.mouse.wheel(0, -amount)
        return f"Scrolled up {amount}px"
    except Exception as e:
        return f"Scroll failed: {e}"


async def scroll_to_bottom() -> str:
    """Scroll to the bottom of the page."""
    page = await _get_page()
    try:
        await page.keyboard.press("End")
        return "Scrolled to bottom"
    except Exception as e:
        return f"Scroll failed: {e}"


# ── Tab Management ────────────────────────────────────────────────────────────

async def new_tab(url: str = "") -> str:
    """Open a new tab, optionally navigating to a URL."""
    global _page
    page = await _get_page()
    try:
        _page = await _context.new_page()
        if url:
            if not url.startswith("http"):
                url = "https://" + url
            await _page.goto(url, wait_until="domcontentloaded", timeout=30000)
            title = await _page.title()
            return f"New tab opened: {title} ({url})"
        return "New tab opened"
    except Exception as e:
        return f"New tab failed: {e}"


async def close_tab() -> str:
    """Close the current tab."""
    global _page
    try:
        if _page:
            await _page.close()
        # Switch to last remaining page
        if _context and _context.pages:
            _page = _context.pages[-1]
            title = await _page.title()
            return f"Tab closed. Now on: {title}"
        return "Tab closed (no tabs remaining)"
    except Exception as e:
        return f"Close tab failed: {e}"


async def list_tabs() -> str:
    """List all open tabs."""
    try:
        if not _context:
            return "No browser open"
        tabs = []
        for i, p in enumerate(_context.pages):
            title = await p.title()
            tabs.append(f"  {i+1}. {title} — {p.url[:60]}")
        return f"Open tabs ({len(tabs)}):\n" + "\n".join(tabs)
    except Exception as e:
        return f"List tabs failed: {e}"


async def switch_tab(index: int) -> str:
    """Switch to a tab by index (1-based)."""
    global _page
    try:
        if not _context or not _context.pages:
            return "No browser open"
        idx = index - 1
        if 0 <= idx < len(_context.pages):
            _page = _context.pages[idx]
            await _page.bring_to_front()
            title = await _page.title()
            return f"Switched to tab {index}: {title}"
        return f"Tab {index} not found. Have {len(_context.pages)} tabs."
    except Exception as e:
        return f"Switch tab failed: {e}"


# ── Wait ──────────────────────────────────────────────────────────────────────

async def wait_for_element(selector: str, timeout: int = 10) -> str:
    """Wait for an element to appear on the page."""
    page = await _get_page()
    try:
        await page.wait_for_selector(selector, timeout=timeout * 1000)
        return f"Element appeared: {selector}"
    except Exception as e:
        return f"Element not found after {timeout}s: {selector}"


async def wait_for_page_load(timeout: int = 15) -> str:
    """Wait for the page to finish loading."""
    page = await _get_page()
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout * 1000)
        return "Page fully loaded"
    except Exception as e:
        return f"Page still loading after {timeout}s"
