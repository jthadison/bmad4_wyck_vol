"""
Unit tests for Settings API Routes

Tests IP address validation and other route utilities.
Story 19.14: Auto-Execution Configuration Backend
"""

import pytest

from src.api.routes.settings import validate_ip_address


class TestIPAddressValidation:
    """Tests for IP address validation."""

    def test_valid_ipv4_address(self):
        """Test validation of valid IPv4 address."""
        result = validate_ip_address("192.168.1.1")
        assert result == "192.168.1.1"

    def test_valid_ipv6_address(self):
        """Test validation of valid IPv6 address."""
        result = validate_ip_address("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
        # ipaddress normalizes IPv6 addresses
        assert result == "2001:db8:85a3::8a2e:370:7334"

    def test_ipv6_shorthand(self):
        """Test validation of IPv6 shorthand notation."""
        result = validate_ip_address("::1")
        assert result == "::1"

    def test_unknown_ip_allowed(self):
        """Test that 'unknown' is allowed as a special case."""
        result = validate_ip_address("unknown")
        assert result == "unknown"

    def test_invalid_ip_format_raises_error(self):
        """Test that invalid IP format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid IP address format"):
            validate_ip_address("not-an-ip")

    def test_empty_string_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid IP address format"):
            validate_ip_address("")

    def test_invalid_ipv4_raises_error(self):
        """Test that invalid IPv4 raises ValueError."""
        with pytest.raises(ValueError, match="Invalid IP address format"):
            validate_ip_address("256.256.256.256")

    def test_localhost_ipv4(self):
        """Test validation of localhost IPv4."""
        result = validate_ip_address("127.0.0.1")
        assert result == "127.0.0.1"

    def test_localhost_ipv6(self):
        """Test validation of localhost IPv6."""
        result = validate_ip_address("::1")
        assert result == "::1"
