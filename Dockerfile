FROM python:3.11

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
        ffmpeg \
        libsm6 \
        libxext6 \
        libgl1-mesa-glx \
        libsndfile1 \  # Required for audio file I/O
        gcc \          # Needed for compiling some Python packages
        g++ \          # Needed for compiling some Python packages
        make && \
        rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Install Python dependencies with build tools first
RUN pip install --no-cache-dir -r requirements.txt

CMD ["gunicorn", "--bind", "0.0.0.0:${PORT:-5000}", "--timeout", "600", "--workers", "1", "local-server:app"]
