"""
Configuration management for the application
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml
from dotenv import load_dotenv
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

    # Storage Configuration
    storage_db_path: str = Field(default="data/extractions.db", description="Path to SQLite database")
    storage_enabled: bool = Field(default=True, description="Enable local storage of extractions")
    storage_cleanup_days: int = Field(default=90, description="Days to keep extraction records")
    storage_auto_cleanup: bool = Field(default=False, description="Enable automatic cleanup of old records")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@lru_cache()
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

    def get_prompt(self, document_type: str = "quote", version: str = None) -> str:
        """Get prompt by document type and version, defaults to latest"""
        if version is None:
            version = self.prompts.get("default_version", "v1")

        doc_type_config = self.prompts.get("document_types", {}).get(document_type)
        if not doc_type_config:
            raise ValueError(f"Document type {document_type} not found")
        
        prompt_config = doc_type_config.get("versions", {}).get(version)
        if not prompt_config:
            raise ValueError(f"Prompt version {version} not found for document type {document_type}")

        return self._render_prompt(prompt_config, document_type)

    def get_available_versions(self, document_type: str = "quote") -> List[str]:
        """Get list of available prompt versions for a document type"""
        doc_type_config = self.prompts.get("document_types", {}).get(document_type, {})
        return list(doc_type_config.get("versions", {}).keys())

    def get_field_config(self, field_name: str, document_type: str = "quote") -> Dict[str, Any]:
        """Get configuration for a specific field in a document type"""
        doc_type_config = self.fields.get("document_types", {}).get(document_type, {})
        return doc_type_config.get("fields", {}).get(field_name, {})

    def get_all_fields(self, document_type: str = "quote") -> Dict[str, Any]:
        """Get all field configurations for a document type"""
        doc_type_config = self.fields.get("document_types", {}).get(document_type, {})
        return doc_type_config.get("fields", {})

    def _render_prompt(self, prompt_config: Dict[str, Any], document_type: str = "quote") -> str:
        """Render prompt template with field definitions"""
        template = prompt_config["template"]
        fields_section = self._format_fields_for_prompt(document_type)
        example_output = prompt_config.get("example_output", "")

        return template.format(fields=fields_section, example_output=example_output)

    def _format_fields_for_prompt(self, document_type: str = "quote") -> str:
        """Format field definitions for inclusion in prompt"""
        fields = self.get_all_fields(document_type)
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
            "document_types": {
                "quote": {
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
                    }
                }
            },
        }

    def _get_default_fields(self) -> Dict[str, Any]:
        """Default field configuration if file doesn't exist"""
        return {
            "document_types": {
                "quote": {
                    "name": "Workers Compensation Quote",
                    "description": "Workers compensation insurance quote document",
                    "fields": {
                        "quote_number": {
                            "type": "String",
                            "description": "This is the unique quote number for the policy. If a quote contains multiple policies, each policy has its own unique quote number.",
                            "required": True,
                        }
                    }
                }
            }
        }


# @lru_cache()
def get_config_manager() -> ConfigManager:
    """Get cached configuration manager instance"""
    return ConfigManager()
