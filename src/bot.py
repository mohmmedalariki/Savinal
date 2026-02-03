"""
src/bot.py
Main entry point for the Telegram Bot. Handles conversation flow, 
callbacks, and coordinates downloading/uploading.
"""

import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, 
    MessageHandler, CallbackQueryHandler, filters, ConversationHandler
)
from . import messages, utils, downloader, queue

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables (for local dev)
from dotenv import load_dotenv
load_dotenv()

# Config
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MAX_FILE_SIZE = float(os.getenv("MAX_TELEGRAM_FILE_MB", 45)) * 1024 * 1024
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT_SECONDS", 300))

# States
CHOOSING_FORMAT = 1
DOWNLOADING = 2

# Global modules
dl_wrapper = downloader.YtDlpWrapper()
dl_queue = queue.download_queue

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message."""
    await update.message.reply_text(messages.START_MESSAGE)
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message."""
    await update.message.reply_text(messages.START_MESSAGE)

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the URL and show formats."""
    url = update.message.text.strip()
    
    if not utils.is_valid_url(url):
        await update.message.reply_text(messages.ERROR_INVALID_URL)
        return ConversationHandler.END
        
    # Send reminder (Quranic verse)
    await update.message.reply_text(messages.REMINDER_MESSAGE)
        
    status_msg = await update.message.reply_text(messages.CHECKING_URL)
    
    try:
        info = await dl_wrapper.get_info(url)
        formats = dl_wrapper.process_formats(info)
        
        if not formats:
            await status_msg.edit_text(messages.ERROR_GENERIC.format(reason="No suitable formats found"))
            return ConversationHandler.END
            
        keyboards = []
        for fmt in formats:
            # format_id|type -> we store format_id in callback data
            # Note: Callback data limit is 64 bytes. If format_id is long, this might break.
            # We assume format_id is reasonably short.
            # We can use a simple index if needed, but stateless is better.
            btn_text = f"{fmt['label']} ({fmt['ext']})"
            keyboards.append([InlineKeyboardButton(btn_text, callback_data=f"dl|{fmt['format_id']}|{fmt['type']}")])
            
        keyboards.append([InlineKeyboardButton("Cancel", callback_data="cancel")])
        
        reply_markup = InlineKeyboardMarkup(keyboards)
        title = info.get('title', 'Video')
        
        # Save context for next step
        context.user_data['url'] = url
        context.user_data['title'] = title
        
        await status_msg.edit_text(
            messages.SELECT_FORMAT.format(title=title),
            reply_markup=reply_markup
        )
        return CHOOSING_FORMAT
        
    except Exception as e:
        logger.error(f"Error in handle_url: {e}")
        await status_msg.edit_text(messages.ERROR_GENERIC.format(reason=str(e)[:100]))
        return ConversationHandler.END

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle format selection."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data == "cancel":
        await query.edit_message_text(messages.CANCELED)
        return ConversationHandler.END
        
    _, format_id, type_ = data.split('|', 2)
    url = context.user_data.get('url')
    
    if not url:
        await query.edit_message_text("Session expired. Please send the link again.")
        return ConversationHandler.END
        
    await query.edit_message_text("Queuing download...")
    
    # Start async download task
    # We use create_task to allow the bot to remain responsive, 
    # but we want to hold the conversation logic somewhat.
    # Actually, proper way is to fire off a bg task that updates the message.
    asyncio.create_task(process_download(update, context, url, format_id, query.message))
    
    return ConversationHandler.END

async def process_download(update, context, url, format_id, message_object):
    """Actual download logic, running in background."""
    
    last_update_percent = 0
    
    def progress_callback(d):
        nonlocal last_update_percent
        if d['status'] == 'downloading':
            # rudimentary throttling of edits
            p_str = d.get('_percent_str', '0%').strip().replace('%', '')
            try:
                p = float(p_str)
                # update every 20%
                if p - last_update_percent >= 20 or p == 100:
                    last_update_percent = p
                    # We need to schedule the edit on the loop
                    # Note: handling 'message_object' which might be stale if user deleted chat is risky
                    # We'll use a silent try/except
                    asyncio.create_task(safe_edit(message_object, messages.DOWNLOADING.format(percent=p)))
            except ValueError:
                pass

    async def safe_edit(msg, text):
        try:
            await msg.edit_text(text)
        except Exception:
            pass

    try:
        await dl_queue.acquire()
        await safe_edit(message_object, messages.DOWNLOADING.format(percent=0))
        
        # Perform download
        file_path = await asyncio.wait_for(
            dl_wrapper.download(url, format_id, progress_callback), 
            timeout=DOWNLOAD_TIMEOUT
        )
        
        await safe_edit(message_object, messages.PROCESSING)
        
        # Check size
        file_size = os.path.getsize(file_path)
        
        if file_size > MAX_FILE_SIZE:
             # S3 Upload logic
             await safe_edit(message_object, messages.UPLOADING_S3)
             s3_url = utils.upload_to_s3(file_path)
             if s3_url:
                 await safe_edit(message_object, messages.S3_LINK_READY.format(url=s3_url))
             else:
                 await safe_edit(message_object, messages.ERROR_GENERIC.format(reason="File too large and upload failed"))
        else:
            # Send file
            await safe_edit(message_object, messages.UPLOADING)
            try:
                # Use open(file_path, 'rb')
                # Telegram supports sending by file path directly usually, 
                # but explicit open is safer for some libraries.
                # python-telegram-bot supports path string or file buffer.
                if file_path.endswith('.mp3'):
                    await message_object.reply_audio(audio=open(file_path, 'rb'), title=context.user_data.get('title'))
                else:
                    await message_object.reply_video(video=open(file_path, 'rb'), caption=context.user_data.get('title'))
                    
                await safe_edit(message_object, "Done! ✅")
            except Exception as e:
                logger.error(f"Telegram upload failed: {e}")
                await safe_edit(message_object, messages.ERROR_GENERIC.format(reason="Upload to Telegram failed"))
                
    except asyncio.TimeoutError:
        await safe_edit(message_object, messages.ERROR_TIMEOUT)
    except Exception as e:
        logger.error(f"Download failed: {e}")
        await safe_edit(message_object, messages.ERROR_GENERIC.format(reason="Download error"))
    finally:
        dl_queue.release()
        if 'file_path' in locals() and file_path:
            utils.cleanup_file(file_path)


def main():
    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in environment.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    # Conversation handler for the flow
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url)],
        states={
            CHOOSING_FORMAT: [CallbackQueryHandler(button_callback)],
        },
        fallbacks=[CommandHandler("cancel", start)],
        per_message=False # Global conversation per user
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv_handler)
    
    # --- Health Check Server (for Koyeb/Render) ---
    from aiohttp import web

    async def health_check(request):
        return web.Response(text="OK", status=200)

    async def run_server():
        server_app = web.Application()
        server_app.router.add_get('/', health_check)
        runner = web.AppRunner(server_app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8000)
        await site.start()
        logger.info("Health check server started on port 8000")

    # We need to run polling WITHOUT blocking the loop, so we can run the server too.
    # Application.run_polling() is blocking. We use initialize/start/updater pattern or custom loop.
    # Simpler approach: Use application.run_polling() but inject the server startup?
    # No, run_polling blocks. 
    # Better: Use asyncio.gather logic if we had control, but PTB manages the loop.
    # PTB v20+ way:
    
    async def main_loop():
        # Start web server
        await run_server()
        
        # Start Loop
        async with app:
            await app.start()
            if app.updater: # Should be None for polling unless we init it
                 pass
            # We use a custom updater or just run_polling in a wrapper?
            # Actually, application.run_polling() supports customization but it's easier to just
            # start the updater manually.
            await app.updater.start_polling()
            
            # Keep alive
            logger.info("Bot started polling.")
            # Simple keep-alive loop
            stop_signal = asyncio.Event()
            await stop_signal.wait()

    # REFACTOR: run_polling is very robust. Let's stick to it but use post_init to start server.
    async def post_init(application):
        await run_server()

    app.post_init = post_init
    
    print("Bot is polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
