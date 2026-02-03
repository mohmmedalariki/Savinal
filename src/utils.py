"""
src/utils.py
Helper functions for URL validation, file handling, and S3 uploads.
"""

import os
import re
import math
import boto3
from botocore.exceptions import NoCredentialsError
import logging

logger = logging.getLogger(__name__)

# Basic URL regex (naive check, yt-dlp does the rest)
URL_REGEX = re.compile(
    r'^(https?://)?(www\.)?(youtube\.com|youtu\.be|x\.com|twitter\.com|instagram\.com|tiktok\.com|reddit\.com|vimeo\.com)/.+$'
)

def is_valid_url(url: str) -> bool:
    """Check if the URL looks somewhat valid for supported platforms."""
    # We can be loose here because yt-dlp is the ultimate validator
    return bool(url and url.strip().startswith('http'))

def human_readable_size(size_bytes: int) -> str:
    """Convert bytes to human readable string (e.g., 10.5 MB)."""
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

def cleanup_file(path: str):
    """Safely remove a file if it exists."""
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"Cleaned up file: {path}")
    except Exception as e:
        logger.error(f"Error cleaning up file {path}: {e}")

def get_s3_client():
    """Create and return an S3 client using env vars."""
    return boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        endpoint_url=os.getenv('S3_ENDPOINT'),
        region_name=os.getenv('AWS_REGION', 'us-east-1')
    )

def upload_to_s3(file_path: str, object_name: str = None) -> str:
    """
    Upload a file to an S3 bucket and return a presigned URL.
    Returns None if upload fails or credentials missing.
    """
    bucket_name = os.getenv('S3_BUCKET')
    if not bucket_name:
        logger.warning("S3_BUCKET not configured.")
        return None

    if object_name is None:
        object_name = os.path.basename(file_path)

    s3_client = get_s3_client()
    try:
        logger.info(f"Uploading {file_path} to s3://{bucket_name}/{object_name}")
        s3_client.upload_file(file_path, bucket_name, object_name)
        
        # Generate presigned link (valid for 1 hour)
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=3600
        )
        return url
    except NoCredentialsError:
        logger.error("AWS Credentials not available")
        return None
    except Exception as e:
        logger.error(f"Failed to upload to S3: {e}")
        return None
