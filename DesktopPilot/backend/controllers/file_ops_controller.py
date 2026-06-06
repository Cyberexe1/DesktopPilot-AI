"""
File Operations Controller — copy, move, rename, delete, zip/unzip files and folders.
Handles all file management commands that go beyond just opening files.
"""

import logging
import os
import shutil
import zipfile
import glob
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

_USER = os.environ.get("USERNAME", "User")

# Common directory shortcuts
DIR_SHORTCUTS = {
    "desktop": os.path.expanduser("~/Desktop"),
    "documents": os.path.expanduser("~/Documents"),
    "downloads": os.path.expanduser("~/Downloads"),
    "pictures": os.path.expanduser("~/Pictures"),
    "videos": os.path.expanduser("~/Videos"),
    "music": os.path.expanduser("~/Music"),
    "c": "C:/",
    "c drive": "C:/",
    "d": "D:/",
    "d drive": "D:/",
    "e": "E:/",
    "e drive": "E:/",
    "f": "F:/",
    "f drive": "F:/",
}

# Dangerous paths that should never be modified
PROTECTED_PATHS = [
    "C:/Windows",
    "C:/Program Files",
    "C:/Program Files (x86)",
    "C:/ProgramData",
    os.path.expanduser("~/AppData"),
]


def _resolve_path(path_or_shortcut: str) -> str:
    """Resolve shortcuts like 'Desktop', 'D drive' to actual paths."""
    lower = path_or_shortcut.lower().strip()
    if lower in DIR_SHORTCUTS:
        return DIR_SHORTCUTS[lower]
    return path_or_shortcut


def _is_safe_path(path: str) -> bool:
    """Check if a path is safe to modify."""
    real = os.path.realpath(path)
    for protected in PROTECTED_PATHS:
        if real.lower().startswith(os.path.realpath(protected).lower()):
            return False
    return True


def _find_file(name: str, search_dirs: list = None) -> str:
    """Find a file by name in common directories."""
    if os.path.exists(name):
        return name

    if search_dirs is None:
        search_dirs = [
            os.path.expanduser("~/Desktop"),
            os.path.expanduser("~/Documents"),
            os.path.expanduser("~/Downloads"),
            "D:/",
            "E:/",
            "F:/",
        ]

    for directory in search_dirs:
        if not os.path.exists(directory):
            continue
        for root, dirs, files in os.walk(directory):
            # Limit depth to 3
            depth = root.replace(directory, '').count(os.sep)
            if depth > 3:
                dirs.clear()
                continue
            for f in files:
                if name.lower() in f.lower():
                    return os.path.join(root, f)
    return ""


# ── Copy Operations ───────────────────────────────────────────────────────────

def copy_file(source: str, destination: str) -> str:
    """Copy a file or folder from source to destination."""
    source = _resolve_path(source)
    destination = _resolve_path(destination)

    # If source is just a filename, try to find it
    if not os.path.exists(source):
        found = _find_file(source)
        if found:
            source = found
        else:
            return f"File not found: {source}"

    if not _is_safe_path(source):
        return f"Cannot copy from protected path: {source}"

    # If destination is a directory, keep the original filename
    if os.path.isdir(destination):
        dest_path = os.path.join(destination, os.path.basename(source))
    else:
        # Ensure destination directory exists
        dest_dir = os.path.dirname(destination)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        dest_path = destination

    try:
        if os.path.isdir(source):
            shutil.copytree(source, dest_path, dirs_exist_ok=True)
            log.info(f"Copied folder: {source} → {dest_path}")
            return f"Copied folder to: {dest_path}"
        else:
            shutil.copy2(source, dest_path)
            log.info(f"Copied file: {source} → {dest_path}")
            return f"Copied to: {dest_path}"
    except Exception as e:
        return f"Copy failed: {e}"


def copy_files_by_extension(extension: str, source_dir: str, dest_dir: str) -> str:
    """Copy all files with a given extension from source to destination."""
    source_dir = _resolve_path(source_dir)
    dest_dir = _resolve_path(dest_dir)

    if not os.path.exists(source_dir):
        return f"Source directory not found: {source_dir}"

    os.makedirs(dest_dir, exist_ok=True)

    ext = extension.lower().strip('.')
    count = 0
    for f in os.listdir(source_dir):
        if f.lower().endswith(f'.{ext}'):
            src = os.path.join(source_dir, f)
            dst = os.path.join(dest_dir, f)
            shutil.copy2(src, dst)
            count += 1

    return f"Copied {count} .{ext} files from {source_dir} to {dest_dir}"


# ── Move Operations ───────────────────────────────────────────────────────────

