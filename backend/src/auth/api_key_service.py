"""
API Key Service

Stub implementation for API key management.
TODO: Implement full API key service.
"""


class APIKeyService:
    """Stub API key service."""

    def __init__(self):
        """Initialize API key service."""
        pass

    def create_api_key(self, user_id: str) -> str:
        """Create API key for user."""
        raise NotImplementedError("API key service not yet implemented")

    def validate_api_key(self, api_key: str) -> bool:
        """Validate API key."""
        raise NotImplementedError("API key service not yet implemented")

    def revoke_api_key(self, api_key: str) -> None:
        """Revoke API key."""
        raise NotImplementedError("API key service not yet implemented")
