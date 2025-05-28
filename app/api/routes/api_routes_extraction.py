"""
API routes for PDF extraction
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.exceptions import ExtractionError, FileProcessingError, GeminiAPIError
from app.core.security import get_current_user
from app.models.request import ModelType
from app.models.response import ErrorResponse, ExtractionResponse, PartialExtractionResponse
from app.services.pdf_processor import pdf_processor

logger = logging.getLogger(__name__)
router = APIRouter()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/extract",
    response_model=ExtractionResponse,
    responses={
        200: {"model": ExtractionResponse, "description": "Successful extraction"},
        206: {"model": PartialExtractionResponse, "description": "Partial extraction with some failures"},
        400: {"model": ErrorResponse, "description": "Bad request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        422: {"model": ErrorResponse, "description": "Extraction failed"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    },
    summary="Extract data from insurance PDF",
    description="""
    Upload a PDF file containing an insurance quote and extract structured data.

    The service will:
    1. Validate the PDF file
    2. Extract text using Gemini AI
    3. Parse and validate the extracted data
    4. Return structured JSON with insurance information

    **Authentication**: Requires X-API-Key header

    **File Requirements**:
    - PDF format only
    - Maximum size: 10MB
    - Must contain readable text (not just images)

    **Models Available**:
    - `gemini-1.5-flash`: Faster, good for most cases
    - `gemini-1.5-pro`: More accurate, slower
    """,
)
@limiter.limit("10/minute")
async def extract_pdf_data(
    request,
    file: UploadFile = File(..., description="PDF file to process"),
    model: ModelType = Form(default=ModelType.FLASH, description="Gemini model to use"),
    prompt_version: Optional[str] = Form(default=None, description="Prompt version (e.g., 'v2')"),
    temperature: float = Form(default=0.1, ge=0.0, le=1.0, description="AI model temperature"),
    max_tokens: int = Form(default=4096, ge=1, le=8192, description="Maximum response tokens"),
    include_confidence: bool = Form(default=False, description="Include confidence scores"),
    current_user: dict = Depends(get_current_user),
):
    """Extract structured data from insurance PDF"""

    logger.info(f"PDF extraction request from user {current_user.get('key', 'unknown')}")

    try:
        # Validate file type
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are supported")

        # Read file content
        pdf_content = await file.read()
        logger.info(f"Processing PDF: {file.filename} ({len(pdf_content)} bytes)")

        # Process PDF
        result = await pdf_processor.process_pdf(
            pdf_content=pdf_content,
            filename=file.filename,
            model_name=model.value,
            prompt_version=prompt_version,
            temperature=temperature,
            max_tokens=max_tokens,
            include_confidence=include_confidence,
        )

        # Determine response type based on result status
        if result["status"] == "success":
            return ExtractionResponse(**result)
        elif result["status"] == "partial_success":
            return JSONResponse(
                status_code=206, content=PartialExtractionResponse(**result).model_dump()
            )  # Partial Content
        else:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Extraction failed")

    except FileProcessingError as e:
        logger.error(f"File processing error: {e.message}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

    except GeminiAPIError as e:
        logger.error(f"Gemini API error: {e.message}")
        if e.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="API rate limit exceeded. Please try again later."
            )
        elif e.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI service authentication failed"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI service is currently unavailable"
            )

    except ExtractionError as e:
        logger.error(f"Extraction error: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Failed to extract data: {e.message}"
        )

    except Exception as e:
        logger.error(f"Unexpected error during extraction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during processing"
        )


@router.get(
    "/models", summary="Get available models", description="Get list of available Gemini models and their capabilities"
)
async def get_available_models(current_user: dict = Depends(get_current_user)):
    """Get available Gemini models"""

    try:
        models = [
            {
                "name": "gemini-1.5-flash",
                "display_name": "Gemini 1.5 Flash",
                "description": "Fast and efficient model, good for most extraction tasks",
                "max_tokens": 8192,
                "recommended_for": ["quick_extraction", "batch_processing"],
            },
            {
                "name": "gemini-1.5-pro",
                "display_name": "Gemini 1.5 Pro",
                "description": "More accurate model with better reasoning capabilities",
                "max_tokens": 8192,
                "recommended_for": ["complex_documents", "high_accuracy_required"],
            },
        ]

        return {"available_models": models, "default_model": "gemini-1.5-flash"}

    except Exception as e:
        logger.error(f"Error getting available models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve available models"
        )


@router.get(
    "/prompts",
    summary="Get available prompt versions",
    description="Get list of available prompt versions and their details",
)
async def get_available_prompts(current_user: dict = Depends(get_current_user)):
    """Get available prompt versions"""

    try:
        from app.services.prompt_manager import get_prompt_manager

        prompt_manager = get_prompt_manager()
        versions = prompt_manager.get_available_versions()
        default_version = prompt_manager.get_default_version()

        prompt_info = []
        for version in versions:
            info = prompt_manager.get_prompt_info(version)
            prompt_info.append(info)

        return {"available_versions": versions, "default_version": default_version, "prompts": prompt_info}

    except Exception as e:
        logger.error(f"Error getting available prompts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve available prompts"
        )


@router.get(
    "/prompts/{version}",
    summary="Get prompt details",
    description="Get detailed information about a specific prompt version",
)
async def get_prompt_details(version: str, preview: bool = False, current_user: dict = Depends(get_current_user)):
    """Get details about a specific prompt version"""

    try:
        from app.services.prompt_manager import get_prompt_manager

        prompt_manager = get_prompt_manager()

        if not prompt_manager.validate_prompt_version(version):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Prompt version '{version}' not found")

        info = prompt_manager.get_prompt_info(version)

        if preview:
            preview_info = prompt_manager.preview_prompt(version)
            info.update(preview_info)

        return info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting prompt details for {version}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve prompt details"
        )


@router.get("/fields", summary="Get field definitions", description="Get all field definitions used for extraction")
async def get_field_definitions(current_user: dict = Depends(get_current_user)):
    """Get field definitions used for extraction"""

    try:
        from app.services.prompt_manager import get_prompt_manager

        prompt_manager = get_prompt_manager()
        fields = prompt_manager.get_all_fields()

        return {"fields": fields, "total_fields": len(fields)}

    except Exception as e:
        logger.error(f"Error getting field definitions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve field definitions"
        )
