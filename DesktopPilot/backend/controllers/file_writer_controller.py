"""
File Writer Controller — creates files of any type and opens them in the correct app.
Supports: txt, docx, pptx, html, css, js, py, jsx, tsx, json, md, and more.
"""

import logging
import os
import subprocess

log = logging.getLogger(__name__)

_USER = os.environ.get("USERNAME", "User")

ALLOWED_DIRS = [
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Downloads"),
    rf"C:\Users\{_USER}\Desktop",
    rf"C:\Users\{_USER}\Documents",
    rf"C:\Users\{_USER}\Downloads",
    rf"C:\Users\{_USER}\Projects",
    "D:/Projects",
    "C:/Projects",
]

# Map file extensions to the app that should open them
EXT_TO_APP = {
    # Text editors
    ".txt":  "notepad",
    ".log":  "notepad",
    ".ini":  "notepad",
    # Microsoft Office
    ".docx": "word",
    ".doc":  "word",
    ".pptx": "powerpoint",
    ".ppt":  "powerpoint",
    ".xlsx": "excel",
    ".xls":  "excel",
    # Code files → VS Code
    ".html": "vscode",
    ".css":  "vscode",
    ".js":   "vscode",
    ".jsx":  "vscode",
    ".ts":   "vscode",
    ".tsx":  "vscode",
    ".py":   "vscode",
    ".java": "vscode",
    ".cpp":  "vscode",
    ".c":    "vscode",
    ".json": "vscode",
    ".md":   "vscode",
    ".yaml": "vscode",
    ".yml":  "vscode",
    ".xml":  "vscode",
    ".sql":  "vscode",
    ".sh":   "vscode",
    ".bat":  "vscode",
    ".env":  "vscode",
    ".gitignore": "vscode",
    # PDF
    ".pdf":  "default",
    # Images
    ".png":  "default",
    ".jpg":  "default",
    ".jpeg": "default",
}


def create_file(filename: str, content: str = "", directory: str = "") -> str:
    """
    Create a new file with content and open it in the appropriate application.
    - .txt → opens in Notepad
    - .docx/.pptx/.xlsx → opens in Word/PowerPoint/Excel
    - .html/.css/.js/.py/.jsx etc → opens in VS Code
    """
    # Default to Desktop
    if not directory or directory.lower() == "desktop":
        directory = os.path.expanduser("~/Desktop")
    elif directory.lower() == "documents":
        directory = os.path.expanduser("~/Documents")
    elif directory.lower() == "downloads":
        directory = os.path.expanduser("~/Downloads")

    # Create directory if it doesn't exist (for project scaffolding)
    if not os.path.exists(directory):
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as e:
            return f"Cannot create directory: {e}"

    # Safety check
    real_dir = os.path.realpath(directory)
    allowed = any(
        real_dir.startswith(os.path.realpath(d))
        for d in ALLOWED_DIRS if os.path.exists(d)
    )
    if not allowed:
        return f"Cannot create files in: {directory} (not in allowed directories)"

    # Sanitize filename (allow dots, dashes, underscores)
    safe_name = "".join(c for c in filename if c.isalnum() or c in '._-/ ')
    if not safe_name:
        return "Invalid filename"

    filepath = os.path.join(directory, safe_name)

    # Create parent directories if needed (for nested paths like src/App.jsx)
    parent = os.path.dirname(filepath)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)

    try:
        ext = os.path.splitext(safe_name)[1].lower()

        if ext == ".docx":
            _create_docx(filepath, content)
        elif ext == ".pptx":
            _create_pptx(filepath, content)
        elif ext == ".xlsx":
            _create_xlsx(filepath, content)
        else:
            # Plain text files (txt, html, css, js, py, etc.)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

        log.info(f"Created: {filepath}")
    except Exception as e:
        return f"Failed to create file: {e}"

    # Open in the correct application
    result = _open_in_correct_app(filepath)
    return f"Created and opened: {filepath}"


def create_project(project_name: str, framework: str, directory: str = "") -> str:
    """
    Scaffold a project structure and open in VS Code.
    Supports: vite, nextjs, nodejs, python, html
    """
    if not directory:
        directory = os.path.expanduser("~/Desktop")

    project_dir = os.path.join(directory, project_name)

    if os.path.exists(project_dir):
        # Just open existing project
        _open_in_vscode(project_dir)
        return f"Project already exists, opened in VS Code: {project_dir}"

    os.makedirs(project_dir, exist_ok=True)

    fw = framework.lower()

    if fw in ("vite", "react", "react-vite"):
        _scaffold_vite(project_dir, project_name)
    elif fw in ("nextjs", "next", "next.js"):
        _scaffold_nextjs(project_dir, project_name)
    elif fw in ("nodejs", "node", "express"):
        _scaffold_nodejs(project_dir, project_name)
    elif fw in ("python", "flask", "fastapi"):
        _scaffold_python(project_dir, project_name)
    elif fw in ("html", "static", "website"):
        _scaffold_html(project_dir, project_name)
    else:
        # Generic — just create a README
        _write(project_dir, "README.md", f"# {project_name}\n\nProject created by DesktopPilot AI\n")

    _open_in_vscode(project_dir)
    return f"Project scaffolded and opened in VS Code: {project_dir}"


