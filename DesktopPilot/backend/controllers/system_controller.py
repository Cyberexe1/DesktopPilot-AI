"""
System Info Controller — battery, RAM, CPU, IP, disk, kill processes.
"""

import logging
import os
import platform
import subprocess

log = logging.getLogger(__name__)


def get_system_info(query: str = "all") -> str:
    """Get system information based on query type."""
    q = query.lower().strip()

    if "battery" in q or "charge" in q or "power" in q:
        return _get_battery()
    elif "ram" in q or "memory" in q:
        return _get_ram()
    elif "cpu" in q or "processor" in q:
        return _get_cpu()
    elif "ip" in q or "network" in q or "address" in q:
        return _get_ip()
    elif "disk" in q or "storage" in q or "space" in q:
        return _get_disk()
    elif "all" in q or "info" in q or "system" in q:
        return _get_all_info()
    else:
        return _get_all_info()


def kill_process(name: str) -> str:
    """Kill a process by name (e.g., 'chrome', 'notepad')."""
    process_name = name.lower().strip()

    # Map common names to actual process names
    PROCESS_MAP = {
        "chrome":     "chrome.exe",
        "notepad":    "notepad.exe",
        "word":       "WINWORD.EXE",
        "excel":      "EXCEL.EXE",
        "powerpoint": "POWERPNT.EXE",
        "vscode":     "Code.exe",
        "vs code":    "Code.exe",
        "spotify":    "Spotify.exe",
        "discord":    "Discord.exe",
        "explorer":   "explorer.exe",
        "cmd":        "cmd.exe",
        "terminal":   "cmd.exe",
    }

    exe_name = PROCESS_MAP.get(process_name, f"{process_name}.exe")

    try:
        result = subprocess.run(
            ["taskkill", "/IM", exe_name, "/F"],
            capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0:
            msg = f"Killed all {name} processes"
            log.info(msg)
            return msg
        else:
            if "not found" in result.stderr.lower():
                return f"No {name} processes running"
            return f"Could not kill {name}: {result.stderr.strip()}"

    except Exception as e:
        return f"Failed to kill {name}: {e}"


def _get_battery() -> str:
    """Get battery percentage and status."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "(Get-WmiObject Win32_Battery | Select-Object EstimatedChargeRemaining, BatteryStatus).EstimatedChargeRemaining"],
            capture_output=True, text=True, timeout=5
        )
        percent = result.stdout.strip()

        # Get charging status
        status_result = subprocess.run(
            ["powershell", "-Command",
             "(Get-WmiObject Win32_Battery).BatteryStatus"],
            capture_output=True, text=True, timeout=5
        )
        status_code = status_result.stdout.strip()
        status = "Charging" if status_code == "2" else "On Battery"

        if percent:
            return f"Battery: {percent}% ({status})"
        return "Battery information not available (desktop PC?)"
    except Exception as e:
        return f"Battery check failed: {e}"


def _get_ram() -> str:
    """Get RAM usage."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "$os = Get-WmiObject Win32_OperatingSystem; "
             "$total = [math]::Round($os.TotalVisibleMemorySize/1MB, 1); "
             "$free = [math]::Round($os.FreePhysicalMemory/1MB, 1); "
             "$used = $total - $free; "
             "$percent = [math]::Round(($used/$total)*100, 0); "
             "Write-Output \"RAM: $used GB / $total GB used ($percent%)\""],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() or "RAM info unavailable"
    except Exception as e:
        return f"RAM check failed: {e}"


def _get_cpu() -> str:
    """Get CPU usage percentage."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "$cpu = (Get-WmiObject Win32_Processor).LoadPercentage; "
             "$name = (Get-WmiObject Win32_Processor).Name; "
             "Write-Output \"CPU: $cpu% usage — $name\""],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() or "CPU info unavailable"
    except Exception as e:
        return f"CPU check failed: {e}"


def _get_ip() -> str:
    """Get IP addresses (local + public)."""
    try:
        # Local IP
        local_result = subprocess.run(
            ["powershell", "-Command",
             "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike '*Loopback*'}).IPAddress"],
            capture_output=True, text=True, timeout=5
        )
        local_ips = [ip.strip() for ip in local_result.stdout.strip().split('\n') if ip.strip()]

        info = f"Local IP: {', '.join(local_ips[:2])}"

        # Try to get public IP
        try:
            import urllib.request
            public_ip = urllib.request.urlopen("https://api.ipify.org", timeout=3).read().decode()
            info += f"\nPublic IP: {public_ip}"
        except Exception:
            pass

        return info
    except Exception as e:
        return f"IP check failed: {e}"


def _get_disk() -> str:
    """Get disk space for C: drive."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "$d = Get-PSDrive C; "
             "$total = [math]::Round(($d.Used + $d.Free)/1GB, 0); "
             "$used = [math]::Round($d.Used/1GB, 0); "
             "$free = [math]::Round($d.Free/1GB, 0); "
             "$percent = [math]::Round(($d.Used/($d.Used+$d.Free))*100, 0); "
             "Write-Output \"Disk C: $used GB used / $total GB total ($free GB free, $percent% used)\""],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() or "Disk info unavailable"
    except Exception as e:
        return f"Disk check failed: {e}"


def _get_all_info() -> str:
    """Get all system info at once."""
    parts = [
        f"Computer: {platform.node()} ({platform.system()} {platform.release()})",
        _get_battery(),
        _get_ram(),
        _get_cpu(),
        _get_ip(),
        _get_disk(),
    ]
    return "\n".join(parts)
