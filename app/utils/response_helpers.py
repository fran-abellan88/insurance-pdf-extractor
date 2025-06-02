"""
Response formatting utilities
"""

from datetime import datetime
from typing import Any, Dict, List


def create_success_response(
    extracted_data: Dict[str, Any],
    processing_time: float,
    model_used: str,
    prompt_version: str,
    file_info: Dict[str, Any] = None,
    confidence_scores: Dict[str, float] = None,
    warnings: List[str] = None,
) -> Dict[str, Any]:
    """
    Create standardized success response∏
    """
    response = {
        "status": "success",
        "extracted_data": extracted_data,
        "processing_time": processing_time,
        "model_used": model_used,
        "prompt_version": prompt_version,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if file_info:
        response["file_info"] = file_info

    if confidence_scores:
        response["confidence_scores"] = confidence_scores

    if warnings:
        response["warnings"] = warnings

    return response


def create_error_response(
    error_type: str, message: str, details: Dict[str, Any] = None, status_code: int = 500
) -> Dict[str, Any]:
    """
    Create standardized error response
    """
    response = {
        "status": "error",
        "error_type": error_type,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
        "status_code": status_code,
    }

    if details:
        response["details"] = details

    return response


def create_partial_success_response(
    extracted_data: Dict[str, Any],
    failed_fields: List[str],
    errors: List[str],
    processing_time: float,
    model_used: str,
    prompt_version: str,
    warnings: List[str] = None,
) -> Dict[str, Any]:
    """
    Create standardized partial success response
    """
    response = {
        "status": "partial_success",
        "extracted_data": extracted_data,
        "failed_fields": failed_fields,
        "errors": errors,
        "processing_time": processing_time,
        "model_used": model_used,
        "prompt_version": prompt_version,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if warnings:
        response["warnings"] = warnings

    return response