def write_to_file(filepath: str, content: str, mode: str = "w") -> str:
    """Write content to an existing file."""
    if not os.path.exists(filepath):
        return f"File not found: {filepath}"
    try:
        with open(filepath, mode, encoding='utf-8') as f:
            f.write(content)
        return f"Written to: {filepath}"
    except Exception as e:
        return f"Failed to write: {e}"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _open_in_correct_app(filepath: str) -> str:
    """Open a file in the correct application based on extension."""
    ext = os.path.splitext(filepath)[1].lower()
    app = EXT_TO_APP.get(ext, "default")

    if app == "vscode":
        _open_in_vscode(filepath)
    elif app == "notepad":
        subprocess.Popen(["notepad.exe", filepath], shell=False)
    elif app == "word":
        os.startfile(filepath)
    elif app == "powerpoint":
        os.startfile(filepath)
    elif app == "excel":
        os.startfile(filepath)
    else:
        os.startfile(filepath)

    return f"Opened: {filepath}"


def _open_in_vscode(path: str):
    """Open a file or folder in VS Code."""
    try:
        subprocess.Popen(["code", path], shell=False)
    except FileNotFoundError:
        vscode = rf"C:\Users\{_USER}\AppData\Local\Programs\Microsoft VS Code\Code.exe"
        try:
            subprocess.Popen([vscode, path], shell=False)
        except Exception:
            os.startfile(path)


def _write(directory: str, filename: str, content: str):
    """Helper to write a file inside a directory."""
    filepath = os.path.join(directory, filename)
    parent = os.path.dirname(filepath)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


# ── Project scaffolders ───────────────────────────────────────────────────────

# ── Project scaffolders ───────────────────────────────────────────────────────

def _create_docx(filepath: str, content: str):
    """Create a proper .docx Word document."""
    from docx import Document
    doc = Document()
    # Split content by newlines and add as paragraphs
    for line in content.split('\n'):
        if line.strip():
            doc.add_paragraph(line)
        else:
            doc.add_paragraph('')  # Empty paragraph for spacing
    doc.save(filepath)


def _create_pptx(filepath: str, content: str):
    """Create a proper .pptx PowerPoint presentation with slides and optional flowcharts."""
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    prs = Presentation()

    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if not lines:
        lines = ["Presentation created by DesktopPilot AI"]

    # First slide — title
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = lines[0]
    if len(lines) > 1:
        slide.placeholders[1].text = lines[1]

    # Check if content requests a flowchart
    full_text = content.lower()
    has_flowchart = any(kw in full_text for kw in ['flowchart', 'flow chart', 'diagram', 'process flow', 'steps:'])

    if has_flowchart:
        # Create a flowchart slide
        _add_flowchart_slide(prs, lines[2:] if len(lines) > 2 else ["Step 1", "Step 2", "Step 3"])
    else:
        # Regular content slides (group 4 lines per slide)
        remaining = lines[2:] if len(lines) > 2 else []
        for i in range(0, len(remaining), 4):
            chunk = remaining[i:i+4]
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            slide.shapes.title.text = chunk[0]
            body = slide.placeholders[1]
            body.text = '\n'.join(chunk[1:]) if len(chunk) > 1 else ""

    prs.save(filepath)


def _add_flowchart_slide(prs, steps: list):
    """Add a slide with a vertical flowchart (boxes + arrows)."""
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.enum.shapes import MSO_SHAPE

    slide = prs.slides.add_slide(prs.slide_layouts[5])  # Blank layout

    # Add title
    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(0.6))
    tf = txBox.text_frame
    tf.text = "Process Flow"
    tf.paragraphs[0].font.size = Pt(24)
    tf.paragraphs[0].font.bold = True

    # Calculate positions for boxes
    max_steps = min(len(steps), 6)  # Max 6 steps per slide
    box_width = Inches(2.5)
    box_height = Inches(0.7)
    start_x = Inches(3.5)
    start_y = Inches(1.2)
    gap_y = Inches(1.1)

    # Colors for boxes
    colors = [
        RGBColor(0x4F, 0x8E, 0xF7),  # Blue
        RGBColor(0x22, 0xC5, 0x5E),  # Green
        RGBColor(0x7C, 0x5C, 0xFC),  # Purple
        RGBColor(0xF5, 0x9E, 0x0B),  # Orange
        RGBColor(0xEF, 0x44, 0x44),  # Red
        RGBColor(0x06, 0xB6, 0xD4),  # Cyan
    ]

    for i in range(max_steps):
        step_text = steps[i] if i < len(steps) else f"Step {i+1}"
        y = start_y + (gap_y * i)

        # Draw box
        shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            start_x, y, box_width, box_height
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = colors[i % len(colors)]
        shape.line.color.rgb = colors[i % len(colors)]

        # Add text to box
        tf = shape.text_frame
        tf.text = step_text
        tf.paragraphs[0].font.size = Pt(12)
        tf.paragraphs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        tf.paragraphs[0].font.bold = True
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER

        # Draw arrow to next box (except last)
        if i < max_steps - 1:
            arrow_y = y + box_height
            arrow_x = start_x + (box_width / 2) - Inches(0.05)
            connector = slide.shapes.add_shape(
                MSO_SHAPE.DOWN_ARROW,
                arrow_x, arrow_y, Inches(0.3), Inches(0.35)
            )
            connector.fill.solid()
            connector.fill.fore_color.rgb = RGBColor(0x64, 0x74, 0x8B)
            connector.line.fill.background()


