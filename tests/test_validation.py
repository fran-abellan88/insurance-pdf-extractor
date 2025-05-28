"""
Tests for data validation models
"""

import pytest
from pydantic import ValidationError

from app.models.extraction import WorkersCompensationData, validate_extracted_data


class TestWorkersCompensationData:

    def test_valid_data(self, sample_extracted_data):
        """Test validation with valid data"""

        data = WorkersCompensationData(**sample_extracted_data)
        assert data.quote_number == "123456"
        assert data.policy_effective_date == "01/01/2024"

    def test_invalid_date_format(self):
        """Test validation with invalid date format"""

        data = {
            "issuing_carrier": "Test Insurance Company",
            "quote_number": "123456",
            "policy_effective_date": "2024-01-01",  # Wrong format
            "policy_expiration_date": "01/01/2025",
            "named_insured_name": "Test Company",
            "named_insured_address": "123 Test St",
        }

        # Should not raise exception due to date normalization
        result = WorkersCompensationData(**data)
        assert result.policy_effective_date == "01/01/2024"

    def test_missing_required_fields(self):
        """Test validation with missing required fields"""

        with pytest.raises(ValidationError):
            WorkersCompensationData(quote_number="")  # Empty required field
