"""
Unit Tests for Broker Profiles (Story 12.5).

Tests broker commission profile retrieval, validation, and defaults.

Author: Story 12.5 Task 15 (Additional QA Requirement)
"""

from decimal import Decimal

import pytest

from src.backtesting.broker_profiles import BrokerProfiles, get_broker_profiles
from src.models.backtest import CommissionConfig


class TestBrokerProfiles:
    """Unit tests for BrokerProfiles."""

    @pytest.fixture
    def broker_profiles(self):
        """Create BrokerProfiles instance."""
        return BrokerProfiles()

    # Test 1: Test Interactive Brokers Retail profile (default)
    def test_interactive_brokers_retail_profile(self, broker_profiles):
        """Test Interactive Brokers Retail commission profile."""
        config = broker_profiles.get_profile("interactive_brokers_retail")

        assert config.commission_type == "PER_SHARE"
        assert config.commission_per_share == Decimal("0.005")
        assert config.min_commission == Decimal("1.00")
        assert config.broker_name == "Interactive Brokers Retail"

    # Test 2: Test Interactive Brokers Pro profile
    def test_interactive_brokers_pro_profile(self, broker_profiles):
        """Test Interactive Brokers Pro commission profile."""
        config = broker_profiles.get_profile("interactive_brokers_pro")

        assert config.commission_type == "PER_SHARE"
        assert config.commission_per_share == Decimal("0.0035")
        assert config.min_commission == Decimal("0.35")
        assert config.broker_name == "Interactive Brokers Pro"

    # Test 3: Test zero-commission broker (Robinhood)
    def test_robinhood_zero_commission(self, broker_profiles):
        """Test Robinhood zero-commission profile."""
        config = broker_profiles.get_profile("robinhood")

        assert config.commission_type == "FIXED"
        assert config.fixed_commission_per_trade == Decimal("0")
        assert config.min_commission == Decimal("0")
        assert config.broker_name == "Robinhood"

    # Test 4: Test all zero-commission brokers
    def test_all_zero_commission_brokers(self, broker_profiles):
        """Test all zero-commission broker profiles."""
        zero_commission_brokers = [
            "td_ameritrade",
            "robinhood",
            "etrade",
            "fidelity",
            "charles_schwab",
        ]

        for broker_name in zero_commission_brokers:
            config = broker_profiles.get_profile(broker_name)
            assert config.commission_type == "FIXED"
            assert config.fixed_commission_per_trade == Decimal("0")
            assert config.min_commission == Decimal("0")

    # Test 5: Test default profile is Interactive Brokers Retail
    def test_default_profile(self, broker_profiles):
        """Test default profile returns Interactive Brokers Retail."""
        default_config = broker_profiles.get_default_profile()
        ib_retail_config = broker_profiles.get_profile("interactive_brokers_retail")

        assert default_config.broker_name == ib_retail_config.broker_name
        assert default_config.commission_per_share == ib_retail_config.commission_per_share
        assert default_config.commission_type == ib_retail_config.commission_type

    # Test 6: Test unknown broker raises ValueError
    def test_unknown_broker_raises_error(self, broker_profiles):
        """Test that requesting unknown broker raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            broker_profiles.get_profile("unknown_broker")

        assert "Unknown broker profile" in str(exc_info.value)
        assert "unknown_broker" in str(exc_info.value)

    # Test 7: Test list_available_profiles returns all brokers
    def test_list_available_profiles(self, broker_profiles):
        """Test listing all available broker profiles."""
        available = broker_profiles.list_available_profiles()

        # Should include at least these brokers
        expected_brokers = [
            "interactive_brokers_retail",
            "interactive_brokers_pro",
            "robinhood",
            "td_ameritrade",
            "etrade",
            "fidelity",
            "charles_schwab",
            "interactive_brokers_legacy",
        ]

        for broker in expected_brokers:
            assert broker in available

        # Should be sorted alphabetically
        assert available == sorted(available)

    # Test 8: Test get_profile_summary returns human-readable summary
    def test_get_profile_summary(self, broker_profiles):
        """Test get_profile_summary returns formatted summary."""
        # Test per-share broker
        ib_summary = broker_profiles.get_profile_summary("interactive_brokers_retail")
        assert ib_summary["name"] == "Interactive Brokers Retail"
        assert ib_summary["type"] == "PER_SHARE"
        assert "$0.005/share" in ib_summary["rate"]
        assert ib_summary["min"] == "$1.00"

        # Test zero-commission broker
        rh_summary = broker_profiles.get_profile_summary("robinhood")
        assert rh_summary["name"] == "Robinhood"
        assert rh_summary["type"] == "FIXED"
        assert rh_summary["min"] == "$0"

    # Test 9: Test singleton get_broker_profiles function
    def test_singleton_get_broker_profiles(self):
        """Test singleton function returns same instance."""
        instance1 = get_broker_profiles()
        instance2 = get_broker_profiles()

        # Should return same instance
        assert instance1 is instance2

        # Should be functional
        config = instance1.get_profile("interactive_brokers_retail")
        assert config.broker_name == "Interactive Brokers Retail"

    # Test 10: Test legacy Interactive Brokers profile
    def test_legacy_interactive_brokers_profile(self, broker_profiles):
        """Test legacy Interactive Brokers profile for historical backtests."""
        config = broker_profiles.get_profile("interactive_brokers_legacy")

        assert config.commission_type == "PER_SHARE"
        assert config.commission_per_share == Decimal("0.01")
        assert config.min_commission == Decimal("1.00")
        assert config.broker_name == "Interactive Brokers (Legacy)"

    # Test 11: Test all profiles are valid CommissionConfig instances
    def test_all_profiles_valid(self, broker_profiles):
        """Test all broker profiles are valid CommissionConfig instances."""
        available = broker_profiles.list_available_profiles()

        for broker_name in available:
            config = broker_profiles.get_profile(broker_name)
            assert isinstance(config, CommissionConfig)
            assert config.broker_name is not None
            assert config.commission_type in ["PER_SHARE", "PERCENTAGE", "FIXED"]

    # Test 12: Test AC1 compliance (default is $0.005/share)
    def test_ac1_compliance_default_commission(self, broker_profiles):
        """Test AC1: Default commission is $0.005/share (Interactive Brokers Retail)."""
        default_config = broker_profiles.get_default_profile()

        # AC1: Commission $0.005/share (Interactive Brokers Retail as default)
        assert default_config.commission_per_share == Decimal("0.005")
        assert default_config.commission_type == "PER_SHARE"
        assert default_config.broker_name == "Interactive Brokers Retail"