def _create_xlsx(filepath: str, content: str):
    """Create a proper .xlsx Excel spreadsheet."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    # Split content into rows (by newline) and columns (by comma or tab)
    for row_idx, line in enumerate(content.split('\n'), start=1):
        if not line.strip():
            continue
        # Try comma-separated first, then tab, then single cell
        if ',' in line:
            cells = line.split(',')
        elif '\t' in line:
            cells = line.split('\t')
        else:
            cells = [line]

        for col_idx, cell in enumerate(cells, start=1):
            ws.cell(row=row_idx, column=col_idx, value=cell.strip())

    wb.save(filepath)


def _scaffold_vite(d: str, name: str):
    _write(d, "package.json", f'''{{"name": "{name}", "version": "1.0.0", "scripts": {{"dev": "vite", "build": "vite build"}}, "dependencies": {{"react": "^18.3.1", "react-dom": "^18.3.1"}}, "devDependencies": {{"vite": "^5.3.1", "@vitejs/plugin-react": "^4.3.1"}}}}''')
    _write(d, "index.html", f'''<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8" />\n  <title>{name}</title>\n</head>\n<body>\n  <div id="root"></div>\n  <script type="module" src="/src/main.jsx"></script>\n</body>\n</html>''')
    _write(d, "vite.config.js", "import { defineConfig } from 'vite'\nimport react from '@vitejs/plugin-react'\n\nexport default defineConfig({ plugins: [react()] })\n")
    _write(d, "src/main.jsx", "import React from 'react'\nimport ReactDOM from 'react-dom/client'\nimport App from './App'\n\nReactDOM.createRoot(document.getElementById('root')).render(<App />)\n")
    _write(d, "src/App.jsx", f"export default function App() {{\n  return <h1>{name}</h1>\n}}\n")


def _scaffold_nextjs(d: str, name: str):
    _write(d, "package.json", f'''{{"name": "{name}", "version": "1.0.0", "scripts": {{"dev": "next dev", "build": "next build", "start": "next start"}}, "dependencies": {{"next": "^14.0.0", "react": "^18.3.1", "react-dom": "^18.3.1"}}}}''')
    _write(d, "app/page.jsx", f"export default function Home() {{\n  return <h1>Welcome to {name}</h1>\n}}\n")
    _write(d, "app/layout.jsx", f"export default function RootLayout({{ children }}) {{\n  return <html><body>{{children}}</body></html>\n}}\n")


def _scaffold_nodejs(d: str, name: str):
    _write(d, "package.json", f'''{{"name": "{name}", "version": "1.0.0", "main": "index.js", "scripts": {{"start": "node index.js", "dev": "nodemon index.js"}}, "dependencies": {{"express": "^4.18.2"}}}}''')
    _write(d, "index.js", "const express = require('express')\nconst app = express()\n\napp.get('/', (req, res) => res.send('Hello World'))\n\napp.listen(3000, () => console.log('Server running on port 3000'))\n")


def _scaffold_python(d: str, name: str):
    _write(d, "requirements.txt", "fastapi==0.111.0\nuvicorn==0.30.1\n")
    _write(d, "main.py", "from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/')\ndef root():\n    return {'message': 'Hello World'}\n")
    _write(d, "README.md", f"# {name}\n\nRun: `uvicorn main:app --reload`\n")


def _scaffold_html(d: str, name: str):
    _write(d, "index.html", f"<!DOCTYPE html>\n<html>\n<head>\n  <title>{name}</title>\n  <link rel='stylesheet' href='style.css'>\n</head>\n<body>\n  <h1>{name}</h1>\n  <script src='script.js'></script>\n</body>\n</html>\n")
    _write(d, "style.css", "body { font-family: sans-serif; margin: 2rem; }\nh1 { color: #333; }\n")
    _write(d, "script.js", "console.log('Hello from " + name + "')\n")
