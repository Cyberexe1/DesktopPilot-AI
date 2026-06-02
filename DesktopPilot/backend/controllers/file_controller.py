"""
File Controller — search and open files.
1. First searches the local SQLite index (fast — indexed files in Desktop/Documents/Downloads)
2. If not found, uses Windows Search to find files ANYWHERE on the system
3. Falls back to opening File Explorer search as last resort
"""

import logging
import os
import subprocess
import time

from database.sqlite_manager import search_file, get_latest_file

log = logging.getLogger(__name__)


def open_file(name: str) -> str:
    """
    Find and open a file by name.
    Strategy:
    1. Search SQLite index (fast, pre-indexed files)
    2. If not found → use Windows Everything/Search to find anywhere
    3. If still not found → open File Explorer search
    """
    # Step 1: Try SQLite index (fast)
    results = search_file(name)
    if not results:
        result = get_latest_file(name)
        if result:
            results = [result]

    if results:
        file_info = results[0]
        path = file_info["path"]
        if os.path.exists(path):
            try:
                os.startfile(path)
                log.info(f"Opened from index: {file_info['name']}")
                return f"Opened: {file_info['name']}"
            except Exception as e:
                log.warning(f"Failed to open indexed file: {e}")

    # Step 2: Try Windows Search (finds files ANYWHERE on the system)
    log.info(f"File '{name}' not in index — searching system...")
    found_path = _search_file_system(name)
    if found_path:
        try:
            os.startfile(found_path)
            log.info(f"Opened via system search: {found_path}")
            return f"Opened: {os.path.basename(found_path)}"
        except Exception as e:
            log.warning(f"Found but failed to open: {e}")

    # Step 3: Fallback — open File Explorer search
    log.info(f"Opening Explorer search for: {name}")
    return _open_explorer_search(name)


def _search_file_system(name: str) -> str | None:
    """
    Search for a file using Windows Search indexing (via PowerShell).
    Returns the full path of the first match, or None.
    """
    try:
        # Use PowerShell to query Windows Search index
        ps_cmd = f"""
$searcher = New-Object -ComObject Microsoft.Search.Interop.CSearchManager
$catalog = $searcher.GetCatalog("SystemIndex")
$session = $catalog.CreateConnection()
$query = "SELECT TOP 5 System.ItemPathDisplay FROM SystemIndex WHERE System.FileName LIKE '%{name}%' ORDER BY System.DateModified DESC"
$reader = $session.Query($query)
while ($reader.Read()) {{ Write-Output $reader.GetString(0) }}
"""
        result = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10
        )

        if result.stdout.strip():
            paths = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
            if paths:
                # Return first existing path
                for p in paths:
                    if os.path.exists(p):
                        log.info(f"Windows Search found: {p}")
                        return p
    except subprocess.TimeoutExpired:
        log.warning("Windows Search timed out")
    except Exception as e:
        log.warning(f"Windows Search failed: {e}")

    # Fallback: try simple filesystem search in common locations
    return _quick_scan(name)


def _quick_scan(name: str) -> str | None:
    """Quick scan common directories for the file (fallback if Windows Search COM fails)."""
    _USER = os.environ.get("USERNAME", "User")
    search_dirs = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Downloads"),
        rf"C:\Users\{_USER}\OneDrive",
        rf"C:\Users\{_USER}\Pictures",
        rf"C:\Users\{_USER}\Videos",
        rf"C:\Users\{_USER}\Music",
        "D:\\",
    ]

    name_lower = name.lower()

    for directory in search_dirs:
        if not os.path.exists(directory):
            continue
        try:
            for root, dirs, files in os.walk(directory):
                # Limit depth to 3
                depth = root.replace(directory, '').count(os.sep)
                if depth > 3:
                    dirs.clear()
                    continue

                for f in files:
                    if name_lower in f.lower():
                        full_path = os.path.join(root, f)
                        log.info(f"Quick scan found: {full_path}")
                        return full_path

                # Skip hidden/system dirs
                dirs[:] = [d for d in dirs if not d.startswith(('.', '$', '__'))]
        except (PermissionError, OSError):
            continue

    return None


def _open_explorer_search(name: str) -> str:
    """Open File Explorer with a search query as last resort."""
    import pyautogui

    try:
        # Open File Explorer search using Win+E then Ctrl+F
        subprocess.Popen(["explorer.exe"], shell=False)
        time.sleep(1.5)

        # Use Windows Search instead (Win key + type)
        pyautogui.press('win')
        time.sleep(0.8)
        pyautogui.typewrite(name, interval=0.04) if name.isascii() else _clipboard_type(name)
        time.sleep(1.0)

        msg = f"Searching for '{name}' in Windows Search — press Enter to open"
        log.info(msg)
        return msg

    except Exception as e:
        return f"Could not search for file: {e}"


def _clipboard_type(text: str):
    """Type via clipboard for non-ASCII text."""
    import pyperclip
    import pyautogui
    pyperclip.copy(text)
    pyautogui.hotkey('ctrl', 'v')
