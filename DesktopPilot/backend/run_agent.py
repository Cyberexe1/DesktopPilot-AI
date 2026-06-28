"""
Frozen entry point for the bundled DesktopPilot local agent.

PyInstaller builds this into a standalone Windows executable so end users
do NOT need Python installed. It starts the FastAPI app with uvicorn.
"""

import os
import sys

# When frozen by PyInstaller, data files live next to the executable in a
# temp dir (sys._MEIPASS). Make the working directory predictable so relative
# resources (user_profile.json, the SQLite db) resolve next to the exe.
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

# The bundled agent does NOT ship local Whisper (torch/faster-whisper) — speech
# transcription is handled by the cloud backend. Disable the local model so the
# lazy import is never triggered.
os.environ.setdefault("WHISPER_MODEL", "disabled")

import uvicorn
from main import app

if __name__ == "__main__":
    port = int(os.environ.get("DP_AGENT_PORT", "8888"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
