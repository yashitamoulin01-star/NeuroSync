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

# Install Python dependencies before copying source to leverage layer cache.
# The canonical manifest lives at backend/requirements.txt.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source. Trained model weights (*.pt/*.pkl) are gitignored and
# not in the image; the app degrades to rule-based/fallback inference without them.
COPY backend/ ./backend/
COPY ml/ ./ml/
COPY models/ ./models/

# Data directory for SQLite + dataset files. Mount a persistent volume here in
# production (e.g. Render/Railway disk) so the database survives restarts.
RUN mkdir -p /app/data
VOLUME ["/app/data"]

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DATASET_DIR=/app/data \
    WHISPER_DEVICE=cpu \
    INFERENCE_DEVICE=cpu \
    PORT=8000

EXPOSE 8000

# Honor the platform-provided $PORT (Render/Railway inject it); default 8000.
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.environ.get('PORT','8000'))"

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
