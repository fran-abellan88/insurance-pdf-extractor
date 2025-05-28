"""
Logging utilities
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict


def setup_logging(log_level: str = "INFO") -> None:
    """
    Setup application logging configuration

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Set specific logger levels
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def log_api_request(endpoint: str, method: str, user_info: Dict[str, Any], file_info: Dict[str, Any] = None) -> None:
    """
    Log API request information

    Args:
        endpoint: API endpoint path
        method: HTTP method
        user_info: User/API key information
        file_info: File information if applicable
    """
    logger = logging.getLogger("api_requests")

    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "endpoint": endpoint,
        "method": method,
        "user": user_info.get("key", "unknown")[:8] + "...",
    }

    if file_info:
        log_data["file"] = {"filename": file_info.get("filename", "unknown"), "size_mb": file_info.get("size_mb", 0)}

    logger.info(f"API Request: {json.dumps(log_data)}")


def log_processing_metrics(operation: str, duration: float, success: bool, details: Dict[str, Any] = None) -> None:
    """
    Log processing metrics

    Args:
        operation: Operation name (e.g., 'pdf_extraction', 'validation')
        duration: Operation duration in seconds
        success: Whether operation was successful
        details: Additional details to log
    """
    logger = logging.getLogger("metrics")

    log_data = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation,
        "duration_seconds": round(duration, 3),
        "success": success,
    }

    if details:
        log_data["details"] = details

    logger.info(f"Metrics: {json.dumps(log_data)}")
