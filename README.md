# Savinal 🤖

> A robust, privacy-focused Telegram bot for downloading videos from YouTube, Twitter, Instagram, TikTok, and more.

## Features
- 🎥 **Multi-Platform**: Support for YouTube, X (Twitter), Instagram, TikTok, Reddit, Vimeo, etc.
- ⚙️ **Quality Selection**: Choose from available resolutions (1080p, 720p, 480p) or Audio Only.
- 🚀 **High Performance**: Asynchronous downloads with `yt-dlp` and `ffmpeg`.
- ☁️ **Large File Handling**: Automatically uploads files >45MB to S3 and provides a secure link.
- 🐳 **Docker Ready**: One-command deployment.
- 🔒 **Secure**: URL validation, timeout protection, and temp file cleanup.

## Quick Start

### 1. Clone & Configure
```bash
git clone https://github.com/yourusername/savinal.git
cd savinal
cp .env.example .env
```
Edit `.env` and add your `TELEGRAM_BOT_TOKEN` (from @BotFather).

### 2. Run with Docker (Recommended)
```bash
docker-compose up -d
```

### 3. Run Locally (Dev)
Requires Python 3.11+ and `ffmpeg`.
```bash
pip install .
python src/bot.py
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot API Token | Required |
| `MAX_CONCURRENT_DOWNLOADS` | Max parallel downloads | `3` |
| `MAX_TELEGRAM_FILE_MB` | Max size for direct upload | `45` |
| `S3_BUCKET` | S3 Bucket Name (for large files) | Optional |
| `AWS_ACCESS_KEY_ID` | AWS Key | Optional |
| `AWS_SECRET_ACCESS_KEY` | AWS Secret | Optional |

## Usage Examples

**1. Standard Download**
> **User**: *Sends https://youtu.be/...*
> **Savinal**: "Got it — checking available formats..."
> **Savinal**: *Shows buttons: [1080p ~120MB] [720p ~50MB] [Audio Only]*
> **User**: *Taps [720p]*
> **Savinal**: "Downloading... 45%... Uploading... Done! ✅" *Sends Video*

**2. Audio Extraction**
> **User**: /start
> **Savinal**: "Hi! Send me a link."
> **User**: *Sends Music Video URL*
> **User**: *Taps [Audio Only (MP3)]*
> **Savinal**: *Sends MP3 file with correct metadata*

**3. Large File Handling**
> **User**: *Selects 4K Video (800MB)*
> **Savinal**: "File too large for Telegram. Uploading to external storage..."
> **Savinal**: "Here is your download link (valid for 24h): https://s3..."

## Troubleshooting
- **"ffmpeg not found"**: Ensure `ffmpeg` is installed on your system or use Docker.
- **"Download Error"**: Some sites block data center IPs. Try running locally or use cookies with yt-dlp (advanced config).

## License
MIT
