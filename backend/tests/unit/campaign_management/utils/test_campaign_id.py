"""
Unit tests for campaign ID generation utility (Story 18.5)

Tests cover:
- ID generation with string and datetime inputs
- ID parsing back to components
- Error handling for invalid formats
"""

from datetime import datetime

import pytest

from src.campaign_management.utils.campaign_id import (
    generate_campaign_id,
    parse_campaign_id,
)


class TestGenerateCampaignId:
    """Tests for generate_campaign_id function."""

    def test_generate_with_string_date(self):
        """Should generate ID from symbol and string date."""
        campaign_id = generate_campaign_id("AAPL", "2024-10-15")

        assert campaign_id == "AAPL-2024-10-15"

    def test_generate_with_datetime(self):
        """Should generate ID from symbol and datetime object."""
        ts = datetime(2024, 10, 15, 14, 30, 0)
        campaign_id = generate_campaign_id("AAPL", ts)

        assert campaign_id == "AAPL-2024-10-15"

    def test_generate_preserves_symbol_case(self):
        """Should preserve symbol case as provided."""
        campaign_id = generate_campaign_id("eurusd", "2024-10-15")

        assert campaign_id == "eurusd-2024-10-15"

    def test_generate_forex_symbol(self):
        """Should work with forex symbols."""
        campaign_id = generate_campaign_id("EURUSD", "2024-10-15")

        assert campaign_id == "EURUSD-2024-10-15"

    def test_generate_crypto_symbol(self):
        """Should work with crypto symbols."""
        campaign_id = generate_campaign_id("BTCUSD", "2024-10-15")

        assert campaign_id == "BTCUSD-2024-10-15"


class TestParseCampaignId:
    """Tests for parse_campaign_id function."""

    def test_parse_valid_id(self):
        """Should parse valid campaign ID into components."""
        parsed = parse_campaign_id("AAPL-2024-10-15")

        assert parsed["symbol"] == "AAPL"
        assert parsed["date"] == "2024-10-15"

    def test_parse_forex_symbol(self):
        """Should parse forex symbol correctly."""
        parsed = parse_campaign_id("EURUSD-2024-10-15")

        assert parsed["symbol"] == "EURUSD"
        assert parsed["date"] == "2024-10-15"

    def test_parse_lowercase_symbol(self):
        """Should preserve lowercase in parsed symbol."""
        parsed = parse_campaign_id("aapl-2024-10-15")

        assert parsed["symbol"] == "aapl"
        assert parsed["date"] == "2024-10-15"

    def test_parse_invalid_format_no_date(self):
        """Should raise ValueError for ID without proper date."""
        with pytest.raises(ValueError, match="Invalid campaign ID format"):
            parse_campaign_id("AAPL")

    def test_parse_invalid_format_incomplete_date(self):
        """Should raise ValueError for ID with incomplete date."""
        with pytest.raises(ValueError, match="Invalid campaign ID format"):
            parse_campaign_id("AAPL-2024-10")

    def test_parse_invalid_date_values(self):
        """Should raise ValueError for invalid date values."""
        with pytest.raises(ValueError, match="Invalid date in campaign ID"):
            parse_campaign_id("AAPL-2024-13-45")  # Invalid month and day

    def test_parse_invalid_date_format(self):
        """Should raise ValueError for malformed date."""
        with pytest.raises(ValueError, match="Invalid date in campaign ID"):
            parse_campaign_id("AAPL-24-10-15")  # Year too short


class TestGenerateAndParse:
    """Integration tests for generate and parse roundtrip."""

    def test_roundtrip_string_date(self):
        """Should roundtrip generate → parse with string date."""
        original_symbol = "AAPL"
        original_date = "2024-10-15"

        campaign_id = generate_campaign_id(original_symbol, original_date)
        parsed = parse_campaign_id(campaign_id)

        assert parsed["symbol"] == original_symbol
        assert parsed["date"] == original_date

    def test_roundtrip_datetime(self):
        """Should roundtrip generate → parse with datetime."""
        original_symbol = "EURUSD"
        original_datetime = datetime(2024, 10, 15, 14, 30, 0)
        expected_date = "2024-10-15"

        campaign_id = generate_campaign_id(original_symbol, original_datetime)
        parsed = parse_campaign_id(campaign_id)

        assert parsed["symbol"] == original_symbol
        assert parsed["date"] == expected_date

    def test_uniqueness_same_inputs(self):
        """Same inputs should produce identical IDs (deterministic)."""
        id1 = generate_campaign_id("AAPL", "2024-10-15")
        id2 = generate_campaign_id("AAPL", "2024-10-15")

        assert id1 == id2

    def test_uniqueness_different_symbols(self):
        """Different symbols should produce different IDs."""
        id1 = generate_campaign_id("AAPL", "2024-10-15")
        id2 = generate_campaign_id("MSFT", "2024-10-15")

        assert id1 != id2

    def test_uniqueness_different_dates(self):
        """Different dates should produce different IDs."""
        id1 = generate_campaign_id("AAPL", "2024-10-15")
        id2 = generate_campaign_id("AAPL", "2024-10-16")

        assert id1 != id2
