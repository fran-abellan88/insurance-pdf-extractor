"""
File processing utilities
"""

import logging
import mimetypes
from pathlib import Path
from typing import Optional, Tuple

import magic

logger = logging.getLogger(__name__)


def detect_file_type(file_content: bytes, filename: str) -> Tuple[str, bool]:
    """
    Detect file type using both filename and content analysis

    Args:
        file_content: File content as bytes
        filename: Original filename

    Returns:
        Tuple of (mime_type, is_valid_pdf)
    """
    try:
        # Try to detect using python-magic (more reliable)
        try:
            import magic

            mime_type = magic.from_buffer(file_content, mime=True)
        except ImportError:
            # Fallback to mimetypes module
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type:
                mime_type = "application/octet-stream"

        is_pdf = mime_type == "application/pdf"

        # Additional PDF validation
        if is_pdf or filename.lower().endswith(".pdf"):
            is_valid_pdf = file_content.startswith(b"%PDF-")
        else:
            is_valid_pdf = False

        return mime_type, is_valid_pdf

    except Exception as e:
        logger.error(f"Error detecting file type: {e}")
        return "application/octet-stream", False


def get_file_size_mb(file_content: bytes) -> float:
    """
    Get file size in megabytes

    Args:
        file_content: File content as bytes

    Returns:
        File size in MB
    """
    return len(file_content) / (1024 * 1024)


def validate_file_size(file_content: bytes, max_size_mb: int = 10) -> bool:
    """
    Validate if file size is within limits

    Args:
        file_content: File content as bytes
        max_size_mb: Maximum allowed size in MB

    Returns:
        True if valid size, False otherwise
    """
    size_mb = get_file_size_mb(file_content)
    return size_mb <= max_size_mb


def extract_file_extension(filename: str) -> str:
    """
    Extract file extension from filename

    Args:
        filename: Original filename

    Returns:
        File extension (including dot)
    """
    if not filename:
        return ""

    return Path(filename).suffix.lower()
