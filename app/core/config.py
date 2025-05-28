"""
Configuration management for the application
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml
from dotenv import find_dotenv, load_dotenv
from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    """Application settings"""

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # API Configuration
    api_key: str = Field()
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # Gemini Configuration
    gemini_api_key: str = Field(...)
    default_model: str = Field(default="gemini-1.5-flash")
    max_tokens: int = Field(default=4096)
    temperature: float = Field(default=0.1)

    # Rate Limiting
    rate_limit_requests: int = Field(default=100)
    rate_limit_window: str = Field(default="1 minute")

    # File Processing
    max_file_size_mb: int = Field(default=10)
    allowed_file_types: List[str] = Field(default_factory=lambda: [".pdf"])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


# @lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


class ConfigManager:
    """Manages configuration files for prompts and fields"""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self._prompts_cache = None
        self._fields_cache = None

    @property
    def prompts(self) -> Dict[str, Any]:
        """Load and cache prompt configurations"""
        if self._prompts_cache is None:
            prompts_file = self.config_dir / "prompts.yaml"
            if prompts_file.exists():
                with open(prompts_file, "r", encoding="utf-8") as f:
                    self._prompts_cache = yaml.safe_load(f)
            else:
                self._prompts_cache = self._get_default_prompts()
        return self._prompts_cache

    @property
    def fields(self) -> Dict[str, Any]:
        """Load and cache field configurations"""
        if self._fields_cache is None:
            fields_file = self.config_dir / "fields.yaml"
            if fields_file.exists():
                with open(fields_file, "r", encoding="utf-8") as f:
                    self._fields_cache = yaml.safe_load(f)
            else:
                self._fields_cache = self._get_default_fields()
        return self._fields_cache

    def get_prompt(self, version: str = None) -> str:
        """Get prompt by version, defaults to latest"""
        if version is None:
            version = self.prompts.get("default_version", "v2")

        prompt_config = self.prompts["versions"].get(version)
        if not prompt_config:
            raise ValueError(f"Prompt version {version} not found")

        return self._render_prompt(prompt_config)

    def get_available_versions(self) -> List[str]:
        """Get list of available prompt versions"""
        return list(self.prompts["versions"].keys())

    def get_field_config(self, field_name: str) -> Dict[str, Any]:
        """Get configuration for a specific field"""
        return self.fields["fields"].get(field_name, {})

    def get_all_fields(self) -> Dict[str, Any]:
        """Get all field configurations"""
        return self.fields["fields"]

    def _render_prompt(self, prompt_config: Dict[str, Any]) -> str:
        """Render prompt template with field definitions"""
        template = prompt_config["template"]
        fields_section = self._format_fields_for_prompt()
        example_output = prompt_config.get("example_output", "")

        return template.format(fields=fields_section, example_output=example_output)

    def _format_fields_for_prompt(self) -> str:
        """Format field definitions for inclusion in prompt"""
        fields = self.fields["fields"]
        formatted_fields = []

        for field_name, field_config in fields.items():
            field_desc = f"{field_name}:\n"
            field_desc += f"   - Data Type: {field_config.get('type', 'String')}\n"
            field_desc += f"   - Description: {field_config.get('description', 'No description available')}\n"

            if field_config.get("required", False):
                field_desc += "   - Required: Yes\n"

            if "format" in field_config:
                field_desc += f"   - Format: {field_config['format']}\n"

            formatted_fields.append(field_desc)

        return "\n".join(formatted_fields)

    def _get_default_prompts(self) -> Dict[str, Any]:
        """Default prompt configuration if file doesn't exist"""
        return {
            "default_version": "v1",
            "versions": {
                "v1": {
                    "description": "Workers Compensation extraction with focus on owners-officers exclusion",
                    "template": """From the provided insurance quote PDF, extract the listed fields for the Workers' Compensation policy. Return the results in the form of a JSON object, as shown in the example output.
Each field should adhere to the specified data type and description. Follow the example structure provided.

### Fields to Extract:

{fields}

### Example Output:

{example_output}""",
                    "example_output": """{
  "quote_number": "01WECBA3BVG003",
  "policy_effective_date": "2023-09-19",
  "policy_expiration_date": "2024-09-19",
  "named_insured_name": "ACME BEER II LLC DBA: NORTH END PIZZA",
  "named_insured_address": "1513 N 13TH ST BOISE ID 83702",
  "additional_named_insured_name": "Excluded",
  "additional_named_insured_address": "Excluded",
  "issuing_carrier": "['TX - Hartford Casualty Insurance Company - 3500', 'PA - Hartford Casualty Insurance Company - 253']",
  "commission": "EMPTY VALUE",
  "estimated_premium_amount": "3753",
  "minimum_earned_premium": "EMPTY VALUE",
  "taxes": "EMPTY VALUE",
  "tria": "Included",
  "waiver_of_subrogation_type": "Excluded",
  "workers_comp_each_accident_limit": "1000000",
  "workers_comp_disease_each_employee": "1000000",
  "workers_comp_disease_policy_limit": "1000000",
  "workers_comp_exclusion_description": "ID-Excluded"
}""",
                }
            },
        }

    def _get_default_fields(self) -> Dict[str, Any]:
        """Default field configuration if file doesn't exist"""
        return {
            "fields": {
                "quote_number": {
                    "type": "String",
                    "description": "This is the unique quote number for the policy. If a quote contains multiple policies, each policy has its own unique quote number.",
                    "required": True,
                },
                "policy_effective_date": {
                    "type": "Date",
                    "format": "MM/DD/YYYY",
                    "description": "The effective date of the policy. If the quote contains multiple policies, this date is usually the same for all policies, but should still be extracted individually if provided.",
                    "required": True,
                },
                "policy_expiration_date": {
                    "type": "Date",
                    "format": "MM/DD/YYYY",
                    "description": "The expiration date of the policy. Similar to the effective date, this date is typically the same for all policies, but should be extracted for each policy if provided.",
                    "required": True,
                },
                "named_insured_name": {
                    "type": "String",
                    "description": "The name of the primary policyholder (the Named Insured).",
                    "required": True,
                },
                "named_insured_address": {
                    "type": "String",
                    "description": "The address of the primary policyholder (the Named Insured).",
                    "required": True,
                },
                "additional_named_insured_name": {
                    "type": "Boolean",
                    "format": "Included/Excluded",
                    "description": "Indicates whether additional named insureds are included. Often, they are not explicitly listed in the quote but may be determined from endorsement forms.",
                },
                "additional_named_insured_address": {
                    "type": "String",
                    "description": "The address of the additional named insured if available; otherwise, return 'Excluded'.",
                },
                "issuing_carrier": {
                    "type": "String",
                    "description": "The name of the issuing carrier in a list, e.g. ['carrier name']. For Workers' compensation policy, check if you can detect a total premium per state. If so, return a list where each item is 'State code - issuing carrier - premium in that state (round it, don't show the decimals appearing after the point sign)', e.g. 'NY - Hartford Casualty Insurance Company - 553', as shown in the example output. Otherwise, just return the name of the issuing carrier in a list. You should extract the total estimated premium, it should explicitly be in the state list of cost, don't make up or transform a number.",
                },
                "commission": {
                    "type": "Percentage/Currency",
                    "description": "The commission details for the policy. This is typically included in the premium or fee section of the document. If not found, return 'EMPTY VALUE'.",
                },
                "estimated_premium_amount": {
                    "type": "Currency",
                    "description": "The total estimated premium amount. Usually found in the premium or fee section of the quote document.",
                },
                "minimum_earned_premium": {
                    "type": "Currency/Percentage",
                    "description": "The minimum earned premium, if applicable. It is sometimes stated within a disclaimer paragraph, but could also be in a table or summary. It could be related to a minimum premium required per state, or a cancellation fee. If the amount is not found, or is not an exact amount (or exact percentage of the total estimated premium), return 'EMPTY VALUE'. Do not calculate the minimum earned premium from penalties ranges, fees ranges, or percentages.",
                },
                "taxes": {
                    "type": "Currency",
                    "description": "The taxes associated with the policy. Usually included in the premium section of the document.",
                },
                "tria": {
                    "type": "Boolean",
                    "format": "Included/Excluded",
                    "description": "Whether the Terrorism Risk Insurance Act (TRIA) coverage is included in the policy. Sometimes this is listed explicitly, and other times it must be inferred from endorsement forms.",
                },
                "waiver_of_subrogation_type": {
                    "type": "Boolean",
                    "format": "Included/Excluded",
                    "description": "Indicates whether a waiver of subrogation is included",
                },
                "workers_comp_each_accident_limit": {
                    "type": "Currency",
                    "description": "The limit for each accident, typically found in the Workers' Compensation section of the quote.",
                },
                "workers_comp_disease_each_employee": {
                    "type": "Currency",
                    "description": "The coverage limit for disease for each employee, found in the Workers' Compensation section.",
                },
                "workers_comp_disease_policy_limit": {
                    "type": "Currency",
                    "description": "The overall policy limit for disease coverage, typically found in the Workers' Compensation section.",
                },
                "workers_comp_exclusion_description": {
                    "type": "String",
                    "description": "There may be states where officers or owners are excluded from the Workers' Compensation policy. It may come as a note stating if a given state is excluded or included. Only if it is an exclusion, return the state code followed by the excluded status, e.g. 'TX-Excluded'. If it is not an exclusion or no exclusion clauses are found, return 'EMPTY VALUE'.",
                },
            }
        }


# @lru_cache()
def get_config_manager() -> ConfigManager:
    """Get cached configuration manager instance"""
    return ConfigManager()
