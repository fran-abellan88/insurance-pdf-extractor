"""
Pydantic models for API responses
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExtractionResponse(BaseModel):
    """Response model for successful PDF extraction"""

    status: str = Field(default="success", description="Response status")
    extracted_data: Dict[str, Any] = Field(description="Extracted data from PDF")
    processing_time: float = Field(description="Processing time in seconds")
    model_used: str = Field(description="Gemini model used for extraction")
    prompt_version: str = Field(description="Prompt version used")
    confidence_scores: Optional[Dict[str, float]] = Field(
        default=None, description="Confidence scores for each field (if requested)"
    )
    warnings: Optional[List[str]] = Field(default=None, description="List of warnings during processing")
    failed_fields: Optional[List[str]] = Field(default=None, description="List of fields that failed extraction")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="Timestamp of the extraction"
    )


class ErrorResponse(BaseModel):
    """Response model for errors"""

    status: str = Field(default="error", description="Response status")
    error_type: str = Field(description="Type of error that occurred")
    message: str = Field(description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Timestamp of the error")


class PartialExtractionResponse(BaseModel):
    """Response model for partial extraction (some fields failed)"""

    status: str = Field(default="partial_success", description="Response status")
    extracted_data: Dict[str, Any] = Field(description="Successfully extracted data")
    failed_fields: List[str] = Field(description="Fields that failed extraction")
    errors: List[str] = Field(description="Error messages for failed fields")
    processing_time: float = Field(description="Processing time in seconds")
    model_used: str = Field(description="Gemini model used for extraction")
    prompt_version: str = Field(description="Prompt version used")
    warnings: Optional[List[str]] = Field(default=None, description="List of warnings during processing")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="Timestamp of the extraction"
    )


class HealthResponse(BaseModel):
    """Health check response"""

    status: str = Field(description="Overall service status")
    version: str = Field(description="API version")
    environment: str = Field(description="Environment (development/production)")
    gemini_api: Dict[str, Any] = Field(description="Gemini API status")
    available_models: List[str] = Field(description="Available Gemini models")
    available_prompts: List[str] = Field(description="Available prompt versions")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Health check timestamp")


class ValidationSummary(BaseModel):
    """Summary of validation results"""

    total_fields: int = Field(description="Total number of fields expected")
    successful_extractions: int = Field(description="Number of successfully extracted fields")
    failed_extractions: int = Field(description="Number of failed extractions")
    validation_errors: int = Field(description="Number of validation errors")
    success_rate: float = Field(description="Success rate as percentage")


class ExtractionMetrics(BaseModel):
    """Detailed metrics about the extraction process"""

    file_info: Dict[str, Any] = Field(description="Information about the processed file")
    processing_stages: Dict[str, float] = Field(description="Time taken for each processing stage")
    api_calls: int = Field(description="Number of API calls made")
    tokens_used: int = Field(description="Number of tokens used")
    validation_summary: ValidationSummary = Field(description="Validation results summary")


class DetailedExtractionResponse(ExtractionResponse):
    """Extended response with detailed metrics"""

    metrics: Optional[ExtractionMetrics] = Field(default=None, description="Detailed extraction metrics")
