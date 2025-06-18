"""
Pydantic models for API responses with token usage support
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """Token usage information"""

    input_tokens: Optional[int] = Field(default=None, description="Number of input tokens (prompt + PDF)")
    prompt_token_count: Optional[int] = Field(default=None, description="Tokens used for the prompt")
    candidates_token_count: Optional[int] = Field(default=None, description="Tokens generated in response")
    total_token_count: Optional[int] = Field(default=None, description="Total tokens used")
    estimated_cost: Optional[float] = Field(default=None, description="Estimated cost in USD")
    cost_breakdown: Optional[Dict[str, Any]] = Field(default=None, description="Detailed cost breakdown")
    error: Optional[str] = Field(default=None, description="Error message if token counting failed")


class TokenMetrics(BaseModel):
    """Detailed token metrics for the metrics section"""

    input_tokens: int = Field(description="Number of input tokens")
    output_tokens: int = Field(description="Number of output tokens")
    total_tokens: int = Field(description="Total number of tokens")


class ExtractionMetrics(BaseModel):
    """Detailed metrics about the extraction process"""

    gemini_processing_time: float = Field(description="Time spent on Gemini API call")
    validation_time: float = Field(description="Time spent on data validation")
    total_fields: int = Field(description="Total number of fields expected")
    extracted_fields: int = Field(description="Number of fields successfully extracted")
    validation_errors: int = Field(description="Number of validation errors")
    warnings: int = Field(description="Number of warnings")
    token_metrics: Optional[TokenMetrics] = Field(default=None, description="Token usage metrics")


class ExtractionResponse(BaseModel):
    """Response model for successful PDF extraction"""

    status: str = Field(default="success", description="Response status")
    extracted_data: Dict[str, Any] = Field(description="Extracted data from PDF")
    processing_time: float = Field(description="Processing time in seconds")
    model_used: str = Field(description="Gemini model used for extraction")
    prompt_version: str = Field(description="Prompt version used")
    file_info: Optional[Dict[str, Any]] = Field(default=None, description="Information about the processed file")
    confidence_scores: Optional[Dict[str, float]] = Field(
        default=None, description="Confidence scores for each field (if requested)"
    )
    page_sources: Optional[Dict[str, Optional[int]]] = Field(
        default=None, description="Page source information for each field (if requested)"
    )
    token_usage: Optional[TokenUsage] = Field(default=None, description="Token usage information (if requested)")
    warnings: Optional[List[str]] = Field(default=None, description="List of warnings during processing")
    failed_fields: Optional[List[str]] = Field(default=None, description="List of fields that failed extraction")
    metrics: Optional[ExtractionMetrics] = Field(default=None, description="Detailed extraction metrics")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="Timestamp of the extraction"
    )


class PartialExtractionResponse(BaseModel):
    """Response model for partial extraction (some fields failed)"""

    status: str = Field(default="partial_success", description="Response status")
    extracted_data: Dict[str, Any] = Field(description="Successfully extracted data")
    failed_fields: List[str] = Field(description="Fields that failed extraction")
    errors: List[str] = Field(description="Error messages for failed fields")
    processing_time: float = Field(description="Processing time in seconds")
    model_used: str = Field(description="Gemini model used for extraction")
    prompt_version: str = Field(description="Prompt version used")
    file_info: Optional[Dict[str, Any]] = Field(default=None, description="Information about the processed file")
    confidence_scores: Optional[Dict[str, float]] = Field(
        default=None, description="Confidence scores for each field (if requested)"
    )
    page_sources: Optional[Dict[str, Optional[int]]] = Field(
        default=None, description="Page source information for each field (if requested)"
    )
    token_usage: Optional[TokenUsage] = Field(default=None, description="Token usage information (if requested)")
    warnings: Optional[List[str]] = Field(default=None, description="List of warnings during processing")
    metrics: Optional[ExtractionMetrics] = Field(default=None, description="Detailed extraction metrics")
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


class DetailedExtractionResponse(ExtractionResponse):
    """Extended response with detailed metrics"""

    validation_summary: Optional[ValidationSummary] = Field(default=None, description="Validation results summary")
