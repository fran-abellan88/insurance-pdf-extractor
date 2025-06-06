"""
Tests for storage service
"""

import json
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.services.storage import LocalStorageService


class TestLocalStorageService:

    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path for testing"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            yield tmp.name
        Path(tmp.name).unlink(missing_ok=True)

    @pytest.fixture
    def storage_service(self, temp_db_path):
        """Create storage service instance with temporary database"""
        return LocalStorageService(temp_db_path)

    @pytest.fixture
    def sample_extraction_data(self):
        """Sample extraction data for testing"""
        return {
            "filename": "test.pdf",
            "file_size": 1024,
            "status": "success",
            "model_used": "gemini-1.5-flash",
            "prompt_version": "v1",
            "processing_time": 2.5,
            "extracted_data": {
                "quote_number": "TEST123",
                "policy_effective_date": "01/01/2024",
                "named_insured_name": "Test Company",
            },
            "confidence_scores": {"quote_number": 0.95, "policy_effective_date": 0.90, "named_insured_name": 0.85},
            "failed_fields": [],
            "warnings": [],
            "user_key": "test_user_123",
            "document_type": "quote",
        }

    @pytest.fixture
    def sample_token_usage(self):
        """Sample token usage data for testing"""
        return {
            "prompt_token_count": 1000,
            "candidates_token_count": 500,
            "total_token_count": 1500,
            "estimated_cost": 0.002,
            "cost_breakdown": {
                "input_cost": 0.001,
                "output_cost": 0.001,
                "total_cost": 0.002,
                "pricing_per_1k_tokens": {"input": 0.075, "output": 0.30},
            },
        }

    def test_init_creates_database(self, temp_db_path):
        """Test that initialization creates database and tables"""

        # Remove file if it exists from fixture cleanup timing
        Path(temp_db_path).unlink(missing_ok=True)
        
        # Database should not exist initially
        assert not Path(temp_db_path).exists()

        storage = LocalStorageService(temp_db_path)

        # Database should be created
        assert Path(temp_db_path).exists()

        # Check that tables were created
        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.cursor()

            # Check extractions table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='extractions'")
            assert cursor.fetchone() is not None

            # Check token_usage table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='token_usage'")
            assert cursor.fetchone() is not None

            # Check extraction_fields table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='extraction_fields'")
            assert cursor.fetchone() is not None

    def test_store_extraction_basic(self, storage_service, sample_extraction_data):
        """Test basic extraction storage"""

        extraction_id = storage_service.store_extraction(**sample_extraction_data)

        assert extraction_id is not None
        assert isinstance(extraction_id, int)
        assert extraction_id > 0

    def test_store_extraction_with_token_usage(self, storage_service, sample_extraction_data, sample_token_usage):
        """Test extraction storage with token usage data"""

        sample_extraction_data["token_usage"] = sample_token_usage

        extraction_id = storage_service.store_extraction(**sample_extraction_data)

        # Verify extraction was stored
        extraction = storage_service.get_extraction(extraction_id)
        assert extraction is not None
        assert extraction["input_tokens"] == 1000
        assert extraction["output_tokens"] == 500
        assert extraction["estimated_cost"] == 0.002

    def test_store_extraction_with_failed_fields(self, storage_service, sample_extraction_data):
        """Test storing extraction with failed fields"""

        sample_extraction_data["failed_fields"] = ["field1", "field2"]
        sample_extraction_data["status"] = "partial_success"

        extraction_id = storage_service.store_extraction(**sample_extraction_data)

        extraction = storage_service.get_extraction(extraction_id)
        assert extraction["status"] == "partial_success"
        # failed_fields should already be a list after _row_to_dict processing
        assert extraction["failed_fields"] == ["field1", "field2"]

    def test_store_extraction_with_warnings(self, storage_service, sample_extraction_data):
        """Test storing extraction with warnings"""

        sample_extraction_data["warnings"] = ["Warning 1", "Warning 2"]

        extraction_id = storage_service.store_extraction(**sample_extraction_data)

        extraction = storage_service.get_extraction(extraction_id)
        # warnings should already be a list after _row_to_dict processing
        assert extraction["warnings"] == ["Warning 1", "Warning 2"]

    def test_store_extraction_binder_document(self, storage_service, sample_extraction_data):
        """Test storing binder document extraction"""

        sample_extraction_data["document_type"] = "binder"
        sample_extraction_data["extracted_data"] = {
            "binder_number": "BIND123",
            "effective_date": "01/01/2024",
            "named_insured": "Test Company",
        }

        extraction_id = storage_service.store_extraction(**sample_extraction_data)

        extraction = storage_service.get_extraction(extraction_id)
        assert extraction["document_type"] == "binder"

    def test_store_extraction_error_handling(self, storage_service, sample_extraction_data):
        """Test extraction storage error handling"""

        # Force an error by mocking the connection to raise an exception
        with patch.object(storage_service, '_get_connection') as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Database error")

            with pytest.raises(Exception):
                storage_service.store_extraction(**sample_extraction_data)

    def test_get_extraction_success(self, storage_service, sample_extraction_data):
        """Test successful extraction retrieval"""

        extraction_id = storage_service.store_extraction(**sample_extraction_data)

        extraction = storage_service.get_extraction(extraction_id)

        assert extraction is not None
        assert extraction["id"] == extraction_id
        assert extraction["filename"] == "test.pdf"
        assert extraction["status"] == "success"
        assert extraction["document_type"] == "quote"

    def test_get_extraction_not_found(self, storage_service):
        """Test extraction retrieval for non-existent ID"""

        extraction = storage_service.get_extraction(99999)

        assert extraction is None

    def test_get_extraction_with_token_usage(self, storage_service, sample_extraction_data, sample_token_usage):
        """Test extraction retrieval with token usage data"""

        sample_extraction_data["token_usage"] = sample_token_usage
        extraction_id = storage_service.store_extraction(**sample_extraction_data)

        extraction = storage_service.get_extraction_with_token_usage(extraction_id)

        assert extraction is not None
        assert "detailed_token_usage" in extraction
        assert extraction["detailed_token_usage"]["prompt_token_count"] == 1000

    def test_get_recent_extractions(self, storage_service, sample_extraction_data):
        """Test getting recent extractions"""

        # Store multiple extractions
        for i in range(3):
            data = sample_extraction_data.copy()
            data["filename"] = f"test_{i}.pdf"
            storage_service.store_extraction(**data)

        recent = storage_service.get_recent_extractions(limit=2)

        assert len(recent) == 2
        # Should be ordered by created_at DESC
        assert recent[0]["filename"] == "test_2.pdf"
        assert recent[1]["filename"] == "test_1.pdf"

    def test_search_extractions_by_filename(self, storage_service, sample_extraction_data):
        """Test searching extractions by filename pattern"""

        # Store extractions with different filenames
        filenames = ["test_quote.pdf", "test_binder.pdf", "other.pdf"]
        for filename in filenames:
            data = sample_extraction_data.copy()
            data["filename"] = filename
            storage_service.store_extraction(**data)

        results = storage_service.search_extractions(filename_pattern="test_")

        assert len(results) == 2
        assert all("test_" in r["filename"] for r in results)

    def test_search_extractions_by_status(self, storage_service, sample_extraction_data):
        """Test searching extractions by status"""

        # Store extractions with different statuses
        statuses = ["success", "partial_success", "failed"]
        for status in statuses:
            data = sample_extraction_data.copy()
            data["status"] = status
            data["filename"] = f"test_{status}.pdf"
            storage_service.store_extraction(**data)

        results = storage_service.search_extractions(status="success")

        assert len(results) == 1
        assert results[0]["status"] == "success"

    def test_search_extractions_by_model(self, storage_service, sample_extraction_data):
        """Test searching extractions by model"""

        # Store extractions with different models
        models = ["gemini-1.5-flash", "gemini-1.5-pro"]
        for model in models:
            data = sample_extraction_data.copy()
            data["model_used"] = model
            data["filename"] = f"test_{model}.pdf"
            storage_service.store_extraction(**data)

        results = storage_service.search_extractions(model_used="gemini-1.5-pro")

        assert len(results) == 1
        assert results[0]["model_used"] == "gemini-1.5-pro"

    def test_search_extractions_by_document_type(self, storage_service, sample_extraction_data):
        """Test searching extractions by document type"""

        # Store extractions with different document types
        doc_types = ["quote", "binder"]
        for doc_type in doc_types:
            data = sample_extraction_data.copy()
            data["document_type"] = doc_type
            data["filename"] = f"test_{doc_type}.pdf"
            storage_service.store_extraction(**data)

        results = storage_service.search_extractions(document_type="binder")

        assert len(results) == 1
        assert results[0]["document_type"] == "binder"

    def test_search_extractions_by_date_range(self, storage_service, sample_extraction_data):
        """Test searching extractions by date range"""

        # Store extraction
        extraction_id = storage_service.store_extraction(**sample_extraction_data)

        # Search with date range that includes today
        start_date = datetime.now() - timedelta(days=1)
        end_date = datetime.now() + timedelta(days=1)

        results = storage_service.search_extractions(start_date=start_date, end_date=end_date)

        assert len(results) == 1
        assert results[0]["id"] == extraction_id

    def test_search_extractions_no_results(self, storage_service, sample_extraction_data):
        """Test searching extractions with no matching results"""

        storage_service.store_extraction(**sample_extraction_data)

        results = storage_service.search_extractions(filename_pattern="nonexistent")

        assert len(results) == 0

    def test_get_token_usage_statistics(self, storage_service, sample_extraction_data, sample_token_usage):
        """Test getting token usage statistics"""

        # Store multiple extractions with token usage
        for i in range(3):
            data = sample_extraction_data.copy()
            data["filename"] = f"test_{i}.pdf"
            data["token_usage"] = sample_token_usage.copy()
            data["token_usage"]["estimated_cost"] = 0.001 * (i + 1)  # Different costs
            storage_service.store_extraction(**data)

        stats = storage_service.get_token_usage_statistics()

        assert "overall_statistics" in stats
        assert "statistics_by_model" in stats
        assert "daily_cost_trends" in stats
        assert "most_expensive_extractions" in stats

        overall = stats["overall_statistics"]
        assert overall["total_extractions_with_tokens"] == 3
        assert overall["total_estimated_cost"] == 0.006  # 0.001 + 0.002 + 0.003

    def test_get_document_type_statistics(self, storage_service, sample_extraction_data):
        """Test getting document type statistics"""

        # Store extractions with different document types and statuses
        configs = [
            {"document_type": "quote", "status": "success"},
            {"document_type": "quote", "status": "partial_success"},
            {"document_type": "binder", "status": "success"},
            {"document_type": "binder", "status": "failed"},
        ]

        for i, config in enumerate(configs):
            data = sample_extraction_data.copy()
            data.update(config)
            data["filename"] = f"test_{i}.pdf"
            storage_service.store_extraction(**data)

        stats = storage_service.get_document_type_statistics()

        assert "document_type_distribution" in stats
        assert "daily_trends_by_type" in stats
        assert "model_usage_by_type" in stats

        # Check distribution
        distribution = stats["document_type_distribution"]
        quote_stats = next(d for d in distribution if d["document_type"] == "quote")
        assert quote_stats["total_extractions"] == 2
        assert quote_stats["successful_extractions"] == 1
        assert quote_stats["partial_extractions"] == 1

    def test_get_field_statistics(self, storage_service, sample_extraction_data):
        """Test getting field statistics"""

        # Store multiple extractions
        for i in range(2):
            data = sample_extraction_data.copy()
            data["filename"] = f"test_{i}.pdf"
            storage_service.store_extraction(**data)

        stats = storage_service.get_field_statistics()

        assert "total_extractions" in stats
        assert "status_breakdown" in stats
        assert "field_success_rates" in stats
        assert "token_usage_summary" in stats

        assert stats["total_extractions"] == 2

    def test_cleanup_old_records(self, storage_service, sample_extraction_data):
        """Test cleaning up old extraction records"""

        # Store an extraction
        extraction_id = storage_service.store_extraction(**sample_extraction_data)

        # Verify it exists
        assert storage_service.get_extraction(extraction_id) is not None

        # Clean up records older than 0 days (should delete everything)
        deleted_count = storage_service.cleanup_old_records(days_to_keep=0)

        assert deleted_count == 1
        assert storage_service.get_extraction(extraction_id) is None

    def test_cleanup_old_records_preserve_recent(self, storage_service, sample_extraction_data):
        """Test that cleanup preserves recent records"""

        # Store an extraction
        extraction_id = storage_service.store_extraction(**sample_extraction_data)

        # Clean up records older than 30 days (should keep recent ones)
        deleted_count = storage_service.cleanup_old_records(days_to_keep=30)

        assert deleted_count == 0
        assert storage_service.get_extraction(extraction_id) is not None

    def test_cleanup_old_records_error_handling(self, storage_service):
        """Test cleanup error handling"""

        with patch.object(storage_service, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Database error")

            deleted_count = storage_service.cleanup_old_records()

            assert deleted_count == 0

    def test_row_to_dict_json_parsing(self, storage_service):
        """Test row to dict conversion with JSON field parsing"""

        # Create a mock row with JSON fields
        mock_row = {
            "id": 1,
            "filename": "test.pdf",
            "extracted_data": '{"quote_number": "123"}',
            "confidence_scores": '{"quote_number": 0.95}',
            "failed_fields": '["field1"]',
            "warnings": '["warning1"]',
            "cost_breakdown": '{"total": 0.002}',
        }

        result = storage_service._row_to_dict(mock_row)

        assert result["extracted_data"] == {"quote_number": "123"}
        assert result["confidence_scores"] == {"quote_number": 0.95}
        assert result["failed_fields"] == ["field1"]
        assert result["warnings"] == ["warning1"]
        assert result["cost_breakdown"] == {"total": 0.002}

    def test_row_to_dict_invalid_json(self, storage_service):
        """Test row to dict conversion with invalid JSON"""

        mock_row = {"id": 1, "filename": "test.pdf", "extracted_data": "invalid json", "confidence_scores": None}

        result = storage_service._row_to_dict(mock_row)

        assert result["extracted_data"] is None
        assert result["confidence_scores"] is None

    def test_add_columns_if_not_exist(self, temp_db_path):
        """Test adding new columns to existing table"""

        # Create database with essential schema (including columns that indexes reference)
        with sqlite3.connect(temp_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE extractions (
                    id INTEGER PRIMARY KEY,
                    filename TEXT NOT NULL,
                    status TEXT NOT NULL,
                    model_used TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            # Also create the other required tables to avoid initialization errors
            conn.execute(
                """
                CREATE TABLE token_usage (
                    id INTEGER PRIMARY KEY,
                    extraction_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE extraction_fields (
                    id INTEGER PRIMARY KEY,
                    extraction_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

        # Initialize storage service (should add missing columns)
        storage = LocalStorageService(temp_db_path)

        # Check that new columns were added
        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(extractions)")
            columns = [column[1] for column in cursor.fetchall()]

            assert "document_type" in columns
            assert "input_tokens" in columns
            assert "estimated_cost" in columns

    def test_get_extraction_error_handling(self, storage_service):
        """Test extraction retrieval error handling"""

        with patch.object(storage_service, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Database error")

            result = storage_service.get_extraction(1)

            assert result is None

    def test_get_recent_extractions_error_handling(self, storage_service):
        """Test recent extractions retrieval error handling"""

        with patch.object(storage_service, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Database error")

            result = storage_service.get_recent_extractions()

            assert result == []

    def test_search_extractions_error_handling(self, storage_service):
        """Test search extractions error handling"""

        with patch.object(storage_service, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Database error")

            result = storage_service.search_extractions()

            assert result == []

    def test_statistics_methods_error_handling(self, storage_service):
        """Test statistics methods error handling"""

        with patch.object(storage_service, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Database error")

            token_stats = storage_service.get_token_usage_statistics()
            doc_stats = storage_service.get_document_type_statistics()
            field_stats = storage_service.get_field_statistics()

            assert token_stats == {}
            assert doc_stats == {}
            assert field_stats == {}


def test_global_storage_service_instance():
    """Test that global storage service instance is created"""

    from app.services.storage import storage_service

    assert storage_service is not None
    assert isinstance(storage_service, LocalStorageService)
