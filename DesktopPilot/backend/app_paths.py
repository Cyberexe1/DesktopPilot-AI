"""
Resolve a writable data directory for the agent.

The bundled agent may be installed in a read-only location (e.g. Program Files),
so runtime data (SQLite cache, user profile) must live in a per-user writable
folder, not next to the executable.
"""

import os
import sys


def get_data_dir() -> str:
    """Return (creating if needed) a writable per-user data directory."""
    override = os.environ.get("DP_DATA_DIR")
    if override:
        data_dir = override
    elif sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        data_dir = os.path.join(base, "DesktopPilot")
    else:
        data_dir = os.path.join(os.path.expanduser("~"), ".desktoppilot")

    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def data_path(filename: str) -> str:
    """Return the absolute path to a file inside the writable data directory."""
    return os.path.join(get_data_dir(), filename)
