FROM python:3.11-slim-bookworm

# Install FFmpeg first (no GLIBC conflicts)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Debug points
RUN echo "### BUILD COMPLETE ###" && \
    ffmpeg -version && \
    python -c "import sys; print('\nPython Path:', sys.path)"

CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "--timeout", "120", "--workers", "1", "local-server:app"]