def move_file(source: str, destination: str) -> str:
    """Move a file or folder from source to destination."""
    source = _resolve_path(source)
    destination = _resolve_path(destination)

    if not os.path.exists(source):
        found = _find_file(source)
        if found:
            source = found
        else:
            return f"File not found: {source}"

    if not _is_safe_path(source):
        return f"Cannot move from protected path: {source}"

    if os.path.isdir(destination):
        dest_path = os.path.join(destination, os.path.basename(source))
    else:
        dest_dir = os.path.dirname(destination)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        dest_path = destination

    try:
        shutil.move(source, dest_path)
        log.info(f"Moved: {source} → {dest_path}")
        return f"Moved to: {dest_path}"
    except Exception as e:
        return f"Move failed: {e}"


def move_files_by_extension(extension: str, source_dir: str, dest_dir: str) -> str:
    """Move all files with a given extension from source to destination."""
    source_dir = _resolve_path(source_dir)
    dest_dir = _resolve_path(dest_dir)

    if not os.path.exists(source_dir):
        return f"Source directory not found: {source_dir}"

    os.makedirs(dest_dir, exist_ok=True)

    ext = extension.lower().strip('.')
    count = 0
    for f in os.listdir(source_dir):
        if f.lower().endswith(f'.{ext}'):
            src = os.path.join(source_dir, f)
            dst = os.path.join(dest_dir, f)
            shutil.move(src, dst)
            count += 1

    return f"Moved {count} .{ext} files from {source_dir} to {dest_dir}"


# ── Rename Operations ─────────────────────────────────────────────────────────

def rename_file(source: str, new_name: str) -> str:
    """Rename a file or folder."""
    source = _resolve_path(source)

    if not os.path.exists(source):
        found = _find_file(source)
        if found:
            source = found
        else:
            return f"File not found: {source}"

    directory = os.path.dirname(source)
    new_path = os.path.join(directory, new_name)

    if os.path.exists(new_path):
        return f"A file named '{new_name}' already exists in {directory}"

    try:
        os.rename(source, new_path)
        log.info(f"Renamed: {source} → {new_path}")
        return f"Renamed to: {new_path}"
    except Exception as e:
        return f"Rename failed: {e}"


# ── Delete Operations ─────────────────────────────────────────────────────────

def delete_file(path: str) -> str:
    """Delete a file (NOT folders — too dangerous for voice commands)."""
    path = _resolve_path(path)

    if not os.path.exists(path):
        found = _find_file(path)
        if found:
            path = found
        else:
            return f"File not found: {path}"

    if not _is_safe_path(path):
        return f"Cannot delete from protected path: {path}"

    if os.path.isdir(path):
        return f"Cannot delete folders via voice command for safety. Use File Explorer to delete: {path}"

    try:
        os.remove(path)
        log.info(f"Deleted: {path}")
        return f"Deleted: {path}"
    except Exception as e:
        return f"Delete failed: {e}"


def delete_files_by_pattern(pattern: str, directory: str) -> str:
    """Delete files matching a pattern (e.g., *.tmp, *.log)."""
    directory = _resolve_path(directory)

    if not os.path.exists(directory):
        return f"Directory not found: {directory}"

    if not _is_safe_path(directory):
        return f"Cannot delete from protected path: {directory}"

    matches = glob.glob(os.path.join(directory, pattern))
    count = 0
    for f in matches:
        if os.path.isfile(f):
            os.remove(f)
            count += 1

    log.info(f"Deleted {count} files matching '{pattern}' in {directory}")
    return f"Deleted {count} files matching '{pattern}' in {directory}"


# ── Folder Operations ─────────────────────────────────────────────────────────

def create_folder(name: str, directory: str = "") -> str:
    """Create a new folder."""
    directory = _resolve_path(directory) if directory else os.path.expanduser("~/Desktop")

    folder_path = os.path.join(directory, name)

    if os.path.exists(folder_path):
        return f"Folder already exists: {folder_path}"

    try:
        os.makedirs(folder_path, exist_ok=True)
        log.info(f"Created folder: {folder_path}")
        return f"Created folder: {folder_path}"
    except Exception as e:
        return f"Failed to create folder: {e}"


def create_folder_structure(folders: list, base_dir: str = "") -> str:
    """Create multiple folders/subfolders."""
    base_dir = _resolve_path(base_dir) if base_dir else os.path.expanduser("~/Desktop")

    created = []
    for folder in folders:
        path = os.path.join(base_dir, folder)
        os.makedirs(path, exist_ok=True)
        created.append(folder)

    return f"Created {len(created)} folders in {base_dir}: {', '.join(created)}"


# ── Zip Operations ────────────────────────────────────────────────────────────

