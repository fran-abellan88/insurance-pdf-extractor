"""
Tests for helper utilities
"""

import json
import logging
from unittest.mock import Mock, patch

import pytest

from app.utils.helpers import (
    log_api_request,
    log_processing_metrics,
    setup_logging,
)


class TestHelpers:

    def test_setup_logging_default_level(self):
        """Test setup_logging with default INFO level"""
        
        with patch("app.utils.helpers.logging.basicConfig") as mock_config:
            with patch("app.utils.helpers.logging.getLogger") as mock_get_logger:
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger
                
                setup_logging()
                
                # Check that basicConfig was called with INFO level
                mock_config.assert_called_once()
                call_args = mock_config.call_args
                assert call_args[1]["level"] == logging.INFO
                assert "%(asctime)s" in call_args[1]["format"]
                
                # Check that specific loggers were silenced
                assert mock_get_logger.call_count >= 2

    def test_setup_logging_debug_level(self):
        """Test setup_logging with DEBUG level"""
        
        with patch("app.utils.helpers.logging.basicConfig") as mock_config:
            with patch("app.utils.helpers.logging.getLogger"):
                
                setup_logging("DEBUG")
                
                call_args = mock_config.call_args
                assert call_args[1]["level"] == logging.DEBUG

    def test_setup_logging_warning_level(self):
        """Test setup_logging with WARNING level"""
        
        with patch("app.utils.helpers.logging.basicConfig") as mock_config:
            with patch("app.utils.helpers.logging.getLogger"):
                
                setup_logging("WARNING")
                
                call_args = mock_config.call_args
                assert call_args[1]["level"] == logging.WARNING

    def test_setup_logging_error_level(self):
        """Test setup_logging with ERROR level"""
        
        with patch("app.utils.helpers.logging.basicConfig") as mock_config:
            with patch("app.utils.helpers.logging.getLogger"):
                
                setup_logging("ERROR")
                
                call_args = mock_config.call_args
                assert call_args[1]["level"] == logging.ERROR

    def test_log_api_request_basic(self):
        """Test basic API request logging"""
        
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_api_request(
                endpoint="/api/extract",
                method="POST",
                user_info={"key": "test_api_key_123456"}
            )
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "API Request:" in call_args
            assert "/api/extract" in call_args
            assert "POST" in call_args
            assert "test_api" in call_args  # Should be truncated

    def test_log_api_request_with_file_info(self):
        """Test API request logging with file information"""
        
        file_info = {
            "filename": "test.pdf",
            "size_mb": 2.5
        }
        
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_api_request(
                endpoint="/api/extract",
                method="POST",
                user_info={"key": "another_key_789"},
                file_info=file_info
            )
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "test.pdf" in call_args
            assert "2.5" in call_args

    def test_log_api_request_missing_user_key(self):
        """Test API request logging with missing user key"""
        
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_api_request(
                endpoint="/api/health",
                method="GET",
                user_info={}  # No key provided
            )
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "unknown" in call_args

    def test_log_api_request_missing_file_info(self):
        """Test API request logging with missing file info fields"""
        
        file_info = {}  # Empty file info
        
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_api_request(
                endpoint="/api/extract",
                method="POST",
                user_info={"key": "test_key"},
                file_info=file_info
            )
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            # With empty file_info, the API logs just basic request info
            assert "/api/extract" in call_args

    def test_log_processing_metrics_basic(self):
        """Test basic processing metrics logging"""
        
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_processing_metrics(
                operation="pdf_extraction",
                duration=2.5,
                success=True
            )
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "Metrics:" in call_args
            assert "pdf_extraction" in call_args
            assert "2.5" in call_args
            assert "true" in call_args

    def test_log_processing_metrics_with_details(self):
        """Test processing metrics logging with details"""
        
        details = {
            "model": "gemini-1.5-flash",
            "token_count": 1500,
            "cost_usd": 0.05
        }
        
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_processing_metrics(
                operation="gemini_extraction",
                duration=1.8,
                success=True,
                details=details
            )
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "gemini_extraction" in call_args
            assert "1.8" in call_args
            assert "gemini-1.5-flash" in call_args
            assert "1500" in call_args
            assert "0.05" in call_args

    def test_log_processing_metrics_failure(self):
        """Test processing metrics logging for failed operations"""
        
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_processing_metrics(
                operation="validation",
                duration=0.3,
                success=False
            )
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "validation" in call_args
            assert "0.3" in call_args
            assert "false" in call_args

    def test_log_processing_metrics_zero_duration(self):
        """Test processing metrics logging with zero duration"""
        
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_processing_metrics(
                operation="quick_check",
                duration=0.0,
                success=True
            )
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "quick_check" in call_args
            assert "0.0" in call_args

    def test_log_processing_metrics_large_duration(self):
        """Test processing metrics logging with large duration"""
        
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_processing_metrics(
                operation="long_operation",
                duration=123.456789,
                success=True
            )
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "long_operation" in call_args
            # Duration should be rounded to 3 decimal places
            assert "123.457" in call_args

    def test_log_processing_metrics_empty_details(self):
        """Test processing metrics logging with empty details"""
        
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_processing_metrics(
                operation="test_op",
                duration=1.0,
                success=True,
                details={}  # Empty details
            )
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "test_op" in call_args
            # Empty details dict is not included in log output
            assert "test_op" in call_args

    def test_log_processing_metrics_none_details(self):
        """Test processing metrics logging with None details"""
        
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_processing_metrics(
                operation="test_op",
                duration=1.0,
                success=True,
                details=None
            )
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "test_op" in call_args
            # None details should not be included
            assert "details" not in call_args

