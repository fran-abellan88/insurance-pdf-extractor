"""
Security utilities for API key authentication
"""

import logging
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# API Key authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class APIKeyAuth:
    """API Key authentication handler"""

    def __init__(self):
        self.settings = get_settings()
        self.valid_api_key = self.settings.api_key

        if not self.valid_api_key:
            logger.warning("No API keys configured. All requests will be rejected.")

    def validate_api_key(self, api_key: str) -> bool:
        """Validate if the provided API key is valid"""
        return api_key in self.valid_api_key

    def get_api_key_info(self, api_key: str) -> Optional[dict]:
        """Get information about the API key (could be extended for user info)"""
        if self.validate_api_key(api_key):
            # In a real application, you might return user info, permissions, etc.
            return {"key": api_key[:8] + "...", "valid": True}  # Only show first 8 chars for logging
        return None


# Global instance
api_key_auth = APIKeyAuth()


async def get_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Dependency to validate API key from header
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Please provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not api_key_auth.validate_api_key(api_key):
        logger.warning(f"Invalid API key attempt: {api_key[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    logger.info(f"Valid API key used: {api_key[:3]}...")
    return api_key


async def get_current_user(api_key: str = Security(get_api_key)) -> dict:
    """
    Get current user information based on API key
    This can be extended to return actual user data from a database
    """
    user_info = api_key_auth.get_api_key_info(api_key)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    return user_info


def create_api_key() -> str:
    """
    Utility function to generate new API keys
    In production, this would be more sophisticated
    """
    import secrets
    import string

    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(32))


def add_api_key(new_key: str) -> bool:
    """
    Add a new API key to the valid keys set
    In production, this would update a database
    """
    try:
        api_key_auth.valid_api_key.add(new_key)
        logger.info(f"Added new API key: {new_key[:8]}...")
        return True
    except Exception as e:
        logger.error(f"Failed to add API key: {e}")
        return False


def revoke_api_key(key_to_revoke: str) -> bool:
    """
    Revoke an API key
    In production, this would update a database
    """
    try:
        api_key_auth.valid_api_key.discard(key_to_revoke)
        logger.info(f"Revoked API key: {key_to_revoke[:8]}...")
        return True
    except Exception as e:
        logger.error(f"Failed to revoke API key: {e}")
        return False
