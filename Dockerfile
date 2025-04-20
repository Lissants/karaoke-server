FROM python:3.11-slim-bookworm

# 1. Install FFmpeg and dependencies
RUN apt-get update && \
    apt-get install -y \
        ffmpeg \
        libsm6 \
        libxext6 \
        libgl1-mesa-glx \
        libsndfile1 && \
    rm -rf /var/lib/apt/lists/*

# 2. Verify FFmpeg installation
RUN ffmpeg -version && which ffmpeg

WORKDIR /app
COPY . .

# 3. Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 4. Use the correct FFmpeg path (/usr/bin/ffmpeg)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "600", "--workers", "1", "local-server:app"]
