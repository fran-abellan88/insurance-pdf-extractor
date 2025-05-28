"""
Test configuration and fixtures
"""

import asyncio
import json
from io import BytesIO
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def client():
    """Create test client"""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def api_key():
    """Get test API key"""
    settings = get_settings()
    return settings.api_key[0] if settings.api_key else "test-api-key"


@pytest.fixture
def auth_headers(api_key):
    """Create authentication headers"""
    return {"X-API-Key": api_key}


@pytest.fixture
def mock_pdf_content():
    """Mock PDF content for testing"""
    # Create a simple mock PDF content
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"


@pytest.fixture
def sample_extracted_data():
    """Sample extracted data for testing"""
    return {
        "quote_number": "123456",
        "policy_effective_date": "01/01/2024",
        "policy_expiration_date": "01/01/2025",
        "named_insured_name": "Test Company LLC",
        "named_insured_address": "123 Test St, Test City, ST 12345",
        "additional_named_insured_name": "Excluded",
        "additional_named_insured_address": "Excluded",
        "issuing_carrier": "['Test Insurance Company']",
        "commission": "EMPTY VALUE",
        "estimated_premium_amount": "1000",
        "minimum_earned_premium": "EMPTY VALUE",
        "taxes": "50",
        "tria": "Included",
        "waiver_of_subrogation_type": "Excluded",
        "workers_comp_each_accident_limit": "1000000",
        "workers_comp_disease_each_employee": "1000000",
        "workers_comp_disease_policy_limit": "1000000",
        "workers_comp_exclusion_description": "EMPTY VALUE",
    }


@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response"""
    return {
        "extracted_data": {
            "quote_number": "123456",
            "policy_effective_date": "01/01/2024",
            "named_insured_name": "Test Company",
        },
        "processing_time": 2.5,
        "model_used": "gemini-1.5-flash",
        "response_text": "Mock response text",
    }
