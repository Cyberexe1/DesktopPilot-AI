"""
System Maintenance Controller — recycle bin, disk cleanup, services, ports, DNS, etc.
Handles system administration commands.
"""

import logging
import os
import subprocess
import ctypes
import socket

log = logging.getLogger(__name__)


def clear_recycle_bin() -> str:
    """Empty the Windows Recycle Bin."""
    try:
        # Use PowerShell to clear recycle bin
        result = subprocess.run(
            ['powershell', '-Command', 'Clear-RecycleBin -Force -ErrorAction SilentlyContinue'],
            capture_output=True, text=True, timeout=30
        )
        log.info("Recycle bin cleared")
        return "Recycle bin emptied successfully."
    except Exception as e:
        return f"Failed to clear recycle bin: {e}"


def check_windows_updates() -> str:
    """Open Windows Update settings."""
    try:
        os.startfile("ms-settings:windowsupdate")
        return "Opened Windows Update settings. Check for updates there."
    except Exception as e:
        return f"Failed to open updates: {e}"


def show_installed_programs() -> str:
    """List installed programs via registry."""
    try:
        result = subprocess.run(
            ['powershell', '-Command',
             'Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | '
             'Select-Object DisplayName, DisplayVersion | '
             'Where-Object { $_.DisplayName } | '
             'Sort-Object DisplayName | '
             'Format-Table -AutoSize | '
             'Out-String -Width 200'],
            capture_output=True, text=True, timeout=30
        )
        programs = result.stdout.strip()
        if len(programs) > 2000:
            programs = programs[:2000] + "\n... (truncated)"
        return f"Installed programs:\n{programs}"
    except Exception as e:
        return f"Failed to list programs: {e}"


def open_disk_cleanup() -> str:
    """Open Windows Disk Cleanup utility."""
    try:
        subprocess.Popen(['cleanmgr'], shell=False)
        return "Opened Disk Cleanup utility."
    except Exception as e:
        return f"Failed to open disk cleanup: {e}"


def open_device_manager() -> str:
    """Open Device Manager."""
    try:
        subprocess.Popen(['devmgmt.msc'], shell=True)
        return "Opened Device Manager."
    except Exception as e:
        return f"Failed to open device manager: {e}"


def check_network_speed() -> str:
    """Quick network latency check (ping Google DNS)."""
    try:
        result = subprocess.run(
            ['ping', '-n', '4', '8.8.8.8'],
            capture_output=True, text=True, timeout=20
        )
        output = result.stdout.strip()
        # Extract the summary line
        lines = output.split('\n')
        summary = [l for l in lines if 'Average' in l or 'average' in l or 'Minimum' in l]
        if summary:
            return f"Network ping to Google DNS (8.8.8.8):\n{chr(10).join(summary)}"
        return f"Ping results:\n{output[-500:]}"
    except Exception as e:
        return f"Network check failed: {e}"


