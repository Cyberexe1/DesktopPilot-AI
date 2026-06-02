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
            # For presentations, enrich content if too sparse
            enriched = _enrich_pptx_content(content, safe_name)
            _create_pptx(filepath, enriched)
        elif ext == ".xlsx":
            _create_xlsx(filepath, content)
        else:
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


def _enrich_pptx_content(content: str, filename: str) -> str:
    """
    If AI-generated content is too sparse, call Bedrock AGAIN
    to generate detailed presentation content (plain text, not JSON).
    """
    lines = [l.strip() for l in content.split('\n') if l.strip()]

    # If content is already rich (>20 lines with bullets), use as-is
    bullet_count = sum(1 for l in lines if l.startswith('•'))
    if bullet_count >= 15:
        return content

    # Extract topic from filename or content
    topic = filename.replace('.pptx', '').replace('.', ' ').strip()
    if lines:
        topic = lines[0]  # First line is usually the topic

    # Check for flowchart request
    full_lower = content.lower()
    has_flowchart = any(kw in full_lower for kw in ['flowchart', 'flow chart', 'diagram', 'process flow'])

    # Determine number of slides from content or default to 4
    num_slides = max(3, len([l for l in lines if len(l) < 50 and not l.startswith('•')]))
    num_slides = min(num_slides, 8)  # Max 8 content sections (+ title + flowchart = 10 max)

    # Extra instructions from original content
    extra = ""
    if has_flowchart:
        extra += "Include a section listing process steps for a flowchart. "
    if lines[1:]:
        extra += f"Key points to cover: {', '.join(lines[1:5])}"

    # ── SECOND BEDROCK CALL — generate rich content ──
    from ai.content_generator import generate_content

    log.info(f"Calling Bedrock again for presentation content: '{topic}'")
    rich_content = generate_content(
        topic=topic,
        content_type="presentation",
        num_slides=num_slides,
        extra_instructions=extra,
    )

    # Append flowchart keyword if requested
    if has_flowchart and "flowchart" not in rich_content.lower():
        # Extract step-like lines for the flowchart
        flowchart_lines = [l for l in lines if len(l) < 40 and not l.startswith('•')]
        if len(flowchart_lines) > 2:
            rich_content += "\nflowchart\n" + "\n".join(flowchart_lines[1:])
        else:
            rich_content += "\nflowchart\nData Collection\nProcessing\nAnalysis\nAction\nMonitoring"

    return rich_content


def _create_pptx(filepath: str, content: str):
    """Create a proper .pptx presentation — 70%+ slide coverage, rich content."""
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    prs = Presentation()

    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if not lines:
        lines = ["Presentation created by DesktopPilot AI"]

    # Check for flowchart
    full_text = content.lower()
    has_flowchart = any(kw in full_text for kw in ['flowchart', 'flow chart', 'diagram', 'process flow', 'steps:'])

    # Separate content from flowchart keywords
    content_lines = []
    for line in lines:
        if line.lower() in ['flowchart', 'flow chart', 'diagram', 'process flow', 'steps:']:
            continue
        content_lines.append(line)

    # ── Slide 1: Title slide ──
    title = content_lines[0] if content_lines else "Untitled"
    subtitle = content_lines[1] if len(content_lines) > 1 else "Created by DesktopPilot AI"

    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = title
    if slide.placeholders[1]:
        slide.placeholders[1].text = subtitle

    # ── Content slides — dense, 5-7 bullets per slide ──
    remaining = content_lines[2:] if len(content_lines) > 2 else []

    # Group lines: first line of each group is title, rest are bullets
    # Strategy: every line that looks like a heading starts a new slide
    slides_data = []
    current_slide = {"title": "", "bullets": []}

    for line in remaining:
        # Detect if line is a heading (no bullet marker, shorter, capitalized)
        is_heading = (
            not line.startswith(('•', '-', '*', '·')) and
            len(line) < 60 and
            not line[0].islower() if line else False
        )

        if is_heading and current_slide["title"]:
            # Save current slide and start new one
            slides_data.append(current_slide)
            current_slide = {"title": line, "bullets": []}
        elif is_heading and not current_slide["title"]:
            current_slide["title"] = line
        else:
            # It's a bullet point
            bullet = line.lstrip('•-*· ')
            if bullet:
                current_slide["bullets"].append(bullet)

    # Don't forget the last slide
    if current_slide["title"] or current_slide["bullets"]:
        slides_data.append(current_slide)

    # If no structured slides found, split remaining into chunks of 5
    if not slides_data and remaining:
        for i in range(0, len(remaining), 5):
            chunk = remaining[i:i+5]
            slides_data.append({
                "title": chunk[0],
                "bullets": chunk[1:] if len(chunk) > 1 else ["Content for this section"]
            })

    # Create each content slide (cap at 8 content slides)
    for sd in slides_data[:8]:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = sd["title"] or "Content"

        # Fill the body with bullets
        body = slide.placeholders[1]
        tf = body.text_frame
        tf.clear()

        for i, bullet in enumerate(sd["bullets"]):
            if i == 0:
                tf.text = bullet
            else:
                p = tf.add_paragraph()
                p.text = bullet
            # Style each paragraph
            para = tf.paragraphs[i]
            para.font.size = Pt(16)
            para.space_after = Pt(8)

    # ── Flowchart slide ──
    if has_flowchart:
        steps = remaining if remaining else ["Step 1", "Step 2", "Step 3", "Step 4", "Step 5"]
        # Use headings as flowchart steps if available
        if slides_data:
            steps = [sd["title"] for sd in slides_data if sd["title"]]
        _add_flowchart_slide(prs, steps)

    # Ensure minimum 3 content slides
    while len(prs.slides) < 4:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = f"Additional Details"
        body = slide.placeholders[1]
        body.text = "• More information can be added here\n• Supporting data and examples\n• References and resources"

    # Hard limit: max 10 slides total
    while len(prs.slides) > 10:
        rId = prs.slides._sldIdLst[-1].rId
        prs.part.drop_rel(rId)
        del prs.slides._sldIdLst[-1]

    prs.save(filepath)


