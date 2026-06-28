"""
File Indexer — scans directories, stores metadata in SQLite.
Phase 2: adds Watchdog file watcher + project auto-discovery.
"""

import json
import logging
import os
import threading
from datetime import datetime

from database.sqlite_manager import clear_files, insert_file, delete_file_from_index, register_project

log = logging.getLogger(__name__)

_USER = os.environ.get("USERNAME", "User")

SCAN_DIRS = [
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Downloads"),
    rf"C:\Users\{_USER}\Desktop",
    rf"C:\Users\{_USER}\Documents",
    rf"C:\Users\{_USER}\Downloads",
    rf"C:\Users\{_USER}\Pictures",
    "D:/Projects",
    "D:/",          # scan D: drive root so files created there are indexed
    "C:/Projects",
    rf"C:\Users\{_USER}\Projects",
]

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls",
    ".pptx", ".ppt", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".json", ".md", ".html", ".css", ".java", ".cpp", ".c",
    ".zip", ".png", ".jpg", ".jpeg",
}

# Project marker files → (framework label, default start command)
PROJECT_MARKERS = {
    "manage.py":       ("Django",   "python manage.py runserver"),
    "package.json":    ("Node.js",  "npm start"),
    "requirements.txt":("Python",   "python main.py"),
    "Cargo.toml":      ("Rust",     "cargo run"),
    "pom.xml":         ("Java",     "mvn spring-boot:run"),
    "go.mod":          ("Go",       "go run ."),
    "app.py":          ("Flask",    "python app.py"),
    "main.py":         ("Python",   "python main.py"),
}

MAX_DEPTH = 4

# ── Watcher state ─────────────────────────────────────────────────────────────
_observer      = None
_reindex_lock  = threading.Lock()
_debounce_timer = None
_pending_changes: set = set()
_DEBOUNCE_SECONDS = 2.0   # Wait 2s after last change before re-indexing


# ── Core indexer ──────────────────────────────────────────────────────────────

def index_files() -> int:
    """Rebuild the full file index. Returns count of indexed files."""
    log.info("Starting file indexer...")
    clear_files()

    count    = 0
    seen     = set()

    for directory in SCAN_DIRS:
        real = os.path.realpath(directory)
        if real in seen or not os.path.exists(directory):
            continue
        seen.add(real)
        count += _scan_directory(directory, depth=0)

    log.info(f"File index complete: {count} files indexed")
    return count


def _scan_directory(directory: str, depth: int) -> int:
    if depth > MAX_DEPTH:
        return 0

    count = 0
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                try:
                    if entry.is_file(follow_symlinks=False):
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in ALLOWED_EXTENSIONS:
                            modified = datetime.fromtimestamp(
                                entry.stat().st_mtime
                            ).isoformat()
                            insert_file(entry.name, entry.path, modified)
                            count += 1
                    elif entry.is_dir(follow_symlinks=False):
                        if not entry.name.startswith(('.', '$', '__')):
                            count += _scan_directory(entry.path, depth + 1)
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError) as e:
        log.warning(f"Cannot scan {directory}: {e}")

    return count


# ── Project auto-discovery ────────────────────────────────────────────────────

def discover_projects() -> list[dict]:
    """
    Scan project directories for known marker files.
    Returns list of {name, path, framework, start_command}.
    """
    project_dirs = [
        "D:/Projects",
        "C:/Projects",
        rf"C:\Users\{_USER}\Projects",
        os.path.expanduser("~/Projects"),
        os.path.expanduser("~/Documents"),
    ]

    discovered = []
    seen_paths = set()

    for base in project_dirs:
        if not os.path.exists(base):
            continue
        try:
            for entry in os.scandir(base):
                if not entry.is_dir(follow_symlinks=False):
                    continue
                real = os.path.realpath(entry.path)
                if real in seen_paths:
                    continue

                for marker, (framework, start_cmd) in PROJECT_MARKERS.items():
                    marker_path = os.path.join(entry.path, marker)
                    if os.path.exists(marker_path):
                        name = entry.name

                        # Try to get a better name from package.json
                        if marker == "package.json":
                            try:
                                with open(marker_path, encoding="utf-8") as f:
                                    pkg  = json.load(f)
                                    name = pkg.get("name", entry.name)
                            except Exception:
                                pass

                        discovered.append({
                            "name":          name,
                            "path":          entry.path,
                            "framework":     framework,
                            "start_command": start_cmd,
                        })
                        seen_paths.add(real)
                        break  # Only match first marker per directory
        except (PermissionError, OSError) as e:
            log.warning(f"Cannot scan {base} for projects: {e}")

    log.info(f"Auto-discovered {len(discovered)} projects")
    return discovered


