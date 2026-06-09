"""
Local SQLite database manager.
Handles files index, command history, and project registry.
"""

import sqlite3
import logging
import os

log = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "desktoppilot.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                path          TEXT NOT NULL UNIQUE,
                modified_date TEXT
            );

            CREATE TABLE IF NOT EXISTS commands (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                command   TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS projects (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL UNIQUE,
                path          TEXT NOT NULL,
                framework     TEXT,
                start_command TEXT
            );
        """)
        conn.commit()
        log.info("SQLite tables initialized")
    finally:
        conn.close()


# ── Files ─────────────────────────────────────────────────────────────────────

def clear_files():
    conn = get_conn()
    try:
        conn.execute("DELETE FROM files")
        conn.commit()
    finally:
        conn.close()


def insert_file(name: str, path: str, modified_date: str):
    conn = get_conn()
    try:
        # Upsert: update if path exists, insert if not
        conn.execute(
            """INSERT INTO files (name, path, modified_date) VALUES (?, ?, ?)
               ON CONFLICT(path) DO UPDATE SET
               name=excluded.name, modified_date=excluded.modified_date""",
            (name, path, modified_date)
        )
        conn.commit()
    except Exception:
        # Fallback: plain insert if ON CONFLICT not supported
        conn.execute(
            "INSERT OR REPLACE INTO files (name, path, modified_date) VALUES (?, ?, ?)",
            (name, path, modified_date)
        )
        conn.commit()
    finally:
        conn.close()


def delete_file_from_index(path: str):
    """Remove a specific file from the index by its path."""
    conn = get_conn()
    try:
        conn.execute("DELETE FROM files WHERE path = ?", (path,))
        conn.commit()
    finally:
        conn.close()


def search_file(query: str) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT name, path FROM files WHERE name LIKE ? ORDER BY modified_date DESC LIMIT 5",
            (f"%{query}%",)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_latest_file(keyword: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT name, path FROM files WHERE name LIKE ? ORDER BY modified_date DESC LIMIT 1",
            (f"%{keyword}%",)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ── Commands ──────────────────────────────────────────────────────────────────

def save_command(command: str):
    conn = get_conn()
    try:
        conn.execute("INSERT INTO commands (command) VALUES (?)", (command,))
        conn.commit()
    finally:
        conn.close()


def get_recent_commands(limit: int = 10) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT command, timestamp FROM commands ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Projects ──────────────────────────────────────────────────────────────────

def register_project(name: str, path: str, framework: str = "", start_command: str = ""):
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO projects (name, path, framework, start_command)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET
                 path=excluded.path,
                 framework=excluded.framework,
                 start_command=excluded.start_command""",
            (name, path, framework, start_command)
        )
        conn.commit()
    finally:
        conn.close()


def find_project(name: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT name, path, framework, start_command FROM projects WHERE name LIKE ? LIMIT 1",
            (f"%{name}%",)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_last_project() -> dict | None:
    """Return the project mentioned in the most recent command."""
    conn = get_conn()
    try:
        projects = conn.execute(
            "SELECT name, path, framework, start_command FROM projects"
        ).fetchall()
        recent = conn.execute(
            "SELECT command FROM commands ORDER BY timestamp DESC LIMIT 10"
        ).fetchall()

        recent_text = " ".join(r["command"] for r in recent).lower()
        for project in projects:
            if project["name"].lower() in recent_text:
                return dict(project)
        return None
    finally:
        conn.close()


def list_projects() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT name, path, framework, start_command FROM projects ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
