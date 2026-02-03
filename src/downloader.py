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

    def _get_opts(self, extra_opts=None):
        """Return base yt-dlp options."""
        opts = {
            'quiet': True,
            'no_warnings': True,
            'outtmpl': f'{self.download_dir}/%(id)s_%(format_id)s.%(ext)s',
            'restrictfilenames': True,  # ASCII only filenames
            # Mimic a real browser to avoid being blocked (especially by FB/IG/X)
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
             # STRICTLY prefer H.264 video and AAC audio for Telegram compatibility
            'format_sort': [
                'res:1080', 'res:720', 'res:480', 
                'vcodec:h264', 'acodec:aac', 
                'ext:mp4'
            ],
        }
        if extra_opts:
            opts.update(extra_opts)
        return opts

    async def get_info(self, url: str):
        """Extract video metadata and available formats."""
        def run_info():
            # noplaylist avoids downloading whole playlist
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
        
        # Helper to classify resolution (handling vertical videos)
        def get_res_class(f):
            h = f.get('height') or 0
            w = f.get('width') or 0
            # Use smaller dimension for class (e.g. 720x1280 -> 720p)
            return min(h, w) if h and w else h

        valid_formats = [f for f in raw_formats if f.get('vcodec') != 'none']
        valid_formats.sort(key=get_res_class, reverse=True)
        
        desired_resolutions = [1080, 720, 480, 360]
        found_res = set()

        for target in desired_resolutions:
            for f in valid_formats:
                # Check fuzzy match for resolution
                h = f.get('height') or 0
                w = f.get('width') or 0
                res_class = min(h, w) if h and w else h
                
                # Allow slight variance or exact match
                if res_class == target and target not in found_res:
                    filesize = f.get('filesize') or f.get('filesize_approx')
                    size_str = ""
                    if filesize:
                        size_mb = filesize / (1024 * 1024)
                        size_str = f" ~{size_mb:.1f}MB"
                    
                    # Detect if vertical
                    is_vertical = h > w if h and w else False
                    orientation_mark = " (Vertical)" if is_vertical else ""
                    
                    label = f"{target}p{orientation_mark}{size_str}"
                    options.append({
                        'format_id': f.get('format_id'),
                        'label': label,
                        'ext': 'mp4',
                        'type': 'video',
                        'filesize': filesize
                    })
                    found_res.add(target)
                    break 
        
        # Fallback: If no standard resolutions found (common on X/Twitter/FB)
        if len(found_res) == 0:
            for f in valid_formats[:3]: # Top 3 best quality
                h = f.get('height')
                # avoid duplicates if possible, but here we just take top 3 distinct
                if h:
                    filesize = f.get('filesize') or f.get('filesize_approx')
                    size_str = f" ~{filesize / (1024 * 1024):.1f}MB" if filesize else ""
                    options.append({
                        'format_id': f.get('format_id'),
                        'label': f"{h}p{size_str}",
                        'ext': 'mp4',
                        'type': 'video',
                        'filesize': filesize
                    })
                    
        return options

    async def download(self, url: str, format_id: str, progress_hook=None):
        """
        Download the specific format.
        """
        formatted_format_string = format_id
        
        # If it's a video, ensure we get audio too!
        if format_id != 'bestaudio/best' and '+' not in format_id:
            formatted_format_string = f"{format_id}+bestaudio/best"

        def hook(d):
            if d['status'] == 'downloading':
                if progress_hook:
                     progress_hook(d)

        opts = self._get_opts({
            'format': formatted_format_string,
            'progress_hooks': [hook],
            'outtmpl': f'{self.download_dir}/%(title)s_%(resolution)s_%(id)s.%(ext)s',
            'merge_output_format': 'mp4'
        })
        
        if format_id == 'bestaudio/best':
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
            opts['outtmpl'] = f'{self.download_dir}/%(title)s_audio_%(id)s.%(ext)s'
            opts.pop('merge_output_format', None)
        else:
            # FORCE RE-ENCODE to H.264 / AAC for maximum compatibility
            # This fixes "black screen" on iOS and "stuck image" on Telegram
            opts['postprocessors'] = [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }]
            opts['postprocessor_args'] = {
                'ffmpeg': ['-c:v', 'libx264', '-c:a', 'aac', '-movflags', '+faststart']
            }

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
             if os.path.exists(expected_mp3):
                 return expected_mp3

        # For video, return mp4
        if format_id != 'bestaudio/best':
            base, _ = os.path.splitext(file_path)
            # Check for merged file
            if os.path.exists(base + '.mp4'):
                return base + '.mp4'
            # Or if original file needs extension swap
            if not file_path.endswith('.mp4') and os.path.exists(file_path):
                 # This shouldn't happen often with merge_output_format
                 return file_path
             
        return file_path
