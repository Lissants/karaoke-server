FROM python:3.11-slim-bookworm

# 1. Install FFmpeg first (with dependencies)
RUN apt-get update && \
    apt-get install -y ffmpeg libsm6 libxext6 && \
    rm -rf /var/lib/apt/lists/*

# 2. Verify installation
RUN ffmpeg -version

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt

CMD ["gunicorn", "--bind", "0.0.0.0:${PORT:-5000}", "--timeout", "120", "--workers", "1", "local-server:app"]
