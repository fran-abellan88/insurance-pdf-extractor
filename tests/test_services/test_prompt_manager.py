"""
Tests for prompt manager service
"""

from unittest.mock import Mock, patch

import pytest

from app.services.prompt_manager import PromptManager


class TestPromptManager:

    @pytest.fixture
    def mock_config_manager(self):
        """Create mock config manager"""
        mock_config = Mock()
        
        # Mock prompts data
        mock_config.prompts = {
            "default_version": "v1",
            "document_types": {
                "quote": {
                    "versions": {
                        "v1": {
                            "description": "Quote extraction v1",
                            "template": "Extract from quote: {fields}\nExample: {example_output}",
                            "example_output": '{"quote_number": "123"}'
                        },
                        "v2": {
                            "description": "Quote extraction v2",
                            "template": "Advanced extract: {fields}",
                            "example_output": '{"quote_number": "456"}'
                        }
                    }
                },
                "binder": {
                    "versions": {
                        "v1": {
                            "description": "Binder extraction v1",
                            "template": "Extract binder: {fields}",
                            "example_output": '{"binder_number": "BIND123"}'
                        }
                    }
                }
            }
        }
        
        # Mock fields data
        mock_config.fields = {
            "document_types": {
                "quote": {
                    "fields": {
                        "quote_number": {
                            "type": "String",
                            "description": "Quote number field",
                            "required": True
                        },
                        "policy_date": {
                            "type": "Date",
                            "description": "Policy date field",
                            "format": "MM/DD/YYYY",
                            "required": False
                        }
                    }
                },
                "binder": {
                    "fields": {
                        "binder_number": {
                            "type": "String",
                            "description": "Binder number field",
                            "required": True
                        }
                    }
                }
            }
        }
        
        # Mock methods
        mock_config.get_prompt.return_value = "Mock prompt with fields"
        mock_config.get_available_versions.return_value = ["v1", "v2"]
        mock_config.get_all_fields.return_value = mock_config.fields["document_types"]["quote"]["fields"]
        mock_config.get_field_config.return_value = {"type": "String", "description": "Test field"}
        
        return mock_config

    @pytest.fixture
    def prompt_manager(self, mock_config_manager):
        """Create prompt manager instance with mock config"""
        return PromptManager(mock_config_manager)

    def test_init(self, mock_config_manager):
        """Test prompt manager initialization"""
        
        manager = PromptManager(mock_config_manager)
        
        assert manager.config_manager == mock_config_manager
        assert manager._cache == {}

    def test_get_prompt_default_version(self, prompt_manager, mock_config_manager):
        """Test getting prompt with default version"""
        
        result = prompt_manager.get_prompt("quote")
        
        mock_config_manager.get_prompt.assert_called_once_with("quote", "v1")
        assert result == "Mock prompt with fields"

    def test_get_prompt_specific_version(self, prompt_manager, mock_config_manager):
        """Test getting prompt with specific version"""
        
        result = prompt_manager.get_prompt("quote", "v2")
        
        mock_config_manager.get_prompt.assert_called_once_with("quote", "v2")
        assert result == "Mock prompt with fields"

    def test_get_prompt_binder_document(self, prompt_manager, mock_config_manager):
        """Test getting prompt for binder document"""
        
        result = prompt_manager.get_prompt("binder", "v1")
        
        mock_config_manager.get_prompt.assert_called_once_with("binder", "v1")
        assert result == "Mock prompt with fields"

    def test_get_prompt_caching(self, prompt_manager, mock_config_manager):
        """Test prompt caching functionality"""
        
        # First call
        result1 = prompt_manager.get_prompt("quote", "v1")
        
        # Second call should use cache
        result2 = prompt_manager.get_prompt("quote", "v1")
        
        # Should only call config manager once due to caching
        assert mock_config_manager.get_prompt.call_count == 1
        assert result1 == result2

    def test_get_prompt_config_error(self, prompt_manager, mock_config_manager):
        """Test prompt retrieval with config error"""
        
        mock_config_manager.get_prompt.side_effect = Exception("Config error")
        
        with pytest.raises(ValueError) as exc_info:
            prompt_manager.get_prompt("quote", "v1")
        
        assert "Prompt for quote version v1 not found" in str(exc_info.value)

    def test_get_available_versions_success(self, prompt_manager, mock_config_manager):
        """Test getting available versions successfully"""
        
        result = prompt_manager.get_available_versions("quote")
        
        mock_config_manager.get_available_versions.assert_called_once_with("quote")
        assert result == ["v1", "v2"]

    def test_get_available_versions_binder(self, prompt_manager, mock_config_manager):
        """Test getting available versions for binder"""
        
        mock_config_manager.get_available_versions.return_value = ["v1"]
        
        result = prompt_manager.get_available_versions("binder")
        
        mock_config_manager.get_available_versions.assert_called_once_with("binder")
        assert result == ["v1"]

    def test_get_available_versions_error(self, prompt_manager, mock_config_manager):
        """Test getting available versions with error"""
        
        mock_config_manager.get_available_versions.side_effect = Exception("Config error")
        
        result = prompt_manager.get_available_versions("quote")
        
        assert result == []

    def test_get_default_version_success(self, prompt_manager):
        """Test getting default version successfully"""
        
        result = prompt_manager.get_default_version()
        
        assert result == "v1"

    def test_get_default_version_error(self, prompt_manager, mock_config_manager):
        """Test getting default version with error"""
        
        mock_config_manager.prompts = {}
        
        result = prompt_manager.get_default_version()
        
        assert result == "v1"  # fallback

    def test_get_default_version_exception(self, prompt_manager, mock_config_manager):
        """Test getting default version with exception"""
        
        del mock_config_manager.prompts
        
        result = prompt_manager.get_default_version()
        
        assert result == "v1"  # fallback

    def test_get_prompt_info_success(self, prompt_manager, mock_config_manager):
        """Test getting prompt info successfully"""
        
        result = prompt_manager.get_prompt_info("quote", "v1")
        
        assert result["document_type"] == "quote"
        assert result["version"] == "v1"
        assert result["description"] == "Quote extraction v1"
        assert result["template_length"] > 0
        assert result["has_example"] is True
        assert result["fields_count"] == 2

    def test_get_prompt_info_default_version(self, prompt_manager, mock_config_manager):
        """Test getting prompt info with default version"""
        
        result = prompt_manager.get_prompt_info("quote")
        
        assert result["version"] == "v1"

    def test_get_prompt_info_error(self, prompt_manager, mock_config_manager):
        """Test getting prompt info with error"""
        
        mock_config_manager.prompts = {"invalid": "data"}
        
        result = prompt_manager.get_prompt_info("quote", "v1")
        
        assert "error" in result
        assert result["document_type"] == "quote"
        assert result["version"] == "v1"

    def test_get_all_fields_success(self, prompt_manager, mock_config_manager):
        """Test getting all fields successfully"""
        
        result = prompt_manager.get_all_fields("quote")
        
        mock_config_manager.get_all_fields.assert_called_once_with("quote")
        assert "quote_number" in result
        assert "policy_date" in result

    def test_get_all_fields_binder(self, prompt_manager, mock_config_manager):
        """Test getting all fields for binder"""
        
        mock_config_manager.get_all_fields.return_value = {"binder_number": {"type": "String"}}
        
        result = prompt_manager.get_all_fields("binder")
        
        mock_config_manager.get_all_fields.assert_called_once_with("binder")
        assert "binder_number" in result

    def test_get_all_fields_error(self, prompt_manager, mock_config_manager):
        """Test getting all fields with error"""
        
        mock_config_manager.get_all_fields.side_effect = Exception("Config error")
        
        result = prompt_manager.get_all_fields("quote")
        
        assert result == {}

    def test_get_field_info_success(self, prompt_manager, mock_config_manager):
        """Test getting field info successfully"""
        
        result = prompt_manager.get_field_info("quote_number", "quote")
        
        mock_config_manager.get_field_config.assert_called_once_with("quote_number", "quote")
        assert result == {"type": "String", "description": "Test field"}

    def test_get_field_info_error(self, prompt_manager, mock_config_manager):
        """Test getting field info with error"""
        
        mock_config_manager.get_field_config.side_effect = Exception("Config error")
        
        result = prompt_manager.get_field_info("quote_number", "quote")
        
        assert result == {}

    def test_validate_prompt_version_valid(self, prompt_manager, mock_config_manager):
        """Test validating existing prompt version"""
        
        result = prompt_manager.validate_prompt_version("v1", "quote")
        
        assert result is True

    def test_validate_prompt_version_invalid(self, prompt_manager, mock_config_manager):
        """Test validating non-existing prompt version"""
        
        mock_config_manager.get_available_versions.return_value = ["v1", "v2"]
        
        result = prompt_manager.validate_prompt_version("v3", "quote")
        
        assert result is False

    def test_clear_cache(self, prompt_manager):
        """Test clearing prompt cache"""
        
        # Add something to cache
        prompt_manager._cache["test_key"] = "test_value"
        
        prompt_manager.clear_cache()
        
        assert prompt_manager._cache == {}

    def test_reload_config(self, prompt_manager, mock_config_manager):
        """Test reloading configuration"""
        
        # Add to cache and set config attributes
        prompt_manager._cache["test"] = "value"
        mock_config_manager._prompts_cache = "old_cache"
        mock_config_manager._fields_cache = "old_cache"
        
        prompt_manager.reload_config()
        
        # Cache should be cleared
        assert prompt_manager._cache == {}
        # Config caches should be reset
        assert mock_config_manager._prompts_cache is None
        assert mock_config_manager._fields_cache is None

    def test_reload_config_error(self, prompt_manager, mock_config_manager):
        """Test reloading configuration with error"""
        
        # Mock the reload to raise an exception
        with patch.object(mock_config_manager, '_prompts_cache', side_effect=AttributeError("Attribute error")):
            # The reload_config method handles exceptions gracefully, so we expect it to complete
            prompt_manager.reload_config()
            # Just verify the cache was cleared even if config reload had issues
            assert prompt_manager._cache == {}

    def test_preview_prompt_success(self, prompt_manager, mock_config_manager):
        """Test previewing prompt successfully"""
        
        mock_config_manager.get_prompt.return_value = "This is a very long prompt template that should be truncated when previewing it to show only the beginning part of the content"
        
        result = prompt_manager.preview_prompt("quote", "v1", max_length=50)
        
        assert result["document_type"] == "quote"
        assert result["version"] == "v1"
        assert len(result["preview"]) <= 53  # 50 + "..."
        assert result["preview"].endswith("...")
        assert result["full_length"] > 50
        assert "info" in result

    def test_preview_prompt_short_content(self, prompt_manager, mock_config_manager):
        """Test previewing short prompt"""
        
        mock_config_manager.get_prompt.return_value = "Short prompt"
        
        result = prompt_manager.preview_prompt("quote", "v1")
        
        assert result["preview"] == "Short prompt"
        assert not result["preview"].endswith("...")

    def test_preview_prompt_default_version(self, prompt_manager, mock_config_manager):
        """Test previewing prompt with default version"""
        
        mock_config_manager.get_prompt.return_value = "Test prompt"
        
        result = prompt_manager.preview_prompt("quote")
        
        assert result["version"] == "v1"

    def test_preview_prompt_error(self, prompt_manager, mock_config_manager):
        """Test previewing prompt with error"""
        
        mock_config_manager.get_prompt.side_effect = Exception("Config error")
        
        result = prompt_manager.preview_prompt("quote", "v1")
        
        assert "error" in result


def test_get_prompt_manager():
    """Test getting cached prompt manager instance"""
    
    # Clear the lru_cache first
    from app.services.prompt_manager import get_prompt_manager
    get_prompt_manager.cache_clear()
    
    with patch("app.services.prompt_manager.get_config_manager") as mock_get_config:
        mock_config = Mock()
        mock_get_config.return_value = mock_config
        
        # First call
        manager1 = get_prompt_manager()
        
        # Second call should return cached instance
        manager2 = get_prompt_manager()
        
        assert manager1 is manager2
        assert mock_get_config.call_count == 1  # Should only be called once due to caching