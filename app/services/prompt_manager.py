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

    def get_prompt(self, version: str = None) -> str:
        """
        Get prompt by version

        Args:
            version: Prompt version to retrieve (defaults to latest)

        Returns:
            Rendered prompt string
        """
        if version is None:
            version = self.get_default_version()

        # Check cache first
        cache_key = f"prompt_{version}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            prompt = self.config_manager.get_prompt(version)
            self._cache[cache_key] = prompt
            logger.info(f"Retrieved prompt version {version}")
            return prompt

        except Exception as e:
            logger.error(f"Failed to get prompt version {version}: {e}")
            raise ValueError(f"Prompt version {version} not found")

    def get_available_versions(self) -> List[str]:
        """Get list of available prompt versions"""
        try:
            return self.config_manager.get_available_versions()
        except Exception as e:
            logger.error(f"Failed to get available versions: {e}")
            return []

    def get_default_version(self) -> str:
        """Get the default prompt version"""
        try:
            return self.config_manager.prompts.get("default_version", "v1")
        except Exception as e:
            logger.error(f"Failed to get default version: {e}")
            return "v1"

    def get_prompt_info(self, version: str = None) -> Dict[str, Any]:
        """
        Get information about a specific prompt version

        Args:
            version: Prompt version to get info for

        Returns:
            Dict containing prompt metadata
        """
        if version is None:
            version = self.get_default_version()

        try:
            prompts_config = self.config_manager.prompts
            version_config = prompts_config["versions"].get(version, {})

            return {
                "version": version,
                "description": version_config.get("description", "No description available"),
                "template_length": len(version_config.get("template", "")),
                "has_example": bool(version_config.get("example_output")),
                "fields_count": len(self.get_all_fields()),
            }

        except Exception as e:
            logger.error(f"Failed to get prompt info for {version}: {e}")
            return {"version": version, "error": str(e)}

    def get_all_fields(self) -> Dict[str, Any]:
        """Get all field configurations"""
        try:
            return self.config_manager.get_all_fields()
        except Exception as e:
            logger.error(f"Failed to get fields: {e}")
            return {}

    def get_field_info(self, field_name: str) -> Dict[str, Any]:
        """Get information about a specific field"""
        try:
            return self.config_manager.get_field_config(field_name)
        except Exception as e:
            logger.error(f"Failed to get field info for {field_name}: {e}")
            return {}

    def validate_prompt_version(self, version: str) -> bool:
        """Validate if a prompt version exists"""
        available_versions = self.get_available_versions()
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
            self.config_manager._prompts_cache = None
            self.config_manager._fields_cache = None

            logger.info("Configuration reloaded successfully")

        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            raise

    def preview_prompt(self, version: str = None, max_length: int = 500) -> Dict[str, Any]:
        """
        Get a preview of the prompt

        Args:
            version: Prompt version to preview
            max_length: Maximum length of preview text

        Returns:
            Dict containing prompt preview and metadata
        """
        try:
            prompt = self.get_prompt(version)
            info = self.get_prompt_info(version)

            return {
                "version": version or self.get_default_version(),
                "preview": prompt[:max_length] + "..." if len(prompt) > max_length else prompt,
                "full_length": len(prompt),
                "info": info,
            }

        except Exception as e:
            logger.error(f"Failed to preview prompt {version}: {e}")
            return {"error": str(e)}


@lru_cache()
def get_prompt_manager() -> PromptManager:
    """Get cached prompt manager instance"""
    config_manager = get_config_manager()
    return PromptManager(config_manager)
