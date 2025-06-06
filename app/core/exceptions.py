"""
Custom exceptions and exception handlers
"""

import logging
import traceback

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Custom exception for PDF extraction errors"""

    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(Exception):
    """Custom exception for data validation errors"""

    def __init__(self, message: str, field: str = None, value: str = None):
        self.message = message
        self.field = field
        self.value = value
        super().__init__(self.message)


class GeminiAPIError(Exception):
    """Custom exception for Gemini API errors"""

    def __init__(self, message: str, status_code: int = None, response_text: str = None):
        self.message = message
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(self.message)


class FileProcessingError(Exception):
    """Custom exception for file processing errors"""

    def __init__(self, message: str, file_name: str = None, file_size: int = None):
        self.message = message
        self.file_name = file_name
        self.file_size = file_size
        super().__init__(self.message)


class DocumentProcessingError(Exception):
    """Custom exception for document processing errors"""

    def __init__(self, message: str, document_type: str = None):
        self.message = message
        self.document_type = document_type
        super().__init__(self.message)


async def extraction_exception_handler(request: Request, exc: ExtractionError) -> JSONResponse:
    """Handle extraction errors"""
    logger.error(f"Extraction error: {exc.message}, Details: {exc.details}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "error_type": "extraction_error",
            "message": exc.message,
            "details": exc.details,
            "extracted_data": None,
        },
    )


async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle validation errors"""
    logger.error(f"Validation error: {exc.message}, Field: {exc.field}, Value: {exc.value}")

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "status": "error",
            "error_type": "validation_error",
            "message": exc.message,
            "field": exc.field,
            "value": exc.value,
        },
    )


async def gemini_api_exception_handler(request: Request, exc: GeminiAPIError) -> JSONResponse:
    """Handle Gemini API errors"""
    logger.error(f"Gemini API error: {exc.message}, Status: {exc.status_code}")

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "error",
            "error_type": "api_error",
            "message": "External AI service is currently unavailable",
            "details": exc.message,
        },
    )


async def file_processing_exception_handler(request: Request, exc: FileProcessingError) -> JSONResponse:
    """Handle file processing errors"""
    logger.error(f"File processing error: {exc.message}, File: {exc.file_name}")

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "status": "error",
            "error_type": "file_error",
            "message": exc.message,
            "file_name": exc.file_name,
            "file_size": exc.file_size,
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle standard HTTP exceptions"""
    logger.warning(f"HTTP exception: {exc.status_code} - {exc.detail}")

    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "error_type": "http_error", "message": exc.detail, "status_code": exc.status_code},
    )


async def validation_request_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors"""
    logger.error(f"Request validation error: {exc.errors()}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "error_type": "request_validation_error",
            "message": "Invalid request format",
            "details": exc.errors(),
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle any unhandled exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}")
    logger.error(f"Traceback: {traceback.format_exc()}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "error_type": "internal_error",
            "message": "An internal server error occurred",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """Setup all exception handlers for the FastAPI app"""

    app.add_exception_handler(ExtractionError, extraction_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(GeminiAPIError, gemini_api_exception_handler)
    app.add_exception_handler(FileProcessingError, file_processing_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_request_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