def _add_flowchart_slide(prs, steps: list):
    """Add a slide with a vertical flowchart that FITS within slide boundaries."""
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.enum.shapes import MSO_SHAPE

    slide = prs.slides.add_slide(prs.slide_layouts[5])  # Blank layout

    # Title
    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(9), Inches(0.5))
    tf = txBox.text_frame
    tf.text = "Process Flow"
    tf.paragraphs[0].font.size = Pt(22)
    tf.paragraphs[0].font.bold = True

    # Layout constants — designed to fit within standard 10x7.5 inch slide
    max_steps = min(len(steps), 7)  # Max 7 steps to fit on one slide
    box_width = Inches(3.0)
    box_height = Inches(0.55)
    arrow_height = Inches(0.25)

    # Calculate total height needed and center vertically
    total_height = (max_steps * box_height) + ((max_steps - 1) * arrow_height)
    available_height = Inches(6.5)  # Slide height minus title and margins
    start_y = Inches(0.9) + (available_height - total_height) / 2
    start_x = (Inches(10) - box_width) / 2  # Center horizontally

    # Clamp start_y to minimum
    if start_y < Inches(0.8):
        start_y = Inches(0.8)

    # Colors for boxes
    colors = [
        RGBColor(0x4F, 0x8E, 0xF7),  # Blue
        RGBColor(0x22, 0xC5, 0x5E),  # Green
        RGBColor(0x7C, 0x5C, 0xFC),  # Purple
        RGBColor(0xF5, 0x9E, 0x0B),  # Orange
        RGBColor(0xEF, 0x44, 0x44),  # Red
        RGBColor(0x06, 0xB6, 0xD4),  # Cyan
        RGBColor(0xEC, 0x48, 0x99),  # Pink
    ]

    for i in range(max_steps):
        step_text = steps[i] if i < len(steps) else f"Step {i+1}"
        y = start_y + (i * (box_height + arrow_height))

        # Ensure we don't go off the slide (7.5 inches total height)
        if y + box_height > Inches(7.2):
            break

        # Draw rounded rectangle box
        shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            start_x, y, box_width, box_height
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = colors[i % len(colors)]
        shape.line.color.rgb = colors[i % len(colors)]

        # Text inside box
        tf = shape.text_frame
        tf.word_wrap = True
        tf.text = step_text
        tf.paragraphs[0].font.size = Pt(11)
        tf.paragraphs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        tf.paragraphs[0].font.bold = True
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER

        # Arrow to next box (except last)
        if i < max_steps - 1:
            arrow_y = y + box_height
            arrow_x = start_x + (box_width / 2) - Inches(0.12)
            # Only add arrow if it fits
            if arrow_y + arrow_height < Inches(7.2):
                connector = slide.shapes.add_shape(
                    MSO_SHAPE.DOWN_ARROW,
                    arrow_x, arrow_y, Inches(0.24), arrow_height
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
