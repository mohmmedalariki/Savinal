"""
src/downloader.py
Wraps yt-dlp interaction for fetching metadata and downloading files.
"""

import asyncio
import logging
import tempfile
import os
import json
from yt_dlp import YoutubeDL
from . import messages

logger = logging.getLogger(__name__)

class YtDlpWrapper:
    def __init__(self, download_dir='downloads'):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        
        # Handle Cookies from Env (for YouTube "Sign in" errors)
        self.cookie_file = None
        cookies_content = os.getenv('COOKIES_CONTENT')
        if cookies_content:
            try:
                self.cookie_file = os.path.join(os.getcwd(), 'cookies.txt')
                # Determine if it's base64 encoded (common for multiline env vars in some dashboards)
                # or just plain text. For safety, just write as-is, assuming user pasted Netscape format.
                with open(self.cookie_file, 'w') as f:
                    f.write(cookies_content)
                logger.info(f"Loaded cookies from environment into {self.cookie_file}")
            except Exception as e:
                logger.error(f"Failed to write cookies file: {e}")

    def _get_opts(self, extra_opts=None):
        """Return base yt-dlp options."""
        opts = {
            'quiet': True,
            'no_warnings': True,
            'outtmpl': f'{self.download_dir}/%(id)s_%(format_id)s.%(ext)s',
            'restrictfilenames': True,
            # Mimic a real browser to avoid being blocked (especially by FB/IG)
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            # Prefer MP4/H264 for compatibility
            'format_sort': ['res:1080', 'res:720', 'res:480', 'codec:h264', 'ext:mp4:m4a'],
        }
        
        # Add cookie file if available
        if self.cookie_file and os.path.exists(self.cookie_file):
            opts['cookiefile'] = self.cookie_file
            
        # Try to use alternative clients for YouTube to bypass bot detection if no cookies
        # or even with cookies to be safer.
        # 'android' client is often less throttled.
        # We perform a safe merge if extra_opts has extractor_args
        if 'extractor_args' not in opts:
             opts['extractor_args'] = {}
        
        # Default to android/web clients for youtube
        opts['extractor_args']['youtube'] = {
            'player_client': ['android', 'web']
        }

        if extra_opts:
            opts.update(extra_opts)
        return opts

    async def get_info(self, url: str):
        """Extract video metadata and available formats."""
        def run_info():
            opts = self._get_opts({'noplaylist': True})
            with YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        try:
            return await asyncio.to_thread(run_info)
        except Exception as e:
            logger.error(f"Error fetching info for {url}: {e}")
            raise e

    def process_formats(self, info_dict):
        """
        Simplify the generic yt-dlp format list into a user-friendly list.
        Returns a list of dicts: {'format_id', 'label', 'ext', 'filesize_str'}
        """
        raw_formats = info_dict.get('formats', [])
        
        options = []
        
        # Audio Only Option
        options.append({
            'format_id': 'bestaudio/best',
            'label': 'Audio Only (MP3)',
            'ext': 'mp3',
            'type': 'audio'
        })
        
        # Standard Resolutions using a mapping
        # We look for the best video stream for each target resolution
        desired_resolutions = [1080, 720, 480, 360]
        found_res = set()
        
        # Pre-filter suitable video streams
        video_formats = [f for f in raw_formats if f.get('vcodec') != 'none' and f.get('height')]
        video_formats.sort(key=lambda x: x['height'], reverse=True) # Highest first

        for target in desired_resolutions:
            # Find the best match close to this resolution
            # We strictly look for exact match or slightly higher/lower? 
            # Simple approach: distinct heights present in the file
            for f in video_formats:
                res = f.get('height')
                # Check if this res matches one of our desired targets exactly
                if res == target and res not in found_res:
                    filesize = f.get('filesize') or f.get('filesize_approx')
                    size_str = ""
                    if filesize:
                        size_mb = filesize / (1024 * 1024)
                        size_str = f" ~{size_mb:.1f}MB"
                    
                    label = f"{target}p{size_str}"
                    options.append({
                        'format_id': f.get('format_id'),
                        'label': label,
                        'ext': 'mp4', # We force merge to mp4 usually
                        'type': 'video',
                        'filesize': filesize
                    })
                    found_res.add(target)
                    break 
        
        # Fallback: If we have very few options (e.g. only audio + 0-1 videos), 
        # add the best available video streams that didn't match strict buckets.
        # This handles platforms like X/Twitter using weird resolutions (e.g. 640x360).
        if len(found_res) == 0:
            for f in video_formats:
                res = f.get('height')
                if res and res not in found_res:
                    filesize = f.get('filesize') or f.get('filesize_approx')
                    size_str = ""
                    if filesize:
                        size_mb = filesize / (1024 * 1024)
                        size_str = f" ~{size_mb:.1f}MB"
                    
                    label = f"{res}p{size_str}"
                    options.append({
                        'format_id': f.get('format_id'),
                        'label': label,
                        'ext': 'mp4',
                        'type': 'video',
                        'filesize': filesize
                    })
                    found_res.add(res)
                    # Limit to top 3 fallback options
                    if len(found_res) >= 3:
                        break

        return options

    async def download(self, url: str, format_id: str, progress_hook=None):
        """
        Download the specific format.
        progress_hook: function(d) -> coroutine or None
        """
        formatted_format_string = format_id
        
        # If it's a video, ensure we get audio too!
        # logic: format_id + bestaudio, keeping video as base
        if format_id != 'bestaudio/best':
            formatted_format_string = f"{format_id}+bestaudio/best"

        def hook(d):
            if d['status'] == 'downloading':
                if progress_hook:
                     progress_hook(d)

        opts = self._get_opts({
            'format': formatted_format_string,
            'progress_hooks': [hook],
            'outtmpl': f'{self.download_dir}/%(title)s_%(resolution)s_%(id)s.%(ext)s',
        })
        
        # If audio only, we want postprocessors to convert to mp3
        if format_id == 'bestaudio/best':
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
            opts['outtmpl'] = f'{self.download_dir}/%(title)s_audio_%(id)s.%(ext)s'
        else:
            # Video: Force usage of mp4 container and potentially re-encode for compatibility
            # This fixes "black screen" or "stuck image" issues on FB/others (often due to av1/vp9 codecs)
            opts['merge_output_format'] = 'mp4'
            opts['postprocessors'] = [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }]

        def run_download():
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        # Wrap in thread
        file_path = await asyncio.to_thread(run_download)
        
        # Post-download path fixups
        if format_id == 'bestaudio/best':
             base, _ = os.path.splitext(file_path)
             expected_mp3 = base + '.mp3'
             # sometimes prepare_filename returns the original ext, check if mp3 exists
             if os.path.exists(expected_mp3):
                 return expected_mp3

        # For video, since we requested merge to mp4, ensure we return that
        if format_id != 'bestaudio/best':
            base, _ = os.path.splitext(file_path)
            if not file_path.endswith('.mp4') and os.path.exists(base + '.mp4'):
                return base + '.mp4'
             
        return file_path
