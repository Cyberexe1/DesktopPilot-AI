"""
Windows Settings Controller — opens system settings pages via ms-settings: URIs.
"""

import logging
import subprocess

log = logging.getLogger(__name__)

SETTINGS_MAP: dict[str, str] = {
    "wifi":         "ms-settings:network-wifi",
    "wi-fi":        "ms-settings:network-wifi",
    "network":      "ms-settings:network",
    "bluetooth":    "ms-settings:bluetooth",
    "display":      "ms-settings:display",
    "sound":        "ms-settings:sound",
    "audio":        "ms-settings:sound",
    "apps":         "ms-settings:appsfeatures",
    "applications": "ms-settings:appsfeatures",
    "updates":      "ms-settings:windowsupdate",
    "windows update":"ms-settings:windowsupdate",
    "privacy":      "ms-settings:privacy",
    "storage":      "ms-settings:storagesense",
    "power":        "ms-settings:powersleep",
    "sleep":        "ms-settings:powersleep",
    "accounts":     "ms-settings:accounts",
    "notifications":"ms-settings:notifications",
    "taskbar":      "ms-settings:taskbar",
    "themes":       "ms-settings:themes",
    "personalization":"ms-settings:personalization",
    "keyboard":     "ms-settings:easeofaccess-keyboard",
    "mouse":        "ms-settings:mousetouchpad",
    "camera":       "ms-settings:privacy-webcam",
    "microphone":   "ms-settings:privacy-microphone",
    "location":     "ms-settings:privacy-location",
    "vpn":          "ms-settings:network-vpn",
    "proxy":        "ms-settings:network-proxy",
    "date":         "ms-settings:dateandtime",
    "time":         "ms-settings:dateandtime",
    "language":     "ms-settings:regionlanguage",
    "region":       "ms-settings:regionlanguage",
}


def open_setting(name: str) -> str:
    """Open a Windows settings page by name."""
    key = name.lower().strip()
    uri = SETTINGS_MAP.get(key)

    if not uri:
        # Fuzzy match
        for map_key, map_uri in SETTINGS_MAP.items():
            if key in map_key or map_key in key:
                uri = map_uri
                break

    if not uri:
        msg = f"Setting '{name}' not found. Available: {', '.join(SETTINGS_MAP.keys())}"
        log.warning(msg)
        return msg

    try:
        subprocess.Popen(["cmd", "/c", "start", uri], shell=False)
        msg = f"Opened settings: {name}"
        log.info(msg)
        return msg
    except Exception as e:
        msg = f"Failed to open settings: {e}"
        log.error(msg)
        return msg
