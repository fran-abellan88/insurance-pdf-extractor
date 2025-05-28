"""
Tests for Gemini service
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.exceptions import ExtractionError, GeminiAPIError
from app.services.gemini import GeminiService


class TestGeminiService:

    @pytest.fixture
    def gemini_service(self):
        """Create Gemini service instance for testing"""
        with patch("app.services.gemini.genai"):
            return GeminiService()

    @pytest.mark.asyncio
    async def test_extract_from_pdf_success(self, gemini_service):
        """Test successful PDF extraction"""

        mock_response = Mock()
        mock_response.text = '{"quote_number": "123456", "named_insured_name": "Test Company"}'

        with patch.object(gemini_service, "get_model") as mock_get_model:
            mock_model = Mock()
            mock_model.generate_content.return_value = mock_response
            mock_get_model.return_value = mock_model

            with patch("app.services.gemini.genai.upload_file") as mock_upload:
                mock_file = Mock()
                mock_file.name = "test_file"
                mock_upload.return_value = mock_file

                with patch("app.services.gemini.genai.delete_file"):
                    result = await gemini_service.extract_from_pdf(pdf_content=b"test content", prompt="test prompt")

                    assert "extracted_data" in result
                    assert result["extracted_data"]["quote_number"] == "123456"
                    assert "processing_time" in result

    def test_extract_json_from_response_success(self, gemini_service):
        """Test JSON extraction from response"""

        response_text = """
        Here is the extracted data:
        ```json
        {"quote_number": "123456", "named_insured_name": "Test Company"}
        ```
        """

        result = gemini_service._extract_json_from_response(response_text)
        assert result["quote_number"] == "123456"
        assert result["named_insured_name"] == "Test Company"

    def test_extract_json_from_response_failure(self, gemini_service):
        """Test JSON extraction failure"""

        response_text = "No JSON content here"

        with pytest.raises(ExtractionError):
            gemini_service._extract_json_from_response(response_text)
