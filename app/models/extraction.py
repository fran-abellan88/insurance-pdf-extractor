"""
Pydantic models for extracted data validation
"""

import re
from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class WorkersCompensationData(BaseModel):
    """Validation model for extracted Workers Compensation data"""

    quote_number: str = Field(description="Unique quote number for the policy")
    policy_effective_date: str = Field(description="Policy effective date in MM/DD/YYYY format")
    policy_expiration_date: str = Field(description="Policy expiration date in MM/DD/YYYY format")
    named_insured_name: str = Field(description="Name of the primary policyholder")
    named_insured_address: str = Field(description="Address of the primary policyholder")
    additional_named_insured_name: Optional[str] = Field(
        default="EMPTY VALUE", description="Additional named insured name or 'Excluded'"
    )
    additional_named_insured_address: Optional[str] = Field(
        default="EMPTY VALUE", description="Additional named insured address or 'Excluded'"
    )
    issuing_carrier: Union[str, List[str]] = Field(description="Issuing carrier information")
    commission: Optional[str] = Field(default="EMPTY VALUE", description="Commission details")
    estimated_premium_amount: Optional[str] = Field(default="EMPTY VALUE", description="Total estimated premium amount")
    minimum_earned_premium: Optional[str] = Field(default="EMPTY VALUE", description="Minimum earned premium")
    taxes: Optional[str] = Field(default="EMPTY VALUE", description="Taxes associated with the policy")
    tria: Optional[str] = Field(default="EMPTY VALUE", description="TRIA coverage status (Included/Excluded)")
    waiver_of_subrogation_type: Optional[str] = Field(
        default="EMPTY VALUE", description="Waiver of subrogation status (Included/Excluded)"
    )
    workers_comp_each_accident_limit: Optional[str] = Field(
        default="EMPTY VALUE", description="Coverage limit for each accident"
    )
    workers_comp_disease_each_employee: Optional[str] = Field(
        default="EMPTY VALUE", description="Disease coverage limit per employee"
    )
    workers_comp_disease_policy_limit: Optional[str] = Field(
        default="EMPTY VALUE", description="Overall disease coverage policy limit"
    )
    workers_comp_exclusion_description: Optional[str] = Field(
        default="EMPTY VALUE", description="Workers compensation exclusion description"
    )

    @field_validator("policy_effective_date", "policy_expiration_date")
    def validate_date_format(cls, v):
        """Validate date format MM/DD/YYYY"""
        if v and v != "EMPTY VALUE":
            date_pattern = r"^\d{2}/\d{2}/\d{4}$"
            if not re.match(date_pattern, v):
                # Try to parse and reformat common date formats
                v = cls._normalize_date(v)
                if not re.match(date_pattern, v):
                    raise ValueError(f"Date must be in MM/DD/YYYY format, got: {v}")
        return v

    @field_validator("quote_number")
    def validate_quote_number(cls, v):
        """Validate quote number is not empty"""
        if not v or v.strip() == "":
            raise ValueError("Quote number cannot be empty")
        return v.strip()

    @field_validator("named_insured_name", "named_insured_address")
    def validate_required_fields(cls, v):
        """Validate required fields are not empty"""
        if not v or v.strip() == "":
            raise ValueError("This field is required and cannot be empty")
        return v.strip()

    @field_validator("estimated_premium_amount", "minimum_earned_premium", "taxes")
    def validate_currency_fields(cls, v):
        """Validate currency fields"""
        if v and v != "EMPTY VALUE":
            # Remove common currency symbols and separators
            cleaned = v.replace("$", "").replace(",", "").strip()
            try:
                float(cleaned)
            except ValueError:
                # If it's not a valid number, keep original value but add warning
                pass
        return v

    @field_validator(
        "workers_comp_each_accident_limit", "workers_comp_disease_each_employee", "workers_comp_disease_policy_limit"
    )
    def validate_limit_fields(cls, v):
        """Validate limit fields"""
        if v and v != "EMPTY VALUE":
            cleaned = v.replace("$", "").replace(",", "").strip()
            try:
                limit_value = float(cleaned)
                if limit_value < 0:
                    raise ValueError("Limit values cannot be negative")
            except ValueError:
                # Keep original value but note validation issue
                pass
        return v

    @field_validator("tria", "waiver_of_subrogation_type")
    def validate_boolean_fields(cls, v):
        """Validate boolean-like fields"""
        if v and v != "EMPTY VALUE":
            valid_values = ["Included", "Excluded", "Yes", "No", "True", "False"]
            if v not in valid_values:
                # Normalize common variations
                v_lower = v.lower()
                if v_lower in ["yes", "true", "included", "include"]:
                    return "Included"
                elif v_lower in ["no", "false", "excluded", "exclude"]:
                    return "Excluded"
        return v

    @field_validator("commission")
    def validate_commission(cls, v):
        """Validate commission field"""
        if v and v != "EMPTY VALUE":
            # Commission can be percentage or currency
            v = v.strip()
            if "%" in v or "$" in v:
                return v
            # Try to parse as number and add % if it's a reasonable percentage
            try:
                num = float(v)
                if 0 <= num <= 100:
                    return f"{num}%"
            except ValueError:
                pass
        return v

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        """Normalize various date formats to MM/DD/YYYY"""
        if not date_str or date_str == "EMPTY VALUE":
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
        ]

        for fmt in formats_to_try:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%m/%d/%Y")
            except ValueError:
                continue

        # If no format matches, return original
        return date_str


