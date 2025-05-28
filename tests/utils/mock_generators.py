"""
Utility to create mock PDF files for testing
"""

import io

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def create_mock_insurance_pdf() -> bytes:
    """Create a mock insurance PDF for testing"""

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)

    # Add mock insurance quote content
    content = [
        "WORKERS COMPENSATION INSURANCE QUOTE",
        "",
        "Quote Number: WC-TEST-123456",
        "Policy Effective Date: 01/01/2024",
        "Policy Expiration Date: 01/01/2025",
        "",
        "Named Insured: Test Company LLC",
        "Address: 123 Test Street, Test City, ST 12345",
        "",
        "Issuing Carrier: Test Insurance Company",
        "Estimated Premium: $1,000.00",
        "Taxes: $50.00",
        "",
        "Coverage Limits:",
        "Each Accident: $1,000,000",
        "Disease - Each Employee: $1,000,000",
        "Disease - Policy Limit: $1,000,000",
        "",
        "TRIA Coverage: Included",
        "Waiver of Subrogation: Excluded",
    ]

    y_position = 750
    for line in content:
        p.drawString(100, y_position, line)
        y_position -= 20

    p.save()
    buffer.seek(0)
    return buffer.getvalue()


if __name__ == "__main__":
    # Create and save mock PDF
    pdf_content = create_mock_insurance_pdf()
    with open("tests/mock_data/sample_insurance_quote.pdf", "wb") as f:
        f.write(pdf_content)
    print("Mock PDF created successfully")
