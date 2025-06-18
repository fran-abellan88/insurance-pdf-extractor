"""
Tests for PDF processor service
"""

from unittest.mock import Mock, patch

import pytest

from app.core.exceptions import FileProcessingError
from app.services.pdf_processor import PDFProcessor


class TestPDFProcessor:

    @pytest.fixture
    def pdf_processor(self):
        """Create PDF processor instance for testing"""
        with patch("app.services.pdf_processor.get_settings") as mock_settings:
            with patch("app.services.pdf_processor.get_prompt_manager") as mock_prompt_manager:
                mock_settings.return_value.max_file_size_mb = 10
                mock_prompt_manager.return_value.get_prompt.return_value = "test prompt"
                mock_prompt_manager.return_value.get_default_version.return_value = "v1"
                mock_prompt_manager.return_value.get_all_fields.return_value = {"test_field": "value"}
                return PDFProcessor()

    @pytest.fixture
    def valid_pdf_content(self):
        """Create valid PDF content for testing"""
        return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF Content) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000010 00000 n
0000000053 00000 n
0000000107 00000 n
0000000181 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
275
%%EOF"""

    @pytest.fixture
    def mock_gemini_response(self):
        """Mock Gemini service response"""
        return {
            "extracted_data": {
                "quote_number": "TEST123",
                "policy_effective_date": "01/01/2024",
                "named_insured_name": "Test Company",
            },
            "processing_time": 1.5,
            "response_text": "Mock response",
            "usage_metadata": {"prompt_token_count": 1000, "candidates_token_count": 500, "total_token_count": 1500},
        }

    async def test_process_pdf_success(self, pdf_processor, valid_pdf_content, mock_gemini_response):
        """Test successful PDF processing"""

        with patch("app.services.pdf_processor.gemini_service") as mock_gemini:
            with patch("app.services.pdf_processor.validate_extracted_data") as mock_validate:
                # Setup mocks - make extract_from_pdf async
                async def mock_extract(*args, **kwargs):
                    return mock_gemini_response
                mock_gemini.extract_from_pdf = mock_extract

                mock_validation_result = Mock()
                mock_validation_result.is_valid = True
                mock_validation_result.has_warnings = False
                mock_validation_result.data.model_dump.return_value = mock_gemini_response["extracted_data"]
                mock_validation_result.validation_errors = []
                mock_validation_result.warnings = []
                mock_validate.return_value = mock_validation_result

                result = await pdf_processor.process_pdf(
                    pdf_content=valid_pdf_content, filename="test.pdf", document_type="quote"
                )

                assert result["status"] == "success"
                assert result["extracted_data"] == mock_gemini_response["extracted_data"]
                assert result["document_type"] == "quote"
                assert "processing_time" in result
                assert "file_info" in result
                assert result["file_info"]["filename"] == "test.pdf"

    async def test_process_pdf_with_token_usage(self, pdf_processor, valid_pdf_content, mock_gemini_response):
        """Test PDF processing with token usage tracking"""

        with patch("app.services.pdf_processor.gemini_service") as mock_gemini:
            with patch("app.services.pdf_processor.validate_extracted_data") as mock_validate:
                with patch.object(pdf_processor, "_count_tokens") as mock_count_tokens:
                    # Setup mocks - make functions async
                    async def mock_extract(*args, **kwargs):
                        return mock_gemini_response
                    mock_gemini.extract_from_pdf = mock_extract
                    
                    async def mock_count(*args, **kwargs):
                        return {"input_tokens": 1000}
                    mock_count_tokens.side_effect = mock_count

                    mock_validation_result = Mock()
                    mock_validation_result.is_valid = True
                    mock_validation_result.has_warnings = False
                    mock_validation_result.data.model_dump.return_value = mock_gemini_response["extracted_data"]
                    mock_validation_result.validation_errors = []
                    mock_validation_result.warnings = []
                    mock_validate.return_value = mock_validation_result

                    result = await pdf_processor.process_pdf(
                        pdf_content=valid_pdf_content, filename="test.pdf", include_token_usage=True
                    )

                    assert "token_usage" in result
                    assert "metrics" in result
                    assert "token_metrics" in result["metrics"]

    async def test_process_pdf_with_confidence_scores(self, pdf_processor, valid_pdf_content, mock_gemini_response):
        """Test PDF processing with confidence scores"""

        with patch("app.services.pdf_processor.gemini_service") as mock_gemini:
            with patch("app.services.pdf_processor.validate_extracted_data") as mock_validate:
                # Setup mocks - make extract_from_pdf async
                async def mock_extract(*args, **kwargs):
                    return mock_gemini_response
                mock_gemini.extract_from_pdf = mock_extract

                mock_validation_result = Mock()
                mock_validation_result.is_valid = True
                mock_validation_result.has_warnings = False
                mock_validation_result.data.model_dump.return_value = mock_gemini_response["extracted_data"]
                mock_validation_result.validation_errors = []
                mock_validation_result.warnings = []
                mock_validate.return_value = mock_validation_result

                result = await pdf_processor.process_pdf(
                    pdf_content=valid_pdf_content, filename="test.pdf", include_confidence=True
                )

                assert "confidence_scores" in result

    async def test_process_pdf_partial_success(self, pdf_processor, valid_pdf_content, mock_gemini_response):
        """Test PDF processing with validation warnings"""

        with patch("app.services.pdf_processor.gemini_service") as mock_gemini:
            with patch("app.services.pdf_processor.validate_extracted_data") as mock_validate:
                # Setup mocks - make extract_from_pdf async
                async def mock_extract(*args, **kwargs):
                    return mock_gemini_response
                mock_gemini.extract_from_pdf = mock_extract

                mock_validation_result = Mock()
                mock_validation_result.is_valid = False
                mock_validation_result.has_warnings = True
                mock_validation_result.data.model_dump.return_value = mock_gemini_response["extracted_data"]
                mock_validation_result.validation_errors = ["Missing field: test_field"]
                mock_validation_result.warnings = ["Date format warning"]
                mock_validate.return_value = mock_validation_result

                result = await pdf_processor.process_pdf(pdf_content=valid_pdf_content, filename="test.pdf")

                assert result["status"] == "partial_success"
                assert "failed_fields" in result
                assert "errors" in result
                assert "warnings" in result

    async def test_process_pdf_binder_document(self, pdf_processor, valid_pdf_content, mock_gemini_response):
        """Test processing binder document type"""

        with patch("app.services.pdf_processor.gemini_service") as mock_gemini:
            with patch("app.services.pdf_processor.validate_extracted_data") as mock_validate:
                # Setup mocks - make extract_from_pdf async
                async def mock_extract(*args, **kwargs):
                    return mock_gemini_response
                mock_gemini.extract_from_pdf = mock_extract

                mock_validation_result = Mock()
                mock_validation_result.is_valid = True
                mock_validation_result.has_warnings = False
                mock_validation_result.data.model_dump.return_value = {"binder_number": "BIND123"}
                mock_validation_result.validation_errors = []
                mock_validation_result.warnings = []
                mock_validate.return_value = mock_validation_result

                result = await pdf_processor.process_pdf(
                    pdf_content=valid_pdf_content, filename="test.pdf", document_type="binder"
                )

                assert result["document_type"] == "binder"
                mock_validate.assert_called_with(mock_gemini_response["extracted_data"], "binder")

    def test_validate_pdf_success(self, pdf_processor, valid_pdf_content):
        """Test successful PDF validation"""

        # Should not raise exception
        pdf_processor._validate_pdf(valid_pdf_content, "test.pdf")

    def test_validate_pdf_too_large(self, pdf_processor):
        """Test PDF file too large"""

        large_content = b"x" * (11 * 1024 * 1024)  # 11MB

        with pytest.raises(FileProcessingError) as exc_info:
            pdf_processor._validate_pdf(large_content, "large.pdf")

        assert "exceeds maximum" in str(exc_info.value)

    def test_validate_pdf_invalid_content(self, pdf_processor):
        """Test invalid PDF content"""

        invalid_content = b"not a pdf file"

        with pytest.raises(FileProcessingError) as exc_info:
            pdf_processor._validate_pdf(invalid_content, "invalid.pdf")

        assert "Invalid PDF file" in str(exc_info.value)

    def test_validate_pdf_empty_file(self, pdf_processor):
        """Test empty PDF file"""

        empty_pdf = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids []
/Count 0
>>
endobj
trailer
<<
/Size 3
/Root 1 0 R
>>
startxref
85
%%EOF"""

        with pytest.raises(FileProcessingError) as exc_info:
            pdf_processor._validate_pdf(empty_pdf, "empty.pdf")

        assert "contains no pages" in str(exc_info.value)

    async def test_count_tokens_success(self, pdf_processor, valid_pdf_content):
        """Test successful token counting"""

        with patch("app.services.pdf_processor.genai") as mock_genai:
            with patch("tempfile.mkstemp") as mock_tempfile:
                with patch("os.fdopen") as mock_fdopen:
                    with patch("os.path.exists") as mock_exists:
                        # Setup mocks
                        mock_tempfile.return_value = (1, "temp_path")
                        mock_fdopen.return_value.__enter__.return_value.write = Mock()
                        mock_exists.return_value = True

                        mock_file = Mock()
                        mock_file.state.name = "ACTIVE"
                        mock_file.name = "test_file"
                        mock_genai.upload_file.return_value = mock_file
                        mock_genai.get_file.return_value = mock_file

                        mock_model = Mock()
                        mock_token_count = Mock()
                        mock_token_count.total_tokens = 1500
                        mock_model.count_tokens.return_value = mock_token_count
                        mock_genai.GenerativeModel.return_value = mock_model

                        result = await pdf_processor._count_tokens(valid_pdf_content, "test prompt", "gemini-1.5-flash")

                        assert result["input_tokens"] == 1500
                        assert result["prompt_token_count"] == 1500

    async def test_count_tokens_processing_failed(self, pdf_processor, valid_pdf_content):
        """Test token counting with file processing failure"""

        with patch("app.services.pdf_processor.genai") as mock_genai:
            with patch("tempfile.mkstemp") as mock_tempfile:
                # Setup mocks
                mock_tempfile.return_value = (1, "temp_path")

                mock_file = Mock()
                mock_file.state.name = "FAILED"
                mock_genai.upload_file.return_value = mock_file

                with pytest.raises(Exception) as exc_info:
                    await pdf_processor._count_tokens(valid_pdf_content, "test prompt", "gemini-1.5-flash")

                assert "File processing failed" in str(exc_info.value)

    def test_estimate_cost_flash_model(self, pdf_processor):
        """Test cost estimation for flash model"""

        cost = pdf_processor._estimate_cost(1000, 500, "gemini-1.5-flash")

        # Expected: (1000/1000 * 0.000075) + (500/1000 * 0.0003) = 0.000075 + 0.00015 = 0.000225
        assert abs(cost - 0.000225) < 0.000001

    def test_estimate_cost_pro_model(self, pdf_processor):
        """Test cost estimation for pro model"""

        cost = pdf_processor._estimate_cost(1000, 500, "gemini-1.5-pro")

        # Expected: (1000/1000 * 0.00125) + (500/1000 * 0.005) = 0.00125 + 0.0025 = 0.00375
        assert abs(cost - 0.00375) < 0.000001

    def test_estimate_cost_unknown_model(self, pdf_processor):
        """Test cost estimation for unknown model defaults to flash"""

        cost = pdf_processor._estimate_cost(1000, 500, "unknown-model")

        # Should default to flash pricing
        expected_cost = (1000 / 1000 * 0.000075) + (500 / 1000 * 0.0003)
        assert abs(cost - expected_cost) < 0.000001

    def test_get_detailed_cost_breakdown(self, pdf_processor):
        """Test detailed cost breakdown generation"""

        breakdown = pdf_processor._get_detailed_cost_breakdown(1000, 500, "gemini-1.5-flash")

        assert breakdown["model_used"] == "gemini-1.5-flash"
        assert breakdown["input_tokens"] == 1000
        assert breakdown["output_tokens"] == 500
        assert breakdown["total_tokens"] == 1500
        assert "pricing_per_1k_tokens" in breakdown
        assert "input_cost" in breakdown
        assert "output_cost" in breakdown
        assert "total_cost" in breakdown
        assert "cost_breakdown" in breakdown

    def test_extract_failed_fields(self, pdf_processor):
        """Test extraction of failed field names from errors"""

        errors = [
            "Field 'quote_number' validation failed",
            "Invalid value for 'named_insured_name'",
            "Missing required field 'policy_date'",
        ]

        failed_fields = pdf_processor._extract_failed_fields(errors)

        # The implementation extracts field names between quotes
        assert len(failed_fields) >= 2
        assert "quote_number" in failed_fields
        assert "policy_date" in failed_fields

    def test_calculate_confidence_scores(self, pdf_processor):
        """Test confidence score calculation"""

        extracted_data = {
            "quote_number": "123456",
            "named_insured_name": "ACME Corporation",
            "empty_field": "EMPTY VALUE",
            "short_field": "X",
            "policy_effective_date": "01/01/2024",
        }

        response_text = "Quote number is 123456 for ACME Corporation effective 01/01/2024"

        scores = pdf_processor._calculate_confidence_scores(extracted_data, response_text)

        assert scores["empty_field"] == 0.0
        assert scores["quote_number"] > scores["short_field"]
        assert scores["policy_effective_date"] > scores["short_field"]  # Date format bonus
        assert all(0.0 <= score <= 1.0 for score in scores.values())

    def test_get_pdf_info_success(self, pdf_processor, valid_pdf_content):
        """Test PDF info extraction"""

        info = pdf_processor.get_pdf_info(valid_pdf_content)

        assert info["num_pages"] == 1
        assert info["size_bytes"] == len(valid_pdf_content)
        assert info["size_mb"] >= 0  # Small PDFs can round to 0.0
        assert "first_page_preview" in info
        assert "estimated_text_length" in info

    def test_get_pdf_info_with_metadata(self, pdf_processor):
        """Test PDF info extraction with metadata"""

        # Create a PDF with metadata using reportlab or similar
        pdf_with_metadata = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
>>
endobj
4 0 obj
<<
/Title (Test Document)
/Author (Test Author)
/Subject (Test Subject)
>>
endobj
trailer
<<
/Size 5
/Root 1 0 R
/Info 4 0 R
>>
startxref
200
%%EOF"""

        info = pdf_processor.get_pdf_info(pdf_with_metadata)

        assert info["num_pages"] == 1
        assert "size_bytes" in info

    def test_get_pdf_info_invalid_pdf(self, pdf_processor):
        """Test PDF info extraction with invalid PDF"""

        invalid_content = b"not a pdf"

        info = pdf_processor.get_pdf_info(invalid_content)

        assert info["num_pages"] == 0
        assert "error" in info
        assert info["size_bytes"] == len(invalid_content)
