"""
Test configuration and fixtures
"""

from unittest.mock import Mock

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
    # Create a more complete mock PDF content
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