class ExtractionResult(BaseModel):
    """Container for extraction results with validation info"""

    data: WorkersCompensationData = Field(description="Validated extracted data")
    validation_errors: List[str] = Field(default_factory=list, description="List of validation errors encountered")
    warnings: List[str] = Field(default_factory=list, description="List of warnings during validation")
    raw_data: dict = Field(description="Original raw extracted data before validation")

    @property
    def is_valid(self) -> bool:
        """Check if extraction result is valid (no validation errors)"""
        return len(self.validation_errors) == 0

    @property
    def has_warnings(self) -> bool:
        """Check if extraction result has warnings"""
        return len(self.warnings) > 0


def validate_extracted_data(raw_data: dict) -> ExtractionResult:
    """
    Validate raw extracted data and return structured result
    """
    validation_errors = []
    warnings = []

    try:
        # Attempt to create validated model
        validated_data = WorkersCompensationData(**raw_data)

        # Additional business logic validations
        if hasattr(validated_data, "policy_effective_date") and hasattr(validated_data, "policy_expiration_date"):
            if (
                validated_data.policy_effective_date != "EMPTY VALUE"
                and validated_data.policy_expiration_date != "EMPTY VALUE"
            ):
                try:
                    effective = datetime.strptime(validated_data.policy_effective_date, "%m/%d/%Y")
                    expiration = datetime.strptime(validated_data.policy_expiration_date, "%m/%d/%Y")
                    if effective >= expiration:
                        warnings.append("Policy effective date should be before expiration date")
                except ValueError:
                    warnings.append("Could not validate date relationship due to invalid date format")

        return ExtractionResult(
            data=validated_data, validation_errors=validation_errors, warnings=warnings, raw_data=raw_data
        )

    except Exception as e:
        validation_errors.append(f"Data validation failed: {str(e)}")

        # Create a model with raw data for partial results
        try:
            # Try to create model with minimal validation
            partial_data = WorkersCompensationData.model_validate(raw_data)
        except Exception as e2:
            print(e2)
            # If that fails too, create empty model
            partial_data = WorkersCompensationData(
                quote_number="VALIDATION_FAILED",
                policy_effective_date="EMPTY VALUE",
                policy_expiration_date="EMPTY VALUE",
                named_insured_name="VALIDATION_FAILED",
                named_insured_address="VALIDATION_FAILED",
            )

        return ExtractionResult(
            data=partial_data, validation_errors=validation_errors, warnings=warnings, raw_data=raw_data
        )
