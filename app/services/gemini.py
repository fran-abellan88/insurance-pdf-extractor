"""
Gemini AI service for PDF processing
"""

import json
import logging
import re
import time
from io import BytesIO
from typing import Any, Dict, Optional

import google.generativeai as genai

from app.core.config import get_settings
from app.core.exceptions import ExtractionError, GeminiAPIError

logger = logging.getLogger(__name__)


class GeminiService:
    """Service for interacting with Google's Gemini AI"""

    def __init__(self):
        self.settings = get_settings()
        self._configure_gemini()
        self._models = {}

    def _configure_gemini(self):
        """Configure Gemini API with API key"""
        try:
            genai.configure(api_key=self.settings.gemini_api_key)
            logger.info("Gemini API configured successfully")
        except Exception as e:
            logger.error(f"Failed to configure Gemini API: {e}")
            raise GeminiAPIError(f"Failed to configure Gemini API: {e}")

    def get_model(self, model_name: str):
        """Get or create a Gemini model instance"""
        if model_name not in self._models:
            try:
                self._models[model_name] = genai.GenerativeModel(model_name)
                logger.info(f"Created Gemini model instance: {model_name}")
            except Exception as e:
                logger.error(f"Failed to create model {model_name}: {e}")
                raise GeminiAPIError(f"Failed to create model {model_name}: {e}")

        return self._models[model_name]

    async def extract_from_pdf(
        self,
        pdf_content: bytes,
        prompt: str,
        model_name: str = "gemini-1.5-flash",
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        Extract data from PDF using Gemini AI

        Args:
            pdf_content: PDF file content as bytes
            prompt: Extraction prompt
            model_name: Gemini model to use
            temperature: Model temperature
            max_tokens: Maximum tokens for response

        Returns:
            Dict containing extracted data

        Raises:
            GeminiAPIError: If API call fails
            ExtractionError: If extraction fails
        """
        start_time = time.time()
        temp_file_path = None
        pdf_file = None

        try:
            # Get model instance
            model = self.get_model(model_name)

            # Save PDF content to temporary file for Gemini upload
            import os
            import tempfile

            logger.info(f"Uploading PDF content ({len(pdf_content)} bytes) to Gemini")

            # Create temporary file (don't delete automatically)
            temp_fd, temp_file_path = tempfile.mkstemp(suffix=".pdf")
            try:
                # Write PDF content to temp file
                with os.fdopen(temp_fd, "wb") as temp_file:
                    temp_file.write(pdf_content)

                logger.debug(f"Created temporary file: {temp_file_path}")

                # Upload PDF file to Gemini
                pdf_file = genai.upload_file(
                    path=temp_file_path, display_name="insurance_quote.pdf", mime_type="application/pdf"
                )

                logger.debug(f"Uploaded file to Gemini: {pdf_file.name}")

                # Wait for file to be processed
                logger.debug("Waiting for file processing...")
                import time as time_module

                while pdf_file.state.name == "PROCESSING":
                    time_module.sleep(1)
                    pdf_file = genai.get_file(pdf_file.name)

                if pdf_file.state.name == "FAILED":
                    raise ExtractionError("File processing failed in Gemini")

                logger.debug("File processing completed successfully")

                # Configure generation parameters
                generation_config = genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    candidate_count=1,
                )

                # Generate content
                logger.info(f"Generating content with model {model_name}")
                response = model.generate_content([pdf_file, prompt], generation_config=generation_config)

                processing_time = time.time() - start_time
                logger.info(f"Gemini processing completed in {processing_time:.2f} seconds")

                # Extract JSON from response
                if not response.text:
                    raise ExtractionError("Empty response from Gemini API")

                extracted_data = self._extract_json_from_response(response.text)

                return {
                    "extracted_data": extracted_data,
                    "processing_time": processing_time,
                    "model_used": model_name,
                    "response_text": response.text[:500] + "..." if len(response.text) > 500 else response.text,
                }

            except Exception as e:
                print(e)
                # If temp file creation failed, temp_fd might still be open
                try:
                    os.close(temp_fd)
                except Exception as e:
                    print(e)
                    pass
                raise

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Gemini extraction failed after {processing_time:.2f}s: {e}")

            if "quota" in str(e).lower() or "rate limit" in str(e).lower():
                raise GeminiAPIError("API rate limit exceeded. Please try again later.", status_code=429)
            elif "authentication" in str(e).lower() or "api key" in str(e).lower():
                raise GeminiAPIError("Authentication failed. Please check API key.", status_code=401)
            else:
                raise GeminiAPIError(f"Gemini API error: {str(e)}")

        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                    logger.debug(f"Temporary file cleaned up: {temp_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_file_path}: {e}")

            # Clean up uploaded file from Gemini
            if pdf_file and hasattr(pdf_file, "name"):
                try:
                    genai.delete_file(pdf_file.name)
                    logger.debug(f"Uploaded file cleaned up from Gemini: {pdf_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to clean up uploaded file from Gemini: {e}")

    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """
        Extract JSON data from Gemini response using multiple strategies

        Args:
            response_text: Raw response text from Gemini

        Returns:
            Parsed JSON data

        Raises:
            ExtractionError: If no valid JSON found
        """
        logger.debug(f"Extracting JSON from response (length: {len(response_text)})")

        # Strategy 1: Look for JSON code blocks
        json_patterns = [
            r"```json\s*(\{.*?\})\s*```",  # JSON code block
            r"```\s*(\{.*?\})\s*```",  # Generic code block
            r"json\s*(\{.*?\})",  # json keyword
            r"(\{.*?\})",  # Any JSON-like structure
        ]

        for i, pattern in enumerate(json_patterns, 1):
            matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)

            for match in matches:
                try:
                    # Clean up the match
                    cleaned_json = match.strip()

                    # Try to parse JSON
                    parsed_data = json.loads(cleaned_json)

                    if isinstance(parsed_data, dict) and parsed_data:
                        logger.info(f"Successfully extracted JSON using strategy {i}")
                        return parsed_data

                except json.JSONDecodeError as e:
                    logger.debug(f"Strategy {i} JSON parse failed: {e}")
                    continue
                except Exception as e:
                    logger.debug(f"Strategy {i} failed: {e}")
                    continue

        # Strategy 2: Try to extract key-value pairs manually
        logger.warning("JSON extraction strategies failed, attempting manual parsing")

        try:
            manual_data = self._manual_json_extraction(response_text)
            if manual_data:
                logger.info("Successfully extracted data using manual parsing")
                return manual_data
        except Exception as e:
            logger.debug(f"Manual extraction failed: {e}")

        # If all strategies fail
        logger.error("All JSON extraction strategies failed")
        raise ExtractionError(
            "Could not extract valid JSON from AI response",
            details={"response_preview": response_text[:500], "response_length": len(response_text)},
        )

    def _manual_json_extraction(self, text: str) -> Dict[str, Any]:
        """
        Manual extraction of key-value pairs from text
        This is a fallback when JSON parsing fails
        """
        result = {}

        # Common field patterns
        field_patterns = [
            r'"?([a-z_]+)"?\s*:\s*"([^"]*)"',  # "field": "value"
            r'"?([a-z_]+)"?\s*:\s*([^,\n}]+)',  # "field": value
        ]

        for pattern in field_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)

            for field, value in matches:
                field = field.strip().lower()
                value = value.strip().strip('"').strip("'")

                # Skip empty values
                if value and value != "null":
                    result[field] = value

        return result if result else None

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to Gemini API

        Returns:
            Dict with connection status and available models
        """
        try:
            # Try to list available models
            models = []
            for model in genai.list_models():
                if "generateContent" in model.supported_generation_methods:
                    models.append(model.name)

            # Test a simple generation
            test_model = self.get_model("gemini-1.5-flash")
            test_response = test_model.generate_content("Hello, respond with 'API working'")

            return {
                "status": "connected",
                "available_models": models,
                "test_response": test_response.text if test_response.text else "No response",
                "api_accessible": True,
            }

        except Exception as e:
            logger.error(f"Gemini API connection test failed: {e}")
            return {
                "status": "error",
                "available_models": [],
                "test_response": None,
                "api_accessible": False,
                "error": str(e),
            }


# Global service instance
gemini_service = GeminiService()
