"""
Tests for response helper utilities
"""

from datetime import datetime

import pytest

from app.utils.response_helpers import (
    create_error_response,
    create_partial_success_response,
    create_success_response,
)


class TestResponseHelpers:

    def test_create_success_response_basic(self):
        """Test creating basic success response"""
        
        extracted_data = {
            "quote_number": "Q123456",
            "named_insured_name": "Test Company",
            "policy_effective_date": "01/01/2024"
        }
        
        response = create_success_response(
            extracted_data=extracted_data,
            processing_time=2.5,
            model_used="gemini-1.5-flash",
            prompt_version="v1"
        )
        
        assert response["status"] == "success"
        assert response["extracted_data"] == extracted_data
        assert response["processing_time"] == 2.5
        assert response["model_used"] == "gemini-1.5-flash"
        assert response["prompt_version"] == "v1"
        assert "timestamp" in response
        
        # Check timestamp is recent (use UTC since that's what the implementation uses)
        timestamp = datetime.fromisoformat(response["timestamp"])
        assert (datetime.utcnow() - timestamp).total_seconds() < 1

    def test_create_success_response_with_file_info(self):
        """Test creating success response with file information"""
        
        extracted_data = {"quote_number": "Q789"}
        file_info = {
            "filename": "test.pdf",
            "size_bytes": 1024,
            "type": "application/pdf"
        }
        
        response = create_success_response(
            extracted_data=extracted_data,
            processing_time=1.0,
            model_used="gemini-1.5-pro",
            prompt_version="v2",
            file_info=file_info
        )
        
        assert response["file_info"] == file_info

    def test_create_success_response_with_confidence_scores(self):
        """Test creating success response with confidence scores"""
        
        extracted_data = {"quote_number": "Q999"}
        confidence_scores = {
            "quote_number": 0.95,
            "named_insured_name": 0.87
        }
        
        response = create_success_response(
            extracted_data=extracted_data,
            processing_time=1.5,
            model_used="gemini-1.5-flash",
            prompt_version="v1",
            confidence_scores=confidence_scores
        )
        
        assert response["confidence_scores"] == confidence_scores

    def test_create_success_response_with_warnings(self):
        """Test creating success response with warnings"""
        
        extracted_data = {"quote_number": "Q111"}
        warnings = ["Date format may be ambiguous", "Low confidence for field X"]
        
        response = create_success_response(
            extracted_data=extracted_data,
            processing_time=2.0,
            model_used="gemini-1.5-flash",
            prompt_version="v1",
            warnings=warnings
        )
        
        assert response["warnings"] == warnings

    def test_create_success_response_none_optional_params(self):
        """Test creating success response with None optional parameters"""
        
        response = create_success_response(
            extracted_data={"test": "data"},
            processing_time=1.0,
            model_used="gemini-1.5-flash",
            prompt_version="v1",
            file_info=None,
            confidence_scores=None,
            warnings=None
        )
        
        # Should not include None optional fields
        assert "file_info" not in response
        assert "confidence_scores" not in response
        assert "warnings" not in response

    def test_create_error_response_basic(self):
        """Test creating basic error response"""
        
        response = create_error_response(
            error_type="ValidationError",
            message="Invalid PDF format"
        )
        
        assert response["status"] == "error"
        assert response["error_type"] == "ValidationError"
        assert response["message"] == "Invalid PDF format"
        assert response["status_code"] == 500
        assert "timestamp" in response

    def test_create_error_response_with_details(self):
        """Test creating error response with details"""
        
        details = {
            "field": "quote_number",
            "expected_format": "alphanumeric",
            "received_value": "invalid@value"
        }
        
        response = create_error_response(
            error_type="FieldValidationError",
            message="Invalid field format",
            details=details,
            status_code=400
        )
        
        assert response["error_type"] == "FieldValidationError"
        assert response["details"] == details
        assert response["status_code"] == 400

    def test_create_error_response_different_status_codes(self):
        """Test creating error responses with different status codes"""
        
        response_400 = create_error_response(
            error_type="BadRequest",
            message="Invalid input",
            status_code=400
        )
        assert response_400["status_code"] == 400
        
        response_404 = create_error_response(
            error_type="NotFound",
            message="Resource not found",
            status_code=404
        )
        assert response_404["status_code"] == 404

    def test_create_error_response_none_details(self):
        """Test creating error response with None details"""
        
        response = create_error_response(
            error_type="TestError",
            message="Test message",
            details=None
        )
        
        # Should not include details key if None
        assert "details" not in response

    def test_create_partial_success_response_basic(self):
        """Test creating basic partial success response"""
        
        extracted_data = {
            "quote_number": "Q123",
            "named_insured_name": "Test Co"
        }
        failed_fields = ["policy_effective_date", "coverage_limit"]
        errors = ["Date format invalid", "Coverage limit not found"]
        
        response = create_partial_success_response(
            extracted_data=extracted_data,
            failed_fields=failed_fields,
            errors=errors,
            processing_time=1.8,
            model_used="gemini-1.5-flash",
            prompt_version="v1"
        )
        
        assert response["status"] == "partial_success"
        assert response["extracted_data"] == extracted_data
        assert response["failed_fields"] == failed_fields
        assert response["errors"] == errors
        assert response["processing_time"] == 1.8
        assert response["model_used"] == "gemini-1.5-flash"
        assert response["prompt_version"] == "v1"
        assert "timestamp" in response

    def test_create_partial_success_response_with_warnings(self):
        """Test creating partial success response with warnings"""
        
        warnings = ["Warning 1", "Warning 2"]
        
        response = create_partial_success_response(
            extracted_data={"quote_number": "Q456"},
            failed_fields=["field1"],
            errors=["Error message"],
            processing_time=2.2,
            model_used="gemini-1.5-pro",
            prompt_version="v2",
            warnings=warnings
        )
        
        assert response["warnings"] == warnings

    def test_create_partial_success_response_none_warnings(self):
        """Test creating partial success response with None warnings"""
        
        response = create_partial_success_response(
            extracted_data={"test": "data"},
            failed_fields=["field1"],
            errors=["error1"],
            processing_time=1.0,
            model_used="gemini-1.5-flash",
            prompt_version="v1",
            warnings=None
        )
        
        # Should not include warnings key if None
        assert "warnings" not in response

    def test_response_timestamp_format(self):
        """Test that all response types have properly formatted timestamps"""
        
        # Test success response timestamp
        success_response = create_success_response(
            extracted_data={"test": "data"},
            processing_time=1.0,
            model_used="test-model",
            prompt_version="v1"
        )
        
        timestamp_str = success_response["timestamp"]
        parsed_timestamp = datetime.fromisoformat(timestamp_str)
        assert isinstance(parsed_timestamp, datetime)
        
        # Test error response timestamp
        error_response = create_error_response("TestError", "Test message")
        error_timestamp_str = error_response["timestamp"]
        error_parsed_timestamp = datetime.fromisoformat(error_timestamp_str)
        assert isinstance(error_parsed_timestamp, datetime)

    def test_response_structure_consistency(self):
        """Test that response structures are consistent"""
        
        # Test success response structure
        success_response = create_success_response(
            extracted_data={},
            processing_time=1.0,
            model_used="test",
            prompt_version="v1"
        )
        
        expected_success_keys = {"status", "extracted_data", "processing_time", "model_used", "prompt_version", "timestamp"}
        assert set(success_response.keys()) == expected_success_keys
        
        # Test error response structure
        error_response = create_error_response("TestError", "message")
        expected_error_keys = {"status", "error_type", "message", "timestamp", "status_code"}
        assert set(error_response.keys()) == expected_error_keys
        
        # Test partial success structure
        partial_response = create_partial_success_response(
            extracted_data={},
            failed_fields=[],
            errors=[],
            processing_time=1.0,
            model_used="test",
            prompt_version="v1"
        )
        
        expected_partial_keys = {"status", "extracted_data", "failed_fields", "errors", "processing_time", "model_used", "prompt_version", "timestamp"}
        assert set(partial_response.keys()) == expected_partial_keys