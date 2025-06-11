"""
API routes for PDF extraction
"""

import logging
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.exceptions import ExtractionError, FileProcessingError, GeminiAPIError
from app.core.security import get_current_user
from app.models.request import ModelType
from app.models.response import (
    ErrorResponse,
    ExtractionResponse,
    PartialExtractionResponse,
)
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
    Upload a PDF file containing an insurance document and extract structured data.

    The service will:
    1. Validate the PDF file
    2. Use the specified document type to select appropriate extraction fields
    3. Extract text using Gemini AI
    4. Parse and validate the extracted data
    5. Store the results locally with token usage tracking
    6. Return structured JSON with insurance information

    **Authentication**: Requires X-API-Key header

    **File Requirements**:
    - PDF format only
    - Maximum size: 10MB
    - Must contain readable text (not just images)

    **Document Types**:
    - `quote`: Insurance quotes for any line of coverage (default)
    - `binder`: Insurance binder documents providing temporary coverage

    **Models Available**:
    - `gemini-1.5-flash`: Faster, good for most cases
    - `gemini-1.5-pro`: More accurate, slower
    - `gemini-2.5-flash-preview`: Latest preview model

    **Token Usage**: Enable `include_token_usage` to get detailed token consumption metrics and cost estimates.
    **Confidence Scores**: Enable `include_confidence` to get confidence scores for each extracted field.
    **Page Sources**: Enable `include_page_sources` to get page source information for each extracted field.
    """,
)
@limiter.limit("10/minute")
async def extract_pdf_data(
    request: Request,
    file: UploadFile = File(..., description="PDF file to process"),
    model: ModelType = Form(default=ModelType.FLASH, description="Gemini model to use"),
    document_type: str = Form(default="quote", description="Document type: 'quote' or 'binder'"),
    prompt_version: Optional[str] = Form(default=None, description="Prompt version (e.g., 'v2')"),
    temperature: float = Form(default=0.1, ge=0.0, le=1.0, description="AI model temperature"),
    max_tokens: int = Form(default=4096, ge=1, le=8192, description="Maximum response tokens"),
    include_confidence: bool = Form(default=False, description="Include confidence scores"),
    include_token_usage: bool = Form(default=False, description="Include detailed token usage and cost estimates"),
    include_page_sources: bool = Form(default=False, description="Include page source information for each field"),
    current_user: dict = Depends(get_current_user),
):
    """Extract structured data from insurance PDF with enhanced token tracking"""

    logger.info("PDF extraction request started")

    try:
        # Validate document type
        supported_types = ["quote", "binder"]
        if document_type not in supported_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid document_type. Supported types: {supported_types}",
            )

        # Validate file type
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are supported")

        # Read file content
        pdf_content = await file.read()
        logger.info(f"Processing PDF: {file.filename} ({len(pdf_content)} bytes) as {document_type}")

        # Process PDF
        result = await pdf_processor.process_pdf(
            pdf_content=pdf_content,
            filename=file.filename,
            model_name=model.value,
            document_type=document_type,
            prompt_version=prompt_version,
            temperature=temperature,
            max_tokens=max_tokens,
            include_confidence=include_confidence,
            include_token_usage=include_token_usage,
            include_page_sources=include_page_sources,
        )

        # Store the extraction results locally with token usage
        try:
            from app.services.storage import storage_service

            extraction_id = storage_service.store_extraction(
                filename=file.filename,
                file_size=len(pdf_content),
                status=result["status"],
                model_used=result["model_used"],
                prompt_version=result["prompt_version"],
                processing_time=result["processing_time"],
                extracted_data=result["extracted_data"],
                num_pages=result.get("file_info", {}).get("num_pages"),
                confidence_scores=result.get("confidence_scores"),
                page_sources=result.get("page_sources"),
                failed_fields=result.get("failed_fields"),
                warnings=result.get("warnings"),
                user_key=current_user.get("key", "unknown"),
                token_usage=result.get("token_usage"),  # Pass token usage data
                document_type=result.get("document_type", "quote"),  # Pass document type
            )

            # Add extraction ID to the response
            result["extraction_id"] = extraction_id
            logger.info(f"Stored extraction results with ID: {extraction_id}")

            # Log token usage if available
            if result.get("token_usage") and "error" not in result["token_usage"]:
                token_info = result["token_usage"]
                logger.info(
                    f"Token usage stored - Input: {token_info.get('prompt_token_count', 0)}, "
                    f"Output: {token_info.get('candidates_token_count', 0)}, "
                    f"Cost: ${token_info.get('estimated_cost', 0):.6f}"
                )

        except Exception as storage_error:
            # Log storage error but don't fail the extraction
            logger.error(f"Failed to store extraction results: {storage_error}")
            # Optionally add a warning to the response
            if "warnings" not in result:
                result["warnings"] = []
            result["warnings"].append("Results could not be stored locally")

        # Determine response type based on result status
        if result["status"] == "success":
            return ExtractionResponse(**result)
        elif result["status"] == "partial_success":
            return JSONResponse(
                status_code=206, content=PartialExtractionResponse(**result).model_dump(mode="json")
            )  # Partial Content
        else:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Extraction failed")

    except HTTPException as e:
        # Re-raise HTTP exceptions as-is (don't log as errors)
        logger.info(f"HTTP exception raised: {e.status_code} - {e.detail}")
        raise

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
            {
                "name": "gemini-2.5-flash-preview-05-20",
                "display_name": "Gemini 2.5 Flash Preview",
                "description": "Placeholder",
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
    description="Get list of available prompt versions and their details for all document types",
)
async def get_available_prompts(document_type: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get available prompt versions for all or specific document types"""

    try:
        from app.services.prompt_manager import get_prompt_manager

        prompt_manager = get_prompt_manager()
        default_version = prompt_manager.get_default_version()

        if document_type:
            # Get prompts for specific document type
            versions = prompt_manager.get_available_versions(document_type)
            prompt_info = []
            for version in versions:
                info = prompt_manager.get_prompt_info(document_type, version)
                prompt_info.append(info)

            return {
                "document_type": document_type,
                "available_versions": versions,
                "default_version": default_version,
                "prompts": prompt_info,
            }
        else:
            # Get prompts for all document types
            document_types = ["quote", "binder"]
            all_prompts = {}

            for doc_type in document_types:
                versions = prompt_manager.get_available_versions(doc_type)
                prompt_info = []
                for version in versions:
                    info = prompt_manager.get_prompt_info(doc_type, version)
                    prompt_info.append(info)

                all_prompts[doc_type] = {"available_versions": versions, "prompts": prompt_info}

            return {
                "document_types": all_prompts,
                "default_version": default_version,
                "supported_document_types": document_types,
            }

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
async def get_field_definitions(document_type: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get field definitions used for extraction for all or specific document types"""

    try:
        from app.services.prompt_manager import get_prompt_manager

        prompt_manager = get_prompt_manager()

        if document_type:
            # Get fields for specific document type
            fields = prompt_manager.get_all_fields(document_type)
            return {"document_type": document_type, "fields": fields, "total_fields": len(fields)}
        else:
            # Get fields for all document types
            document_types = ["quote", "binder"]
            all_fields = {}

            for doc_type in document_types:
                fields = prompt_manager.get_all_fields(doc_type)
                all_fields[doc_type] = {"fields": fields, "total_fields": len(fields)}

            return {"document_types": all_fields, "supported_document_types": document_types}

    except Exception as e:
        logger.error(f"Error getting field definitions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve field definitions"
        )


@router.get(
    "/document-types", summary="Get supported document types", description="Get list of supported document types"
)
async def get_supported_document_types(current_user: dict = Depends(get_current_user)):
    """Get list of supported document types"""

    try:
        from app.services.document_detector import DocumentTypeDetector
        from app.services.gemini import gemini_service

        detector = DocumentTypeDetector(gemini_service)
        supported_types = detector.get_supported_document_types()

        return {
            "supported_document_types": supported_types,
            "total_types": len(supported_types),
            "default_type": "quote",
        }

    except Exception as e:
        logger.error(f"Error getting supported document types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve supported document types"
        )
