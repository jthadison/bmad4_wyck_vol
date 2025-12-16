"""
API Key Service

Handles API key generation, hashing, and validation.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID, uuid4


class APIKeyService:
    """Service for API key management"""

    # API key prefix for identification
    KEY_PREFIX = "bmad_"
    # Length of random key component (bytes)
    KEY_LENGTH = 32

    def create_api_key(
        self, user_id: UUID, name: str, scopes: list[str], expires_days: int
    ) -> tuple[UUID, str, str, datetime]:
        """
        Create a new API key

        Args:
            user_id: User UUID
            name: Key name/description
            scopes: List of permission scopes
            expires_days: Days until expiration

        Returns:
            Tuple of (key_id, api_key, key_hash, expires_at)
            - key_id: UUID for the key
            - api_key: Full key string (only returned once)
            - key_hash: SHA256 hash of the key (for storage)
            - expires_at: Expiration datetime
        """
        # Generate unique key ID
        key_id = uuid4()

        # Generate random key
        random_bytes = secrets.token_bytes(self.KEY_LENGTH)
        key_hex = random_bytes.hex()
        api_key = f"{self.KEY_PREFIX}{key_hex}"

        # Hash the key for storage (never store plain key)
        key_hash = self._hash_key(api_key)

        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(days=expires_days)

        return key_id, api_key, key_hash, expires_at

    def _hash_key(self, api_key: str) -> str:
        """
        Hash an API key using SHA256

        Args:
            api_key: Full API key string

        Returns:
            SHA256 hash as hex string
        """
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    def verify_key(self, api_key: str, key_hash: str) -> bool:
        """
        Verify an API key against its hash

        Args:
            api_key: Full API key string
            key_hash: Stored hash

        Returns:
            True if key matches hash, False otherwise
        """
        try:
            computed_hash = self._hash_key(api_key)
            return secrets.compare_digest(computed_hash, key_hash)
        except Exception:
            return False

    def mask_key(self, api_key: str) -> str:
        """
        Mask an API key for display (show only prefix and last 4 chars)

        Args:
            api_key: Full API key string

        Returns:
            Masked key string (e.g., "bmad_...abc123")
        """
        if not api_key or len(api_key) < 10:
            return "***"

        return f"{self.KEY_PREFIX}...{api_key[-8:]}"
