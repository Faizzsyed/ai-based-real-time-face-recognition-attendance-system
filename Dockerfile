# Minimal Dockerfile for AttendAI Backend
# Usage: docker build -t attendai-backend .

FROM python:3.11-slim

# Prevent Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE=1
# Prevent Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies if required for OpenCV or Face models (YuNet/SFace)
# Minimal requirements for opencv-python-headless
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    tzdata \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY backend/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY backend /app/backend
COPY models /app/models
COPY scripts/download_face_models.py /app/scripts/download_face_models.py
# All three assets are fetched from authoritative sources and SHA-256 checked.
# This must fail the build if a download is missing, truncated or modified.
RUN python /app/scripts/download_face_models.py

# Create data directory if needed by the app
RUN mkdir -p /app/data

# Run as a non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Start Uvicorn
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --app-dir /app/backend --host 0.0.0.0 --port \"${PORT:-${API_PORT:-8000}}\" --proxy-headers"]
