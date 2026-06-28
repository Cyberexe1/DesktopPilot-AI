# ── DesktopPilot AI — Cloud API image (AWS App Runner) ──────────────────────
FROM python:3.11-slim

# System libs PyAV/ffmpeg need at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching
COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

# Copy only the cloud-safe code (see .dockerignore for exclusions)
COPY cloud_api.py .
COPY app_paths.py .
COPY ai/        ./ai/
COPY voice/     ./voice/
COPY controllers/auth_controller.py ./controllers/auth_controller.py
COPY controllers/knowledge_controller.py ./controllers/knowledge_controller.py
COPY controllers/__init__.py        ./controllers/__init__.py
COPY database/  ./database/

# Cloud never loads the local Whisper model
ENV WHISPER_MODEL=disabled \
    PYTHONUNBUFFERED=1 \
    AWS_DEFAULT_REGION=us-east-1

# App Runner sends traffic to port 8080 by default
EXPOSE 8080

CMD ["uvicorn", "cloud_api:app", "--host", "0.0.0.0", "--port", "8080"]
