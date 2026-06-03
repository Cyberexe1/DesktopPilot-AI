"""
Brightness & Volume Controller — controls display brightness and system volume.
"""

import logging
import subprocess

log = logging.getLogger(__name__)


def set_brightness(level: int) -> str:
    """Set screen brightness (0-100)."""
    level = max(0, min(100, level))
    try:
        result = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command",
             f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return f"Brightness set to {level}%"
        return f"Brightness control failed: {result.stderr.strip()}"
    except Exception as e:
        return f"Brightness control failed: {e}"


def get_brightness() -> str:
    """Get current brightness level."""
    try:
        result = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command",
             "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"],
            capture_output=True, text=True, timeout=5
        )
        level = result.stdout.strip()
        if level:
            return f"Current brightness: {level}%"
        return "Could not read brightness"
    except Exception as e:
        return f"Brightness check failed: {e}"


def brightness_up(amount: int = 10) -> str:
    """Increase brightness by amount."""
    try:
        result = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command",
             "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"],
            capture_output=True, text=True, timeout=5
        )
        current = int(result.stdout.strip() or 50)
        new_level = min(100, current + amount)
        return set_brightness(new_level)
    except Exception:
        return set_brightness(70)


def brightness_down(amount: int = 10) -> str:
    """Decrease brightness by amount."""
    try:
        result = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command",
             "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"],
            capture_output=True, text=True, timeout=5
        )
        current = int(result.stdout.strip() or 50)
        new_level = max(0, current - amount)
        return set_brightness(new_level)
    except Exception:
        return set_brightness(30)


def set_volume(level: int) -> str:
    """Set system volume (0-100)."""
    level = max(0, min(100, level))
    try:
        # Use nircmd or PowerShell for volume
        subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command",
             f"$obj = New-Object -ComObject WScript.Shell; "
             f"1..50 | ForEach-Object {{ $obj.SendKeys([char]174) }}; "  # Mute first (volume down 50x)
             f"1..{level // 2} | ForEach-Object {{ $obj.SendKeys([char]175) }}"],  # Volume up
            capture_output=True, timeout=10
        )
        return f"Volume set to approximately {level}%"
    except Exception as e:
        return f"Volume control failed: {e}"


def volume_up() -> str:
    """Increase volume."""
    import pyautogui
    pyautogui.press('volumeup')
    pyautogui.press('volumeup')
    pyautogui.press('volumeup')
    return "Volume increased"


def volume_down() -> str:
    """Decrease volume."""
    import pyautogui
    pyautogui.press('volumedown')
    pyautogui.press('volumedown')
    pyautogui.press('volumedown')
    return "Volume decreased"


def mute_toggle() -> str:
    """Toggle mute/unmute."""
    import pyautogui
    pyautogui.press('volumemute')
    return "Mute toggled"
