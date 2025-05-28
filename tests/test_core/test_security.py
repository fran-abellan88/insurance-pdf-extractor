"""
Tests for security functionality
"""
import pytest
from fastapi import HTTPException

from app.core.security import APIKeyAuth


class TestAPIKeySecurity:

    def test_valid_api_key(self):
        """Test validation with valid API key"""

        auth = APIKeyAuth()
        auth.valid_api_key = {"test-key-123"}

        assert auth.validate_api_key("test-key-123") is True
        assert auth.validate_api_key("invalid-key") is False

    def test_get_api_key_info(self):
        """Test getting API key information"""

        auth = APIKeyAuth()
        auth.valid_api_key = {"test-key-123"}

        info = auth.get_api_key_info("test-key-123")
        assert info is not None
        assert info["valid"] is True
        assert "test-key" in info["key"]  # Should show truncated key