def flush_dns() -> str:
    """Flush DNS resolver cache."""
    try:
        result = subprocess.run(
            ['ipconfig', '/flushdns'],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() or "DNS cache flushed."
    except Exception as e:
        return f"DNS flush failed: {e}"


def show_environment_variables() -> str:
    """Show key environment variables."""
    important_vars = [
        'PATH', 'USERPROFILE', 'TEMP', 'COMPUTERNAME',
        'PROCESSOR_ARCHITECTURE', 'NUMBER_OF_PROCESSORS',
        'OS', 'JAVA_HOME', 'PYTHON_HOME', 'NODE_PATH',
    ]

    result = "Environment Variables:\n"
    for var in important_vars:
        val = os.environ.get(var, "")
        if var == 'PATH':
            # Show first 5 PATH entries
            paths = val.split(';')[:5]
            result += f"  {var}: {'; '.join(paths)}... ({len(val.split(';'))} total)\n"
        elif val:
            result += f"  {var}: {val}\n"

    return result


def open_services() -> str:
    """Open Windows Services manager."""
    try:
        subprocess.Popen(['services.msc'], shell=True)
        return "Opened Services manager."
    except Exception as e:
        return f"Failed to open services: {e}"


def check_ports_in_use() -> str:
    """Show which ports are currently in use."""
    try:
        result = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True, text=True, timeout=15
        )
        lines = result.stdout.strip().split('\n')

        # Filter to LISTENING ports only
        listening = [l for l in lines if 'LISTENING' in l]

        if not listening:
            return "No listening ports found."

        # Take first 30
        output = "Ports in use (LISTENING):\n"
        output += f"{'Address':<30} {'PID':<8}\n"
        output += "-" * 40 + "\n"

        for line in listening[:30]:
            parts = line.split()
            if len(parts) >= 5:
                addr = parts[1]
                pid = parts[4]
                output += f"  {addr:<28} PID {pid}\n"

        if len(listening) > 30:
            output += f"\n  ... and {len(listening) - 30} more"

        return output
    except Exception as e:
        return f"Failed to check ports: {e}"


def get_startup_programs() -> str:
    """List programs that run at startup."""
    try:
        result = subprocess.run(
            ['powershell', '-Command',
             'Get-CimInstance Win32_StartupCommand | '
             'Select-Object Name, Command, Location | '
             'Format-Table -AutoSize | '
             'Out-String -Width 200'],
            capture_output=True, text=True, timeout=15
        )
        return f"Startup programs:\n{result.stdout.strip()[:2000]}"
    except Exception as e:
        return f"Failed to list startup programs: {e}"


def get_disk_usage() -> str:
    """Show disk usage for all drives."""
    try:
        result = subprocess.run(
            ['powershell', '-Command',
             'Get-PSDrive -PSProvider FileSystem | '
             'Select-Object Name, @{N="Used(GB)";E={[math]::Round($_.Used/1GB,1)}}, '
             '@{N="Free(GB)";E={[math]::Round($_.Free/1GB,1)}}, '
             '@{N="Total(GB)";E={[math]::Round(($_.Used+$_.Free)/1GB,1)}} | '
             'Format-Table -AutoSize | Out-String'],
            capture_output=True, text=True, timeout=15
        )
        return f"Disk usage:\n{result.stdout.strip()}"
    except Exception as e:
        return f"Failed to get disk usage: {e}"


def get_wifi_info() -> str:
    """Show current WiFi connection info."""
    try:
        result = subprocess.run(
            ['netsh', 'wlan', 'show', 'interfaces'],
            capture_output=True, text=True, timeout=10
        )
        return f"WiFi info:\n{result.stdout.strip()[:1500]}"
    except Exception as e:
        return f"Failed to get WiFi info: {e}"


def shutdown_computer(delay_seconds: int = 0) -> str:
    """Schedule a shutdown (with delay for safety)."""
    if delay_seconds < 60:
        delay_seconds = 300  # Minimum 5 minutes for safety
    try:
        subprocess.Popen(['shutdown', '/s', '/t', str(delay_seconds)])
        minutes = delay_seconds // 60
        return f"Computer will shut down in {minutes} minutes. Run 'shutdown /a' to cancel."
    except Exception as e:
        return f"Shutdown failed: {e}"


def cancel_shutdown() -> str:
    """Cancel a scheduled shutdown."""
    try:
        subprocess.run(['shutdown', '/a'], capture_output=True)
        return "Shutdown cancelled."
    except Exception as e:
        return f"Cancel failed: {e}"


def restart_computer(delay_seconds: int = 60) -> str:
    """Schedule a restart."""
    try:
        subprocess.Popen(['shutdown', '/r', '/t', str(delay_seconds)])
        return f"Computer will restart in {delay_seconds} seconds. Run 'shutdown /a' to cancel."
    except Exception as e:
        return f"Restart failed: {e}"
