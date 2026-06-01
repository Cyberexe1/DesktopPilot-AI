"""
Smart Form Filler — reads form fields from screen via Textract,
matches them to user profile data, and fills them using keyboard automation.
"""

import json
import logging
import os
import time

import pyautogui

from controllers.screen_reader_controller import analyze_screen
from controllers.keyboard_controller import type_text, press_key

log = logging.getLogger(__name__)

PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "user_profile.json")

DEFAULT_PROFILE = {
    "first_name": "",
    "last_name": "",
    "full_name": "",
    "email": "",
    "phone": "",
    "address": "",
    "city": "",
    "state": "",
    "zip_code": "",
    "country": "India",
    "date_of_birth": "",
    "company": "",
    "job_title": "",
    "linkedin": "",
    "github": "",
    "website": "",
}

# Map common form field labels to profile keys
FIELD_MAP = {
    "name": "full_name",
    "full name": "full_name",
    "first name": "first_name",
    "last name": "last_name",
    "email": "email",
    "e-mail": "email",
    "email address": "email",
    "phone": "phone",
    "phone number": "phone",
    "mobile": "phone",
    "mobile number": "phone",
    "contact": "phone",
    "address": "address",
    "street": "address",
    "street address": "address",
    "city": "city",
    "state": "state",
    "province": "state",
    "zip": "zip_code",
    "zip code": "zip_code",
    "postal code": "zip_code",
    "pincode": "zip_code",
    "pin code": "zip_code",
    "country": "country",
    "dob": "date_of_birth",
    "date of birth": "date_of_birth",
    "birthday": "date_of_birth",
    "company": "company",
    "organization": "company",
    "job title": "job_title",
    "position": "job_title",
    "role": "job_title",
    "linkedin": "linkedin",
    "github": "github",
    "website": "website",
    "url": "website",
}


def get_profile() -> dict:
    """Load user profile from JSON file."""
    if os.path.exists(PROFILE_PATH):
        try:
            with open(PROFILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_PROFILE.copy()


def save_profile(profile: dict) -> str:
    """Save user profile to JSON file."""
    try:
        with open(PROFILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
        return "Profile saved"
    except Exception as e:
        return f"Failed to save profile: {e}"


def update_profile(field: str, value: str) -> str:
    """Update a single field in the user profile."""
    profile = get_profile()
    key = FIELD_MAP.get(field.lower(), field.lower().replace(" ", "_"))
    if key in profile:
        profile[key] = value
        save_profile(profile)
        return f"Updated {key} = {value}"
    else:
        profile[key] = value
        save_profile(profile)
        return f"Added {key} = {value}"


def fill_form() -> str:
    """
    Read the screen, detect form fields, and fill them with profile data.
    Uses Tab to move between fields.
    """
    profile = get_profile()
    if not any(profile.values()):
        return "Profile is empty. Set your details first with 'Set my name to ...' or edit user_profile.json"

    log.info("Analyzing screen for form fields...")
    screen_data = analyze_screen()

    if not screen_data.get("forms"):
        # Fallback: try to detect fields from text
        return _fill_by_text_detection(profile, screen_data.get("text", ""))

    # Fill detected form fields
    filled = 0
    forms = screen_data["forms"]

    for label, current_value in forms.items():
        label_lower = label.lower().strip().rstrip(':')
        profile_key = FIELD_MAP.get(label_lower)

        if profile_key and profile.get(profile_key):
            value = profile[profile_key]
            log.info(f"Filling '{label}' with '{value}'")
            # Click on the field area (approximate)
            pyautogui.press('tab')
            time.sleep(0.3)
            pyautogui.hotkey('ctrl', 'a')  # Select existing text
            time.sleep(0.1)
            _type_value(value)
            filled += 1

    if filled > 0:
        return f"Filled {filled} form fields"
    return "No matching form fields found on screen"


def _fill_by_text_detection(profile: dict, screen_text: str) -> str:
    """Fallback: detect field labels from screen text and fill using Tab navigation."""
    lines = [l.strip().lower() for l in screen_text.split('\n') if l.strip()]

    # Find which profile fields match labels on screen
    matches = []
    for line in lines:
        clean = line.rstrip(':').strip()
        if clean in FIELD_MAP:
            key = FIELD_MAP[clean]
            if profile.get(key):
                matches.append((clean, key, profile[key]))

    if not matches:
        return "No form fields detected on screen. Make sure a form is visible."

    log.info(f"Detected {len(matches)} fields by text: {[m[0] for m in matches]}")

    # Fill fields using Tab to navigate
    filled = 0
    for label, key, value in matches:
        pyautogui.press('tab')
        time.sleep(0.3)
        _type_value(value)
        filled += 1
        time.sleep(0.2)

    return f"Filled {filled} fields: {', '.join(m[0] for m in matches)}"


def _type_value(value: str):
    """Type a value into the current field."""
    if value.isascii():
        pyautogui.typewrite(value, interval=0.03)
    else:
        import pyperclip
        pyperclip.copy(value)
        pyautogui.hotkey('ctrl', 'v')
