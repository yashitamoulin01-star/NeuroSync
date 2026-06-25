FROM python:3.11-slim

WORKDIR /app

# System dependencies for OpenCV, MediaPipe, and audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies before copying source to leverage layer cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY backend/ ./backend/
COPY ml/ ./ml/
COPY models/ ./models/

# Data directory for SQLite and dataset files
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DATASET_DIR=/app/data \
    WHISPER_DEVICE=cpu

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/system/liveness')"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
