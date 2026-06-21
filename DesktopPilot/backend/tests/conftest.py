"""
Pytest configuration — makes the backend package importable from the tests folder
so tests can do `from controllers... import` / `from ai... import` regardless of cwd.
"""

import os
import sys

# backend/ is the parent of this tests/ directory
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
