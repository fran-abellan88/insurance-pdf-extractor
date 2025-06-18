"""
Document type detection service using AI to identify document types
"""

import logging
from typing import Optional

from app.core.exceptions import DocumentProcessingError
from app.services.gemini import GeminiService

logger = logging.getLogger(__name__)


class DocumentTypeDetector:
    """Service to detect document types from PDF content"""

    def __init__(self, gemini_service: GeminiService):
        self.gemini_service = gemini_service

    async def detect_document_type(self, pdf_content: bytes, filename: str = "") -> str:
        """
        Detect the type of insurance document from PDF content

        Args:
            pdf_content: Raw PDF bytes
            filename: Optional filename for additional context

        Returns:
            str: Document type identifier (e.g., 'quote', 'binder')

        Raises:
            DocumentProcessingError: If document type cannot be determined
        """
        try:
            detection_prompt = self._build_detection_prompt(filename)

            # Use Gemini to analyze the document and determine type
            result = await self.gemini_service.extract_from_pdf(
                pdf_content=pdf_content,
                prompt=detection_prompt,
                model_name="gemini-1.5-flash",  # Use fast model for detection
                temperature=0.1,
                max_tokens=100  # Short response expected
            )

            # Parse the response to get document type
            # The Gemini service returns response_text for the raw response
            response_text = result.get("response_text", "")
            
            # Log the raw response for debugging
            logger.info(f"Raw Gemini response for {filename}: {response_text[:200]}...")
            
            document_type = self._parse_detection_result(response_text)

            logger.info(f"Detected document type: {document_type} for file: {filename}")
            return document_type

        except Exception as e:
            logger.error(f"Failed to detect document type for {filename}: {str(e)}")
            # Default to quote if detection fails
            return "quote"

    def _build_detection_prompt(self, filename: str = "") -> str:
        """Build prompt for document type detection"""
        context = f" The filename is: {filename}." if filename else ""

        return f"""
        Analyze this insurance document and determine its type.{context}

        Return ONLY one of these document types:
        - quote: A quote for any type of insurance coverage
        - binder: A temporary insurance document providing immediate coverage

        Look for these key indicators:

        Insurance Quote:
        - Contains "Quote" or "Quotation" in the title
        - Has detailed premium calculations
        - Shows class codes and payroll information
        - Contains state-specific workers comp information
        - Has "Quote Number" field

        Binder:
        - Contains "Binder" in the title or header
        - Mentions "temporary coverage" or "pending policy issuance"
        - Has binder number or reference
        - Lists multiple coverage types (GL, Auto, Property, etc.)
        - Contains certificate holder information
        - Has "effective immediately" or similar language

        Respond with ONLY the document type identifier, nothing else.
        """

    def _parse_detection_result(self, response: str) -> str:
        """Parse AI response to extract document type"""
        response = response.strip().lower()

        # Look for exact matches first
        if "quote" in response:
            return "quote"
        elif "binder" in response:
            return "binder"

        # Look for partial matches
        if "quot" in response:
            return "quote"
        elif "bind" in response:
            return "binder"

        # Default fallback
        logger.warning(f"Could not parse document type from response: {response}")
        return "quote"

    def get_supported_document_types(self) -> list[str]:
        """Get list of supported document types"""
        return ["quote", "binder"]
