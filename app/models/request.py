"""
Pydantic models for API requests with token usage support
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ModelType(str, Enum):
    """Available Gemini models"""

    FLASH = "gemini-1.5-flash"
    PRO = "gemini-1.5-pro"
    FLASH_2_5_PREVIEW = "gemini-2.5-flash-preview-05-20"


class ExtractionRequest(BaseModel):
    """Request model for PDF extraction"""

    model: ModelType = Field(default=ModelType.FLASH, description="Gemini model to use for extraction")

    prompt_version: Optional[str] = Field(
        default=None,
        description="Version of the prompt to use (defaults to latest)",
        json_schema_extra={"example": "v2"},
    )

    temperature: Optional[float] = Field(
        default=0.1, ge=0.0, le=1.0, description="Temperature for AI model (0.0 = deterministic, 1.0 = creative)"
    )

    max_tokens: Optional[int] = Field(default=4096, ge=1, le=8192, description="Maximum tokens for the response")

    include_confidence: bool = Field(default=False, description="Whether to include confidence scores in the response")

    include_token_usage: bool = Field(
        default=False, description="Whether to include detailed token usage metrics and cost estimates"
    )

    @field_validator("prompt_version")
    def validate_prompt_version(cls, v):
        """Validate prompt version format"""
        if v is not None and not v.startswith("v"):
            raise ValueError('Prompt version must start with "v" (e.g., "v2")')
        return v


class HealthCheckResponse(BaseModel):
    """Health check response model"""

    status: str = Field(description="Service status")
    version: str = Field(description="API version")
    gemini_available: bool = Field(description="Whether Gemini API is accessible")
    available_models: List[str] = Field(description="List of available models")
    available_prompt_versions: List[str] = Field(description="List of available prompt versions")


class FileUpload(BaseModel):
    """File upload validation"""

    filename: str = Field(description="Name of the uploaded file")
    content_type: str = Field(description="MIME type of the file")
    size: int = Field(description="File size in bytes")

    @field_validator("content_type")
    def validate_content_type(cls, v):
        """Validate file content type"""
        allowed_types = ["application/pdf"]
        if v not in allowed_types:
            raise ValueError(f"File type {v} not supported. Allowed types: {allowed_types}")
        return v

    @field_validator("size")
    def validate_file_size(cls, v):
        """Validate file size (10MB limit)"""
        max_size = 10 * 1024 * 1024  # 10MB in bytes
        if v > max_size:
            raise ValueError(f"File size {v} bytes exceeds maximum allowed size of {max_size} bytes")
        return v

    @field_validator("filename")
    def validate_filename(cls, v):
        """Validate filename"""
        if not v.lower().endswith(".pdf"):
            raise ValueError("File must have .pdf extension")
        return v


class TokenUsageRequest(BaseModel):
    """Request model for token usage estimation"""

    model: ModelType = Field(default=ModelType.FLASH, description="Gemini model to estimate tokens for")
    prompt_version: Optional[str] = Field(default=None, description="Prompt version to use")

    @field_validator("prompt_version")
    def validate_prompt_version(cls, v):
        """Validate prompt version format"""
        if v is not None and not v.startswith("v"):
            raise ValueError('Prompt version must start with "v" (e.g., "v2")')
        return v
