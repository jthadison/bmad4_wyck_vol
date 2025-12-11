"""
Password Service

Handles password hashing, verification, and strength validation using bcrypt.
"""

import re

import bcrypt


class PasswordService:
    """Service for password management"""

    # Minimum bcrypt cost factor (rounds)
    MIN_COST_FACTOR = 12

    def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt with min 12 rounds

        Args:
            password: Plain text password

        Returns:
            Hashed password as string
        """
        # Generate salt and hash
        salt = bcrypt.gensalt(rounds=self.MIN_COST_FACTOR)
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)

        # Return as string (bcrypt returns bytes)
        return hashed.decode("utf-8")

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against a hash

        Args:
            password: Plain text password
            password_hash: Hashed password

        Returns:
            True if password matches hash, False otherwise
        """
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception:
            # Invalid hash or other bcrypt error
            return False

    def validate_password_strength(self, password: str) -> tuple[bool, str]:
        """
        Validate password strength

        Requirements:
        - Minimum 12 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character

        Args:
            password: Plain text password

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check minimum length
        if len(password) < 12:
            return False, "Password must be at least 12 characters long"

        # Check for uppercase letter
        if not re.search(r"[A-Z]", password):
            return False, "Password must contain at least one uppercase letter"

        # Check for lowercase letter
        if not re.search(r"[a-z]", password):
            return False, "Password must contain at least one lowercase letter"

        # Check for digit
        if not re.search(r"\d", password):
            return False, "Password must contain at least one digit"

        # Check for special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/;\'`~]', password):
            return False, "Password must contain at least one special character"

        return True, ""

    def change_password(
        self, current_password: str, current_hash: str, new_password: str
    ) -> tuple[bool, str, str]:
        """
        Change password with validation

        Args:
            current_password: Current plain text password
            current_hash: Current password hash
            new_password: New plain text password

        Returns:
            Tuple of (success, new_hash or error_message, message_type)
            message_type is either "hash" or "error"
        """
        # Verify current password
        if not self.verify_password(current_password, current_hash):
            return False, "Current password is incorrect", "error"

        # Validate new password strength
        is_valid, error_msg = self.validate_password_strength(new_password)
        if not is_valid:
            return False, error_msg, "error"

        # Hash new password
        new_hash = self.hash_password(new_password)

        return True, new_hash, "hash"
