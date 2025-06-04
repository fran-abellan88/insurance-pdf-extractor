"""
PDF processing service with compatible token counting
"""

import logging
import time
from io import BytesIO
from typing import Any, Dict, Optional

import google.generativeai as genai
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
        include_token_usage: bool = False,
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
            include_token_usage: Whether to include detailed token usage metrics

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

            # Count tokens before processing if requested
            token_metrics = {}
            if include_token_usage:
                try:
                    token_metrics = await self._count_tokens(pdf_content, prompt, model_name)
                    logger.info(f"Input tokens: {token_metrics.get('input_tokens', 'unknown')}")
                except Exception as e:
                    logger.warning(f"Failed to count input tokens: {e}")
                    token_metrics = {"error": str(e)}

            # Extract data using Gemini
            gemini_result = await gemini_service.extract_from_pdf(
                pdf_content=pdf_content,
                prompt=prompt,
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Add token usage from response if available
            if include_token_usage and "usage_metadata" in gemini_result:
                usage_meta = gemini_result["usage_metadata"]
                # Update token_metrics with actual usage data
                token_metrics.update(
                    {
                        "prompt_token_count": usage_meta.get("prompt_token_count", 0),
                        "candidates_token_count": usage_meta.get("candidates_token_count", 0),
                        "total_token_count": usage_meta.get("total_token_count", 0),
                    }
                )

                # Calculate cost based on actual input/output usage
                input_tokens = token_metrics.get("prompt_token_count", 0)
                output_tokens = token_metrics.get("candidates_token_count", 0)
                if input_tokens > 0 or output_tokens > 0:
                    token_metrics["estimated_cost"] = self._estimate_cost(input_tokens, output_tokens, model_name)
                    token_metrics["cost_breakdown"] = self._get_detailed_cost_breakdown(
                        input_tokens, output_tokens, model_name
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

            # Add token usage if requested and available
            if include_token_usage:
                response["token_usage"] = token_metrics

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

            # Add token metrics to overall metrics if available
            if include_token_usage and token_metrics and "error" not in token_metrics:
                response["metrics"]["token_metrics"] = {
                    "input_tokens": token_metrics.get("prompt_token_count", 0),
                    "output_tokens": token_metrics.get("candidates_token_count", 0),
                    "total_tokens": token_metrics.get("total_token_count", 0),
                }

            logger.info(f"PDF processing completed successfully in {total_processing_time:.2f}s")
            return response

        except Exception as e:
            total_processing_time = time.time() - start_time
            logger.error(f"PDF processing failed after {total_processing_time:.2f}s: {e}")
            raise

    async def _count_tokens(self, pdf_content: bytes, prompt: str, model_name: str) -> Dict[str, Any]:
        """
        Count tokens for the given PDF and prompt using the older API

        Args:
            pdf_content: PDF file content as bytes
            prompt: The prompt text
            model_name: Gemini model name

        Returns:
            Dict containing token count information
        """
        try:
            # Create a temporary file for upload
            import os
            import tempfile

            temp_file_path = None
            pdf_file = None

            try:
                # Create temporary file
                temp_fd, temp_file_path = tempfile.mkstemp(suffix=".pdf")

                # Write PDF content to temp file
                with os.fdopen(temp_fd, "wb") as temp_file:
                    temp_file.write(pdf_content)

                # Upload PDF file to Gemini
                pdf_file = genai.upload_file(
                    path=temp_file_path, display_name="token_count_pdf.pdf", mime_type="application/pdf"
                )

                # Wait for file to be processed
                while pdf_file.state.name == "PROCESSING":
                    time.sleep(0.5)
                    pdf_file = genai.get_file(pdf_file.name)

                if pdf_file.state.name == "FAILED":
                    raise Exception("File processing failed in Gemini for token counting")

                # Use the older count_tokens method directly on the model
                model = genai.GenerativeModel(model_name)

                # Create the content list similar to what we send for generation
                content = [prompt, pdf_file]

                # Count tokens using the model's count_tokens method
                token_count = model.count_tokens(content)

                # Extract the token count (the exact attribute name may vary)
                total_tokens = getattr(token_count, "total_tokens", 0)

                return {
                    "input_tokens": total_tokens,
                    "prompt_token_count": total_tokens,
                    # Note: We can't estimate output tokens beforehand, so cost will be calculated after generation
                }

            finally:
                # Clean up temporary file
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                    except Exception as e:
                        logger.warning(f"Failed to clean up temporary file: {e}")

                # Clean up uploaded file from Gemini
                if pdf_file and hasattr(pdf_file, "name"):
                    try:
                        genai.delete_file(pdf_file.name)
                    except Exception as e:
                        logger.warning(f"Failed to clean up uploaded file from Gemini: {e}")

        except Exception as e:
            logger.error(f"Token counting failed: {e}")
            raise

    def _estimate_cost(self, input_tokens: int, output_tokens: int, model_name: str) -> float:
        """
        Estimate the cost based on input and output token counts and model

        Args:
            input_tokens: Number of input tokens (prompt + PDF)
            output_tokens: Number of output tokens (generated response)
            model_name: Model name

        Returns:
            Estimated cost in USD
        """
        # Prices per 1,000 tokens
        pricing = {
            "gemini-1.5-flash": {
                "input": 0.000075,  # $0.075 per 1M tokens
                "output": 0.0003,  # $0.30 per 1M tokens
            },
            "gemini-1.5-pro": {
                "input": 0.00125,  # $1.25 per 1M tokens
                "output": 0.005,  # $5.00 per 1M tokens
            },
            "gemini-2.5-flash-preview-05-20": {
                "input": 0.00015,  # $0.150 per 1M tokens
                "output": 0.0006,  # $0.600 per 1M tokens
            },
            "gemini-2.5-pro": {
                "input": 0.00125,  # $1.25 per 1M tokens
                "output": 0.0100,  # $10.00 per 1M tokens
            },
        }

        # Extract base model name
        base_model = model_name
        if base_model not in pricing:
            # Try to match partial names
            for key in pricing.keys():
                if key in model_name:
                    base_model = key
                    break
            else:
                base_model = "gemini-1.5-flash"  # Default fallback

        model_pricing = pricing[base_model]

        # Calculate costs separately
        input_cost = (input_tokens / 1000) * model_pricing["input"]
        output_cost = (output_tokens / 1000) * model_pricing["output"]
        total_cost = input_cost + output_cost

        return round(total_cost, 6)

    def _get_detailed_cost_breakdown(self, input_tokens: int, output_tokens: int, model_name: str) -> Dict[str, Any]:
        """
        Get detailed cost breakdown for transparency

        Returns:
            Dict with detailed cost information
        """
        # Get the pricing info (reuse logic from _estimate_cost)
        pricing = {
            "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
            "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
            "gemini-2.0-flash": {"input": 0.000075, "output": 0.0003},
            "gemini-2.5-flash-preview-05-20": {"input": 0.000075, "output": 0.0003},
        }

        base_model = model_name
        if base_model not in pricing:
            for key in pricing.keys():
                if key in model_name:
                    base_model = key
                    break
            else:
                base_model = "gemini-1.5-flash"

        model_pricing = pricing[base_model]

        input_cost = (input_tokens / 1000) * model_pricing["input"]
        output_cost = (output_tokens / 1000) * model_pricing["output"]
        total_cost = input_cost + output_cost

        return {
            "model_used": base_model,
            "pricing_per_1k_tokens": model_pricing,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "total_cost": round(total_cost, 6),
            "cost_breakdown": f"${round(input_cost, 6)} (input) + ${round(output_cost, 6)} (output) = ${round(total_cost, 6)}",
        }

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