def auto_register_projects():
    """Discover projects and register them in SQLite (non-destructive upsert)."""
    projects = discover_projects()
    for p in projects:
        try:
            register_project(p["name"], p["path"], p["framework"], p["start_command"])
        except Exception as e:
            log.warning(f"Could not register project {p['name']}: {e}")
    return len(projects)


# ── Watchdog file watcher ─────────────────────────────────────────────────────

def start_file_watcher():
    """Start background Watchdog observer. Safe to call multiple times."""
    global _observer

    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        log.warning("watchdog not installed — file watcher disabled")
        return None

    if _observer and _observer.is_alive():
        return _observer

    class _Handler(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory:
                _schedule_update(event.src_path, action="add")

        def on_deleted(self, event):
            if not event.is_directory:
                _schedule_update(event.src_path, action="remove")

        def on_moved(self, event):
            if not event.is_directory:
                _schedule_update(event.src_path, action="remove")
                _schedule_update(event.dest_path, action="add")

        def on_modified(self, event):
            if not event.is_directory:
                _schedule_update(event.src_path, action="add")

    _observer = Observer()
    handler   = _Handler()

    watched = 0
    for directory in SCAN_DIRS:
        if os.path.exists(directory):
            try:
                _observer.schedule(handler, directory, recursive=True)
                watched += 1
            except Exception as e:
                log.warning(f"Cannot watch {directory}: {e}")

    if watched > 0:
        _observer.daemon = True
        _observer.start()
        log.info(f"File watcher started — watching {watched} directories")
    else:
        log.warning("No directories available to watch")

    return _observer


def stop_file_watcher():
    global _observer, _debounce_timer
    if _debounce_timer:
        _debounce_timer.cancel()
    if _observer and _observer.is_alive():
        _observer.stop()
        _observer.join(timeout=3)
        _observer = None
        log.info("File watcher stopped")


def _schedule_update(path: str, action: str):
    """
    Debounced update — collects file changes and processes them in a batch
    after DEBOUNCE_SECONDS of quiet. Prevents hammering SQLite on bulk operations.
    """
    global _debounce_timer

    ext = os.path.splitext(path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return

    # Track the change
    _pending_changes.add((path, action))

    # Cancel existing timer and restart debounce
    if _debounce_timer:
        _debounce_timer.cancel()

    _debounce_timer = threading.Timer(_DEBOUNCE_SECONDS, _process_pending_changes)
    _debounce_timer.daemon = True
    _debounce_timer.start()


def _process_pending_changes():
    """Process all pending file changes incrementally (no full re-index)."""
    global _pending_changes

    if not _pending_changes:
        return

    # Grab and clear pending changes
    with _reindex_lock:
        changes = list(_pending_changes)
        _pending_changes.clear()

    if not changes:
        return

    added = 0
    removed = 0

    for path, action in changes:
        try:
            if action == "add" and os.path.exists(path):
                name = os.path.basename(path)
                modified = datetime.fromtimestamp(
                    os.path.getmtime(path)
                ).isoformat()
                insert_file(name, path, modified)
                added += 1
            elif action == "remove":
                delete_file_from_index(path)
                removed += 1
        except Exception as e:
            log.warning(f"Error processing file change {path}: {e}")

    if added or removed:
        log.info(f"File index updated: +{added} added, -{removed} removed "
                 f"({len(changes)} changes processed)")
