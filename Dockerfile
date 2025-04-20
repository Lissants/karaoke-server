FROM python:3.11-slim-bookworm

# 1. Install FFmpeg with all runtime dependencies
RUN apt-get update && \
    apt-get install -y \
        ffmpeg \
        libsm6 \
        libxext6 \
        libgl1-mesa-glx && \
        rm -rf /var/lib/apt/lists/*

# 2. Verify FFmpeg is in PATH and works
RUN ffmpeg -version && which ffmpeg  # Should show /usr/bin/ffmpeg

WORKDIR /app
COPY . .

# 3. Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 4. Create symlink to expected location
RUN ln -s /usr/bin/ffmpeg /usr/local/bin/ffmpeg

# 5. Run with explicit PATH
CMD ["sh", "-c", "export PATH=/usr/bin:$PATH && gunicorn --bind 0.0.0.0:${PORT:-5000} --timeout 120 --workers 1 local-server:app"]
