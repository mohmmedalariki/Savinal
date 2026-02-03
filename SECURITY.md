# Security Policy

## Safe Operation
1. **Bot Token**: Never commit your `.env` file or expose `TELEGRAM_BOT_TOKEN`.
2. **Execution Environment**: Run the bot in a Docker container to isolate it from your host system.
3. **Downloads**:
   - The bot downloads files to a temporary folder (`downloads/`).
   - Files are sanitized (ASCII only) to prevent filesystem exploits.
   - Files are automatically deleted after upload or error.
4. **Limits**:
   - `MAX_CONCURRENT_DOWNLOADS` prevents resource exhaustion (DoS).
   - `DOWNLOAD_TIMEOUT_SECONDS` prevents stuck processes.

## Reporting Vulnerabilities
If you find a security issue, please open an issue or contact the maintainer directly.