def zip_folder(source: str, output: str = "") -> str:
    """Zip a folder or file."""
    source = _resolve_path(source)

    if not os.path.exists(source):
        found = _find_file(source)
        if found:
            source = found
        else:
            return f"Not found: {source}"

    if not output:
        # Default: save zip to Desktop with same name
        basename = os.path.basename(source.rstrip('/\\'))
        desktop = os.path.expanduser("~/Desktop")
        output = os.path.join(desktop, f"{basename}.zip")
    else:
        output = _resolve_path(output)
        # If output is a directory, create zip filename inside it
        if os.path.isdir(output) or output.endswith('/') or output.endswith('\\'):
            os.makedirs(output, exist_ok=True)
            basename = os.path.basename(source.rstrip('/\\'))
            output = os.path.join(output, f"{basename}.zip")
        # Ensure output ends with .zip
        if not output.lower().endswith('.zip'):
            output = output + '.zip'

    # Ensure output directory exists
    out_dir = os.path.dirname(output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    try:
        if os.path.isdir(source):
            # shutil.make_archive expects path WITHOUT .zip extension
            archive_base = output[:-4]  # Remove .zip
            shutil.make_archive(archive_base, 'zip', source)
        else:
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(source, os.path.basename(source))

        log.info(f"Zipped: {source} → {output}")
        return f"Zipped to: {output}"
    except Exception as e:
        return f"Zip failed: {e}"


def unzip_file(source: str, destination: str = "") -> str:
    """Extract a zip file."""
    source = _resolve_path(source)

    if not os.path.exists(source):
        found = _find_file(source)
        if found:
            source = found
        else:
            return f"Zip file not found: {source}"

    if not destination:
        destination = os.path.splitext(source)[0]

    try:
        with zipfile.ZipFile(source, 'r') as zf:
            zf.extractall(destination)

        log.info(f"Extracted: {source} → {destination}")
        return f"Extracted to: {destination}"
    except Exception as e:
        return f"Unzip failed: {e}"


# ── List / Search Operations ──────────────────────────────────────────────────

def list_large_files(directory: str = "", min_size_mb: int = 100) -> str:
    """List files larger than a given size."""
    directory = _resolve_path(directory) if directory else os.path.expanduser("~/Downloads")

    if not os.path.exists(directory):
        return f"Directory not found: {directory}"

    large_files = []
    for root, dirs, files in os.walk(directory):
        depth = root.replace(directory, '').count(os.sep)
        if depth > 3:
            dirs.clear()
            continue
        for f in files:
            filepath = os.path.join(root, f)
            try:
                size = os.path.getsize(filepath)
                if size > min_size_mb * 1024 * 1024:
                    large_files.append((filepath, size))
            except OSError:
                continue

    large_files.sort(key=lambda x: x[1], reverse=True)

    if not large_files:
        return f"No files larger than {min_size_mb}MB found in {directory}"

    result = f"Large files in {directory} (>{min_size_mb}MB):\n"
    for path, size in large_files[:20]:
        size_mb = size / (1024 * 1024)
        result += f"  {size_mb:.1f}MB — {path}\n"

    return result


def find_duplicates(directory: str = "") -> str:
    """Find duplicate files by name in a directory."""
    directory = _resolve_path(directory) if directory else os.path.expanduser("~/Documents")

    if not os.path.exists(directory):
        return f"Directory not found: {directory}"

    file_map = {}
    for root, dirs, files in os.walk(directory):
        depth = root.replace(directory, '').count(os.sep)
        if depth > 3:
            dirs.clear()
            continue
        for f in files:
            name_lower = f.lower()
            filepath = os.path.join(root, f)
            if name_lower not in file_map:
                file_map[name_lower] = []
            file_map[name_lower].append(filepath)

    duplicates = {k: v for k, v in file_map.items() if len(v) > 1}

    if not duplicates:
        return f"No duplicate files found in {directory}"

    result = f"Found {len(duplicates)} duplicate file names in {directory}:\n"
    for name, paths in list(duplicates.items())[:15]:
        result += f"  {name}:\n"
        for p in paths:
            result += f"    - {p}\n"

    return result


# ── Cleanup Operations ────────────────────────────────────────────────────────

def cleanup_desktop() -> str:
    """Organize desktop by moving files to appropriate folders."""
    desktop = os.path.expanduser("~/Desktop")

    categories = {
        "Images": ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp'],
        "Documents": ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.txt'],
        "Videos": ['.mp4', '.avi', '.mkv', '.mov', '.wmv'],
        "Music": ['.mp3', '.wav', '.flac', '.aac', '.m4a'],
        "Archives": ['.zip', '.rar', '.7z', '.tar', '.gz'],
        "Code": ['.py', '.js', '.jsx', '.ts', '.html', '.css', '.java', '.cpp', '.c'],
        "Installers": ['.exe', '.msi', '.dmg'],
    }

    moved = {}
    for f in os.listdir(desktop):
        filepath = os.path.join(desktop, f)
        if os.path.isdir(filepath):
            continue

        ext = os.path.splitext(f)[1].lower()
        for category, extensions in categories.items():
            if ext in extensions:
                dest_dir = os.path.join(desktop, category)
                os.makedirs(dest_dir, exist_ok=True)
                shutil.move(filepath, os.path.join(dest_dir, f))
                moved[category] = moved.get(category, 0) + 1
                break

    if not moved:
        return "Desktop is already clean — no files to organize."

    result = "Desktop organized:\n"
    for cat, count in moved.items():
        result += f"  {cat}: {count} files moved\n"

    return result
