"""
Tests for extraction endpoints
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status


class TestExtractionEndpoint:

    def test_extract_pdf_success(self, client, auth_headers, mock_pdf_content, sample_extracted_data):
        """Test successful PDF extraction"""

        with patch("app.services.pdf_processor.pdf_processor.process_pdf") as mock_process:
            mock_process.return_value = {
                "status": "success",
                "extracted_data": sample_extracted_data,
                "processing_time": 2.5,
                "model_used": "gemini-1.5-flash",
                "prompt_version": "v1",
                "file_info": {"filename": "test.pdf", "size_bytes": 1024},
            }

            response = client.post(
                "/api/v1/extract",
                headers=auth_headers,
                files={"file": ("test.pdf", mock_pdf_content, "application/pdf")},
                data={"model": "gemini-1.5-flash"},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "extracted_data" in data
            assert data["extracted_data"]["quote_number"] == "123456"

    def test_extract_pdf_unauthorized(self, client, mock_pdf_content):
        """Test extraction without API key"""

        response = client.post("/api/v1/extract", files={"file": ("test.pdf", mock_pdf_content, "application/pdf")})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_extract_pdf_invalid_file_type(self, client, auth_headers):
        """Test extraction with non-PDF file"""

        response = client.post(
            "/api/v1/extract", headers=auth_headers, files={"file": ("test.txt", b"text content", "text/plain")}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_extract_pdf_partial_success(self, client, auth_headers, mock_pdf_content):
        """Test partial extraction success"""

        with patch("app.services.pdf_processor.pdf_processor.process_pdf") as mock_process:
            mock_process.return_value = {
                "status": "partial_success",
                "extracted_data": {"quote_number": "123456"},
                "failed_fields": ["named_insured_name"],
                "errors": ["Could not extract named insured name"],
                "processing_time": 2.5,
                "model_used": "gemini-1.5-flash",
                "prompt_version": "v7",
            }

            response = client.post(
                "/api/v1/extract",
                headers=auth_headers,
                files={"file": ("test.pdf", mock_pdf_content, "application/pdf")},
            )

            assert response.status_code == 206  # Partial Content
            data = response.json()
            assert data["status"] == "partial_success"
            assert "failed_fields" in data
