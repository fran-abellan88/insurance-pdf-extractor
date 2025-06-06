"""
Prompt management service for versioning and configuration
"""

import logging
from functools import lru_cache
from typing import Any, Dict, List

from app.core.config import ConfigManager, get_config_manager

logger = logging.getLogger(__name__)


class PromptManager:
    """Manages prompt templates and versions"""

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._cache = {}

    def get_prompt(self, document_type: str = "quote", version: str = None) -> str:
        """
        Get prompt by document type and version

        Args:
            document_type: Type of document (e.g., 'quote', 'binder')
            version: Prompt version to retrieve (defaults to latest)

        Returns:
            Rendered prompt string
        """
        if version is None:
            version = self.get_default_version()

        # Check cache first
        cache_key = f"prompt_{document_type}_{version}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            prompt = self.config_manager.get_prompt(document_type, version)
            self._cache[cache_key] = prompt
            logger.info(f"Retrieved prompt for {document_type} version {version}")
            return prompt

        except Exception as e:
            logger.error(f"Failed to get prompt for {document_type} version {version}: {e}")
            raise ValueError(f"Prompt for {document_type} version {version} not found")

    def get_available_versions(self, document_type: str = "quote") -> List[str]:
        """Get list of available prompt versions for a document type"""
        try:
            return self.config_manager.get_available_versions(document_type)
        except Exception as e:
            logger.error(f"Failed to get available versions for {document_type}: {e}")
            return []

    def get_default_version(self) -> str:
        """Get the default prompt version"""
        try:
            return self.config_manager.prompts.get("default_version", "v1")
        except Exception as e:
            logger.error(f"Failed to get default version: {e}")
            return "v1"

    def get_prompt_info(self, document_type: str = "quote", version: str = None) -> Dict[str, Any]:
        """
        Get information about a specific prompt version

        Args:
            document_type: Type of document
            version: Prompt version to get info for

        Returns:
            Dict containing prompt metadata
        """
        if version is None:
            version = self.get_default_version()

        try:
            prompts_config = self.config_manager.prompts
            doc_type_config = prompts_config["document_types"].get(document_type, {})
            version_config = doc_type_config.get("versions", {}).get(version, {})

            return {
                "document_type": document_type,
                "version": version,
                "description": version_config.get("description", "No description available"),
                "template_length": len(version_config.get("template", "")),
                "has_example": bool(version_config.get("example_output")),
                "fields_count": len(self.get_all_fields(document_type)),
            }

        except Exception as e:
            logger.error(f"Failed to get prompt info for {document_type} {version}: {e}")
            return {"document_type": document_type, "version": version, "error": str(e)}

    def get_all_fields(self, document_type: str = "quote") -> Dict[str, Any]:
        """Get all field configurations for a document type"""
        try:
            return self.config_manager.get_all_fields(document_type)
        except Exception as e:
            logger.error(f"Failed to get fields for {document_type}: {e}")
            return {}

    def get_field_info(self, field_name: str, document_type: str = "quote") -> Dict[str, Any]:
        """Get information about a specific field for a document type"""
        try:
            return self.config_manager.get_field_config(field_name, document_type)
        except Exception as e:
            logger.error(f"Failed to get field info for {field_name} in {document_type}: {e}")
            return {}

    def validate_prompt_version(self, version: str, document_type: str = "quote") -> bool:
        """Validate if a prompt version exists for a document type"""
        available_versions = self.get_available_versions(document_type)
        return version in available_versions

    def clear_cache(self) -> None:
        """Clear the prompt cache"""
        self._cache.clear()
        logger.info("Prompt cache cleared")

    def reload_config(self) -> None:
        """Reload configuration from files"""
        try:
            # Clear caches
            self.clear_cache()
            if hasattr(self.config_manager, '_prompts_cache'):
                self.config_manager._prompts_cache = None
            if hasattr(self.config_manager, '_fields_cache'):
                self.config_manager._fields_cache = None

            logger.info("Configuration reloaded successfully")

        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            raise

    def preview_prompt(self, document_type: str = "quote", version: str = None, max_length: int = 500) -> Dict[str, Any]:
        """
        Get a preview of the prompt

        Args:
            document_type: Type of document
            version: Prompt version to preview
            max_length: Maximum length of preview text

        Returns:
            Dict containing prompt preview and metadata
        """
        try:
            prompt = self.get_prompt(document_type, version)
            info = self.get_prompt_info(document_type, version)

            return {
                "document_type": document_type,
                "version": version or self.get_default_version(),
                "preview": prompt[:max_length] + "..." if len(prompt) > max_length else prompt,
                "full_length": len(prompt),
                "info": info,
            }

        except Exception as e:
            logger.error(f"Failed to preview prompt {document_type} {version}: {e}")
            return {"error": str(e)}


@lru_cache()
def get_prompt_manager() -> PromptManager:
    """Get cached prompt manager instance"""
    config_manager = get_config_manager()
    return PromptManager(config_manager)
