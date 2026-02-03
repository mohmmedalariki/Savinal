"""
src/queue.py
Manages concurrent downloads using asyncio Semaphores.
"""

import asyncio
import os
import logging

logger = logging.getLogger(__name__)

class DownloadQueue:
    def __init__(self, max_concurrent: int = 3):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_tasks = 0
    
    async def acquire(self):
        """Acquire a slot in the download queue."""
        await self.semaphore.acquire()
        self.active_tasks += 1
        logger.info(f"Download slot acquired. Active tasks: {self.active_tasks}")

    def release(self):
        """Release a slot in the download queue."""
        self.active_tasks -= 1
        self.semaphore.release()
        logger.info(f"Download slot released. Active tasks: {self.active_tasks}")

    def get_stats(self):
        """Return current queue stats."""
        # Note: Semaphore._value is internal, but commonly accessed for metrics
        # For a more robust solution we assume max - active if using strict acquire/release
        return {
            "active_downloads": self.active_tasks,
            "slots_available": self.semaphore._value if hasattr(self.semaphore, '_value') else "N/A"
        }

# Global instance
MAX_CONCURRENT = int(os.getenv('MAX_CONCURRENT_DOWNLOADS', 3))
download_queue = DownloadQueue(max_concurrent=MAX_CONCURRENT)
