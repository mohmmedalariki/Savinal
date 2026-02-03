FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
# ffmpeg is crucial for yt-dlp
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies first for caching
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source code
COPY src/ src/
COPY .env.example .

# Run the bot
CMD ["python", "-m", "src.bot"]
