"""
src/messages.py
Centralized module for user-facing messages to support consistency and localization.
"""

START_MESSAGE = (
    "Hi — I'm Savinal. Send me a video link and I'll show download options. "
    "Use /audio to get audio-only."
)

CHECKING_URL = "Got it — checking available formats..."

SELECT_FORMAT = "Choose the quality you want for:\n{title}"

DOWNLOADING = "Downloading — please wait. Progress: {percent}%"

FILE_TOO_LARGE = (
    "That file is too large for Telegram (>{limit}MB). "
    "I can: 1) provide an external download link, 2) send audio-only, 3) cancel. Choose below."
)

ERROR_GENERIC = "Sorry — I couldn't download that. Reason: {reason}. Try another link or /help."

ERROR_INVALID_URL = "That doesn't look like a supported URL. Please check the link."

ERROR_TIMEOUT = "The download took too long and was cancelled."

PROCESSING = "Processing media..."

UPLOADING = "Uploading to Telegram..."

UPLOADING_S3 = "File too large for Telegram. Uploading to external storage..."
S3_LINK_READY = "Here is your download link (valid for 24h):\n{url}"

CANCELED = "Download cancelled."
