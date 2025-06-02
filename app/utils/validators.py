"""
Data validation utilities
"""

import logging
import re
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


def clean_currency_string(value: str) -> Optional[float]:
    """
    Clean and parse currency string to float

    Args:
        value: Currency string (e.g., "$1,234.56", "1234.56", "1,234")

    Returns:
        Float value or None if parsing fails
    """
    if not value or value.upper() == "EMPTY VALUE":
        return None

    try:
        # Remove currency symbols and separators
        cleaned = re.sub(r"[$,\s]", "", str(value))
        return float(cleaned)
    except (ValueError, TypeError):
        logger.warning(f"Failed to parse currency value: {value}")
        return None


def validate_date_format(date_str: str) -> bool:
    """
    Validate if date string is in MM/DD/YYYY format

    Args:
        date_str: Date string to validate

    Returns:
        True if valid format, False otherwise
    """
    if not date_str or date_str.upper() == "EMPTY VALUE":
        return True  # Empty values are allowed

    pattern = r"^\d{2}/\d{2}/\d{4}$"
    return bool(re.match(pattern, date_str))


def normalize_date(date_str: str) -> str:
    """
    Normalize various date formats to MM/DD/YYYY

    Args:
        date_str: Date string in various formats

    Returns:
        Normalized date string in MM/DD/YYYY format
    """
    if not date_str or date_str.upper() == "EMPTY VALUE":
        return date_str

    # Remove extra whitespace
    date_str = date_str.strip()

    # Try to parse various formats
    formats_to_try = [
        "%m/%d/%Y",  # MM/DD/YYYY
        "%m-%d-%Y",  # MM-DD-YYYY
        "%Y-%m-%d",  # YYYY-MM-DD
        "%d/%m/%Y",  # DD/MM/YYYY
        "%B %d, %Y",  # Month DD, YYYY
        "%b %d, %Y",  # Mon DD, YYYY
        "%m/%d/%y",  # MM/DD/YY
        "%Y%m%d",  # YYYYMMDD
    ]

    for fmt in formats_to_try:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%m/%d/%Y")
        except ValueError:
            continue

    # If no format matches, return original
    logger.warning(f"Could not normalize date format: {date_str}")
    return date_str


def clean_text_field(value: str) -> str:
    """
    Clean text field by removing unnecessary characters and formatting

    Args:
        value: Text value to clean

    Returns:
        Cleaned text value
    """
    if not value or value.upper() == "EMPTY VALUE":
        return value

    # Remove extra whitespace and line breaks
    cleaned = re.sub(r"\s+", " ", str(value).strip())

    # Remove common PDF artifacts
    cleaned = re.sub(r"[·•]", "", cleaned)  # Remove bullet points
    cleaned = re.sub(r"\s+", " ", cleaned)  # Normalize whitespace again

    return cleaned.strip()


def validate_quote_number(quote_number: str) -> bool:
    """
    Validate quote number format

    Args:
        quote_number: Quote number to validate

    Returns:
        True if valid, False otherwise
    """
    if not quote_number or len(quote_number.strip()) == 0:
        return False

    # Quote number should contain alphanumeric characters
    # and common separators (-, _, etc.)
    pattern = r"^[A-Za-z0-9\-_\(\)\s]+$"
    return bool(re.match(pattern, quote_number.strip()))


def normalize_boolean_field(value: str) -> str:
    """
    Normalize boolean-like fields to standard format

    Args:
        value: Boolean-like value (Yes/No, True/False, Included/Excluded, etc.)

    Returns:
        Normalized value (Included/Excluded)
    """
    if not value or value.upper() == "EMPTY VALUE":
        return value

    value_lower = str(value).lower().strip()

    # Map various boolean representations
    included_values = ["yes", "true", "included", "include", "y", "1", "on"]
    excluded_values = ["no", "false", "excluded", "exclude", "n", "0", "off"]

    if value_lower in included_values:
        return "Included"
    elif value_lower in excluded_values:
        return "Excluded"
    else:
        # Return original value if no mapping found
        return value


def extract_state_codes(text: str) -> List[str]:
    """
    Extract US state codes from text

    Args:
        text: Text to search for state codes

    Returns:
        List of found state codes
    """
    if not text:
        return []

    # US state codes pattern
    state_pattern = r"\b[A-Z]{2}\b"
    matches = re.findall(state_pattern, text.upper())

    # Filter to only valid US state codes
    valid_states = {
        "AL",
        "AK",
        "AZ",
        "AR",
        "CA",
        "CO",
        "CT",
        "DE",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NV",
        "NH",
        "NJ",
        "NM",
        "NY",
        "NC",
        "ND",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VT",
        "VA",
        "WA",
        "WV",
        "WI",
        "WY",
        "DC",  # District of Columbia
    }

    return [state for state in matches if state in valid_states]


def validate_currency_amount(amount: str) -> bool:
    """
    Validate if string represents a valid currency amount

    Args:
        amount: Amount string to validate

    Returns:
        True if valid currency format, False otherwise
    """
    if not amount or amount.upper() == "EMPTY VALUE":
        return True  # Empty values are allowed

    try:
        # Try to clean and parse as currency
        cleaned_amount = clean_currency_string(amount)
        return cleaned_amount is not None and cleaned_amount >= 0
    except Exception as e:
        print(e)
        return False


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage/logging

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    if not filename:
        return "unknown_file"

    # Remove or replace problematic characters
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", filename)
    sanitized = re.sub(r"\s+", "_", sanitized)

    # Limit length
    if len(sanitized) > 100:
        name, ext = sanitized.rsplit(".", 1) if "." in sanitized else (sanitized, "")
        sanitized = name[:90] + ("." + ext if ext else "")

    return sanitized


def format_processing_time(seconds: float) -> str:
    """
    Format processing time in human-readable format

    Args:
        seconds: Processing time in seconds

    Returns:
        Formatted time string
    """
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.1f}s"
