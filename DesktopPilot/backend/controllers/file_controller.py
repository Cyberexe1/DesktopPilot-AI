"""
File Controller — search and open files using the local SQLite index.
"""

import logging
import os

from database.sqlite_manager import search_file, get_latest_file

log = logging.getLogger(__name__)

# Map file extensions to preferred applications
EXT_APP_MAP = {
    ".pdf":  "explorer",   # Opens with default PDF viewer
    ".docx": "winword",
    ".doc":  "winword",
    ".xlsx": "excel",
    ".xls":  "excel",
    ".pptx": "powerpnt",
    ".ppt":  "powerpnt",
    ".txt":  "notepad",
    ".py":   "code",       # VS Code
    ".js":   "code",
    ".ts":   "code",
    ".jsx":  "code",
    ".tsx":  "code",
    ".json": "code",
    ".md":   "code",
}


def open_file(name: str) -> str:
    """Find a file by name keyword and open it with the appropriate application."""
    # Try exact keyword search first, then latest match
    results = search_file(name)
    if not results:
        result = get_latest_file(name)
        if result:
            results = [result]

    if not results:
        msg = f"File matching '{name}' not found in index"
        log.warning(msg)
        return msg

    file_info = results[0]
    path      = file_info["path"]

    if not os.path.exists(path):
        msg = f"File no longer exists at: {path}"
        log.warning(msg)
        return msg

    try:
        # Use Windows shell to open with default/associated application
        os.startfile(path)
        msg = f"Opened: {file_info['name']}"
        log.info(msg)
        return msg
    except Exception as e:
        msg = f"Failed to open file: {e}"
        log.error(msg)
        return msg
