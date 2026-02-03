"""
tests/test_core.py
Unit tests for utils and basic logic.
"""
import pytest
from src import utils, downloader, queue

def test_is_valid_url():
    assert utils.is_valid_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert utils.is_valid_url("https://twitter.com/user/status/123456")
    assert not utils.is_valid_url("not_a_url")

def test_human_readable_size():
    assert utils.human_readable_size(1024) == "1.0 KB"
    assert utils.human_readable_size(1024 * 1024 * 2.5) == "2.5 MB"

@pytest.mark.asyncio
async def test_queue_locking():
    q = queue.DownloadQueue(max_concurrent=1)
    await q.acquire()
    assert q.active_tasks == 1
    # Release
    q.release()
    assert q.active_tasks == 0

def test_format_processing():
    dl = downloader.YtDlpWrapper()
    mock_info = {
        'formats': [
            {'format_id': '137', 'height': 1080, 'ext': 'mp4', 'vcodec': 'h264'},
            {'format_id': '22', 'height': 720, 'ext': 'mp4', 'vcodec': 'h264'},
            {'format_id': '140', 'vcodec': 'none', 'acodec': 'aac'} # audio
        ]
    }
    options = dl.process_formats(mock_info)
    # Expect Audio + 1080p + 720p = 3
    assert len(options) >= 2 
    assert any(o['type'] == 'audio' for o in options)
    assert any(o['label'].startswith('1080p') for o in options)
