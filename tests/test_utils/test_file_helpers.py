"""
Tests for file helper utilities
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.utils.file_helpers import (
    detect_file_type,
    extract_file_extension,
    get_file_size_mb,
    validate_file_size,
)


class TestFileHelpers:

    @pytest.fixture
    def sample_pdf_content(self):
        """Create sample PDF content for testing"""
        return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
trailer
<<
/Root 1 0 R
>>
startxref
85
%%EOF"""

    @pytest.fixture
    def sample_text_content(self):
        """Create sample text content for testing"""
        return b"This is a sample text file content"

    def test_extract_file_extension_with_extension(self):
        """Test extracting file extension from filename with extension"""

        assert extract_file_extension("document.pdf") == ".pdf"
        assert extract_file_extension("image.jpg") == ".jpg"
        assert extract_file_extension("data.csv") == ".csv"

    def test_extract_file_extension_uppercase(self):
        """Test extracting file extension with uppercase"""

        assert extract_file_extension("DOCUMENT.PDF") == ".pdf"
        assert extract_file_extension("Image.JPG") == ".jpg"

    def test_extract_file_extension_without_extension(self):
        """Test extracting file extension from filename without extension"""

        assert extract_file_extension("document") == ""
        assert extract_file_extension("README") == ""

    def test_extract_file_extension_multiple_dots(self):
        """Test extracting file extension from filename with multiple dots"""

        assert extract_file_extension("archive.tar.gz") == ".gz"
        assert extract_file_extension("config.yaml.bak") == ".bak"

    def test_extract_file_extension_hidden_file(self):
        """Test extracting file extension from hidden file"""

        assert extract_file_extension(".gitignore") == ""
        assert extract_file_extension(".env.local") == ".local"

    def test_extract_file_extension_empty_filename(self):
        """Test extracting file extension from empty filename"""

        assert extract_file_extension("") == ""
        assert extract_file_extension(None) == ""

    def test_get_file_size_mb_small_file(self, sample_text_content):
        """Test getting file size in MB for small file"""

        size_mb = get_file_size_mb(sample_text_content)

        assert size_mb > 0
        assert size_mb < 0.001  # Should be very small for sample text

    def test_get_file_size_mb_large_file(self):
        """Test getting file size in MB for larger file"""

        # Create 1MB of data
        large_content = b"x" * (1024 * 1024)
        size_mb = get_file_size_mb(large_content)

        assert abs(size_mb - 1.0) < 0.001  # Should be approximately 1MB

    def test_get_file_size_mb_empty_file(self):
        """Test getting file size in MB for empty file"""

        size_mb = get_file_size_mb(b"")

        assert size_mb == 0.0

    def test_validate_file_size_within_limit(self, sample_text_content):
        """Test file size validation within limit"""

        is_valid = validate_file_size(sample_text_content, max_size_mb=1)

        assert is_valid is True

    def test_validate_file_size_exceeds_limit(self):
        """Test file size validation exceeding limit"""

        # Create 2MB of data
        large_content = b"x" * (2 * 1024 * 1024)
        is_valid = validate_file_size(large_content, max_size_mb=1)

        assert is_valid is False

    def test_validate_file_size_exact_limit(self):
        """Test file size validation at exact limit"""

        # Create exactly 1MB of data
        exact_content = b"x" * (1024 * 1024)
        is_valid = validate_file_size(exact_content, max_size_mb=1)

        assert is_valid is True

    def test_validate_file_size_empty_file(self):
        """Test file size validation for empty file"""

        is_valid = validate_file_size(b"", max_size_mb=1)

        assert is_valid is True

    def test_detect_file_type_pdf_with_magic(self, sample_pdf_content):
        """Test detecting PDF file type with magic library available"""

        # Mock the magic module to be available
        mock_magic = Mock()
        mock_magic.from_buffer.return_value = "application/pdf"
        
        with patch("app.utils.file_helpers.magic", mock_magic):
            mime_type, is_valid_pdf = detect_file_type(sample_pdf_content, "test.pdf")

            assert mime_type == "application/pdf"
            assert is_valid_pdf is True

    def test_detect_file_type_pdf_fallback_mimetypes(self, sample_pdf_content):
        """Test detecting PDF file type falling back to mimetypes"""

        # Mock magic to be None (not available)
        with patch("app.utils.file_helpers.magic", None):
            mime_type, is_valid_pdf = detect_file_type(sample_pdf_content, "test.pdf")

            assert mime_type == "application/pdf"  # From mimetypes
            assert is_valid_pdf is True  # From content check

    def test_detect_file_type_text_file(self, sample_text_content):
        """Test detecting text file type"""

        # Mock the magic module to be available
        mock_magic = Mock()
        mock_magic.from_buffer.return_value = "text/plain"
        
        with patch("app.utils.file_helpers.magic", mock_magic):
            mime_type, is_valid_pdf = detect_file_type(sample_text_content, "test.txt")

            assert mime_type == "text/plain"
            assert is_valid_pdf is False

    def test_detect_file_type_invalid_pdf_content(self):
        """Test detecting file type with invalid PDF content but .pdf extension"""

        invalid_pdf = b"This is not a PDF file"

        # Mock the magic module to be available
        mock_magic = Mock()
        mock_magic.from_buffer.return_value = "text/plain"
        
        with patch("app.utils.file_helpers.magic", mock_magic):
            mime_type, is_valid_pdf = detect_file_type(invalid_pdf, "fake.pdf")

            assert mime_type == "text/plain"
            assert is_valid_pdf is False  # Content doesn't start with %PDF-

    def test_detect_file_type_unknown_extension(self, sample_text_content):
        """Test detecting file type with unknown extension"""

        # Mock magic to be None (not available)
        with patch("app.utils.file_helpers.magic", None):
            mime_type, is_valid_pdf = detect_file_type(sample_text_content, "test.unknown")

            assert mime_type == "application/octet-stream"  # Default fallback
            assert is_valid_pdf is False

    def test_detect_file_type_error_handling(self, sample_text_content):
        """Test detecting file type with error handling"""

        # Mock the magic module to throw an exception
        mock_magic = Mock()
        mock_magic.from_buffer.side_effect = Exception("Unexpected error")
        
        with patch("app.utils.file_helpers.magic", mock_magic):
            mime_type, is_valid_pdf = detect_file_type(sample_text_content, "test.txt")

            assert mime_type == "application/octet-stream"  # Error fallback
            assert is_valid_pdf is False

    def test_detect_file_type_pdf_by_content_only(self, sample_pdf_content):
        """Test detecting PDF by content when filename suggests PDF"""

        # Mock the magic module to return wrong type
        mock_magic = Mock()
        mock_magic.from_buffer.return_value = "text/plain"  # Wrong MIME type
        
        with patch("app.utils.file_helpers.magic", mock_magic):
            # Use .pdf extension so content check happens
            mime_type, is_valid_pdf = detect_file_type(sample_pdf_content, "test.pdf")

            assert mime_type == "text/plain"
            assert is_valid_pdf is True  # Content check should pass because extension is .pdf

    def test_detect_file_type_magic_import_error_with_mimetypes(self, sample_pdf_content):
        """Test magic import error with successful mimetypes fallback"""

        # Mock magic to be None (not available)
        with patch("app.utils.file_helpers.magic", None):
            mime_type, is_valid_pdf = detect_file_type(sample_pdf_content, "document.pdf")

            assert mime_type == "application/pdf"  # From mimetypes
            assert is_valid_pdf is True  # From content validation