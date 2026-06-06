"""
Windows Toast Notification Controller.
Uses PowerShell with Windows Runtime API (works on Windows 10 and 11).
"""

import logging
import subprocess

log = logging.getLogger(__name__)


def notify(title: str, message: str):
    """Show a Windows 10/11 toast notification."""
    safe_title = title.replace("'", "''").replace('"', '`"')
    safe_msg   = message.replace("'", "''").replace('"', '`"')

    # Method 1: PowerShell toast notification
    ps = f"""
try {{
    # Try BurntToast (best Windows 11 support)
    if (Get-Module -ListAvailable -Name BurntToast) {{
        Import-Module BurntToast
        New-BurntToastNotification -Text '{safe_title}', '{safe_msg}'
    }} else {{
        # Fallback: Windows 10/11 toast via Shell
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null
        $template = '<toast><visual><binding template="ToastText02"><text id="1">{safe_title}</text><text id="2">{safe_msg}</text></binding></visual></toast>'
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("DesktopPilot AI")
        $notifier.Show($toast)
    }}
}} catch {{
    # Final fallback: balloon tip
    try {{
        Add-Type -AssemblyName System.Windows.Forms
        $n = New-Object System.Windows.Forms.NotifyIcon
        $n.Icon = [System.Drawing.SystemIcons]::Information
        $n.BalloonTipIcon = 'Info'
        $n.BalloonTipTitle = '{safe_title}'
        $n.BalloonTipText = '{safe_msg}'
        $n.Visible = $true
        $n.ShowBalloonTip(5000)
        Start-Sleep -Milliseconds 5500
        $n.Dispose()
    }} catch {{}}
}}
"""
    try:
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-NonInteractive", "-Command", ps],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info(f"Notification: {title} — {message}")
    except Exception as e:
        log.warning(f"Notification failed: {e}")


def notify_done(success_count: int, total: int):
    """Notify user that a command finished executing."""
    if success_count == total:
        notify("DesktopPilot AI", f"Done — all {total} step{'s' if total != 1 else ''} completed")
    else:
        failed = total - success_count
        notify("DesktopPilot AI", f"{success_count}/{total} steps done, {failed} failed")


def notify_error(message: str):
    """Notify user of an error."""
    notify("DesktopPilot AI — Error", message[:100])
