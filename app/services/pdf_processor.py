"""
PDF processing service
"""

import logging
import time
from io import BytesIO
from typing import Any, Dict, Optional

import pypdf

from app.core.config import get_settings
from app.core.exceptions import FileProcessingError
from app.models.extraction import ExtractionResult, validate_extracted_data
from app.services.gemini import gemini_service
from app.services.prompt_manager import get_prompt_manager

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Service for processing PDF files and extracting insurance data"""

    def __init__(self):
        self.settings = get_settings()
        self.prompt_manager = get_prompt_manager()

    async def process_pdf(
        self,
        pdf_content: bytes,
        filename: str,
        model_name: str = "gemini-1.5-flash",
        prompt_version: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        include_confidence: bool = False,
    ) -> Dict[str, Any]:
        """
        Process PDF and extract insurance data

        Args:
            pdf_content: PDF file content as bytes
            filename: Original filename
            model_name: Gemini model to use
            prompt_version: Version of prompt to use
            temperature: AI model temperature
            max_tokens: Maximum tokens for response
            include_confidence: Whether to include confidence scores

        Returns:
            Dict containing extraction results
        """
        start_time = time.time()

        try:
            # Validate PDF file
            self._validate_pdf(pdf_content, filename)

            # Get prompt
            prompt = self.prompt_manager.get_prompt(prompt_version)
            logger.info(f"Using prompt version: {prompt_version or 'latest'}")

            # Extract data using Gemini
            gemini_result = await gemini_service.extract_from_pdf(
                pdf_content=pdf_content,
                prompt=prompt,
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Validate extracted data
            validation_result = validate_extracted_data(gemini_result["extracted_data"])

            total_processing_time = time.time() - start_time

            # Prepare response
            response = {
                "status": "success" if validation_result.is_valid else "partial_success",
                "extracted_data": validation_result.data.model_dump(),
                "processing_time": total_processing_time,
                "model_used": model_name,
                "prompt_version": prompt_version or self.prompt_manager.get_default_version(),
                "file_info": {
                    "filename": filename,
                    "size_bytes": len(pdf_content),
                    "size_mb": round(len(pdf_content) / (1024 * 1024), 2),
                },
            }

            # Add validation info if there are issues
            if not validation_result.is_valid:
                response["failed_fields"] = self._extract_failed_fields(validation_result.validation_errors)
                response["errors"] = validation_result.validation_errors

            if validation_result.has_warnings:
                response["warnings"] = validation_result.warnings

            # Add confidence scores if requested
            if include_confidence:
                response["confidence_scores"] = self._calculate_confidence_scores(
                    validation_result.data.model_dump(), gemini_result.get("response_text", "")
                )

            # Add detailed metrics
            response["metrics"] = {
                "gemini_processing_time": gemini_result["processing_time"],
                "validation_time": total_processing_time - gemini_result["processing_time"],
                "total_fields": len(self.prompt_manager.get_all_fields()),
                "extracted_fields": len(
                    [v for v in validation_result.data.model_dump().values() if v != "EMPTY VALUE"]
                ),
                "validation_errors": len(validation_result.validation_errors),
                "warnings": len(validation_result.warnings),
            }

            logger.info(f"PDF processing completed successfully in {total_processing_time:.2f}s")
            return response

        except Exception as e:
            total_processing_time = time.time() - start_time
            logger.error(f"PDF processing failed after {total_processing_time:.2f}s: {e}")
            raise

    def _validate_pdf(self, pdf_content: bytes, filename: str) -> None:
        """
        Validate PDF file content and metadata

        Args:
            pdf_content: PDF file content
            filename: Original filename

        Raises:
            FileProcessingError: If validation fails
        """
        try:
            # Check file size
            max_size = self.settings.max_file_size_mb * 1024 * 1024
            if len(pdf_content) > max_size:
                raise FileProcessingError(
                    f"File size {len(pdf_content)} bytes exceeds maximum {max_size} bytes", filename, len(pdf_content)
                )

            # Check if it's a valid PDF
            try:
                pdf_reader = pypdf.PdfReader(BytesIO(pdf_content))
                num_pages = len(pdf_reader.pages)

                if num_pages == 0:
                    raise FileProcessingError("PDF file contains no pages", filename)

                # Try to extract some text to ensure it's readable
                first_page = pdf_reader.pages[0]
                text_sample = first_page.extract_text()

                if not text_sample or len(text_sample.strip()) < 10:
                    logger.warning(f"PDF {filename} may be image-based or have little text content")

                logger.info(f"PDF validation successful: {filename} ({num_pages} pages)")

            except Exception as e:
                raise FileProcessingError(f"Invalid PDF file: {str(e)}", filename)

        except FileProcessingError:
            raise
        except Exception as e:
            raise FileProcessingError(f"PDF validation failed: {str(e)}", filename)

    def _extract_failed_fields(self, validation_errors: list) -> list:
        """Extract field names that failed validation"""
        failed_fields = []

        for error in validation_errors:
            # Try to extract field names from error messages
            # This is a simple heuristic - could be improved
            if "field" in error.lower():
                # Extract quoted field names
                import re

                matches = re.findall(r"'([^']*)'", error)
                failed_fields.extend(matches)

        return list(set(failed_fields))  # Remove duplicates

    def _calculate_confidence_scores(self, extracted_data: dict, response_text: str) -> dict:
        """
        Calculate confidence scores for extracted fields
        This is a simple heuristic - could be improved with ML models

        Args:
            extracted_data: Extracted and validated data
            response_text: Original AI response text

        Returns:
            Dict of field confidence scores (0.0 to 1.0)
        """
        confidence_scores = {}

        for field, value in extracted_data.items():
            if value == "EMPTY VALUE":
                confidence_scores[field] = 0.0
            else:
                # Simple heuristic based on value characteristics
                score = 0.5  # Base score

                # Higher confidence for longer, more structured values
                if len(str(value)) > 5:
                    score += 0.2

                # Higher confidence if value appears in original response
                if str(value) in response_text:
                    score += 0.2

                # Lower confidence for very short values
                if len(str(value)) < 3:
                    score -= 0.1

                # Field-specific rules
                if field in ["quote_number", "named_insured_name"]:
                    score += 0.1  # Usually reliable

                if field.endswith("_date") and "/" in str(value):
                    score += 0.1  # Date format gives confidence

                confidence_scores[field] = min(1.0, max(0.0, score))

        return confidence_scores

    def get_pdf_info(self, pdf_content: bytes) -> Dict[str, Any]:
        """
        Extract metadata and basic info from PDF

        Args:
            pdf_content: PDF file content

        Returns:
            Dict containing PDF information
        """
        try:
            pdf_reader = pypdf.PdfReader(BytesIO(pdf_content))

            info = {
                "num_pages": len(pdf_reader.pages),
                "size_bytes": len(pdf_content),
                "size_mb": round(len(pdf_content) / (1024 * 1024), 2),
            }

            # Try to get metadata
            if pdf_reader.metadata:
                metadata = pdf_reader.metadata
                info["metadata"] = {
                    "title": metadata.get("/Title", ""),
                    "author": metadata.get("/Author", ""),
                    "subject": metadata.get("/Subject", ""),
                    "creator": metadata.get("/Creator", ""),
                    "producer": metadata.get("/Producer", ""),
                    "creation_date": str(metadata.get("/CreationDate", "")),
                    "modification_date": str(metadata.get("/ModDate", "")),
                }

            # Extract text sample from first page
            if len(pdf_reader.pages) > 0:
                first_page_text = pdf_reader.pages[0].extract_text()
                info["first_page_preview"] = first_page_text[:500] if first_page_text else "No text extracted"
                info["estimated_text_length"] = len(first_page_text) if first_page_text else 0

            return info

        except Exception as e:
            logger.error(f"Failed to extract PDF info: {e}")
            return {
                "num_pages": 0,
                "size_bytes": len(pdf_content),
                "size_mb": round(len(pdf_content) / (1024 * 1024), 2),
                "error": str(e),
            }


# Global processor instance
pdf_processor = PDFProcessor()
