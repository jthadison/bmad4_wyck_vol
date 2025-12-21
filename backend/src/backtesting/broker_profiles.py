"""
Preset Broker Commission Profiles (Story 12.5 Task 11).

Provides pre-configured commission profiles for common brokers to simplify
backtest configuration and ensure realistic cost modeling.

AC1: Commission $0.005/share (Interactive Brokers Retail as default)

Author: Story 12.5 Task 11
"""

from decimal import Decimal

import structlog

from src.models.backtest import CommissionConfig

logger = structlog.get_logger(__name__)


class BrokerProfiles:
    """
    Pre-configured broker commission profiles for common US brokers.

    Provides realistic commission configurations for popular brokers
    to ensure accurate backtest cost modeling.

    Methods:
        get_profile: Get commission config for a specific broker
        list_available_profiles: List all available broker names
        get_default_profile: Get Interactive Brokers Retail (most common)

    Example:
        profiles = BrokerProfiles()

        # Use Interactive Brokers Retail (default)
        ib_config = profiles.get_profile("interactive_brokers_retail")
        # commission_type = "PER_SHARE", $0.005/share

        # Use Robinhood (commission-free)
        rh_config = profiles.get_profile("robinhood")
        # commission_type = "FIXED", $0/trade

        # Use for backtest
        backtest_config = BacktestConfig(commission_config=ib_config)

    Author: Story 12.5 Task 11
    """

    def __init__(self):
        """
        Initialize broker profiles.

        Subtask 11.1: Define commission profiles for common brokers
        Subtask 11.2: Include min/max commission caps
        Subtask 11.3: Add broker metadata (name, description)

        Author: Story 12.5 Subtask 11.1-11.3
        """
        self._profiles: dict[str, CommissionConfig] = {}
        self._initialize_profiles()

    def _initialize_profiles(self):
        """
        Initialize all broker commission profiles.

        Subtask 11.4: Create profiles for major US brokers

        Brokers included:
        1. Interactive Brokers Retail (IBKR) - Most common for active traders
        2. Interactive Brokers Pro (IBKR Pro) - Lower rates for high volume
        3. TD Ameritrade - Zero commission retail broker
        4. Robinhood - Commission-free trading
        5. E*TRADE - Zero commission retail broker
        6. Fidelity - Zero commission retail broker
        7. Charles Schwab - Zero commission retail broker

        Author: Story 12.5 Subtask 11.4
        """
        # 1. Interactive Brokers Retail (Default)
        # Most common for serious traders
        # $0.005/share, $1 min, $1% of trade value max
        self._profiles["interactive_brokers_retail"] = CommissionConfig(
            commission_type="PER_SHARE",
            commission_per_share=Decimal("0.005"),
            commission_percentage=Decimal("0"),
            fixed_commission_per_trade=Decimal("0"),
            min_commission=Decimal("1.00"),
            max_commission=Decimal("0"),  # 1% of trade value (applied in calculator)
            broker_name="Interactive Brokers Retail",
        )

        # 2. Interactive Brokers Pro
        # For high-volume traders
        # $0.0035/share, $0.35 min, no max
        self._profiles["interactive_brokers_pro"] = CommissionConfig(
            commission_type="PER_SHARE",
            commission_per_share=Decimal("0.0035"),
            commission_percentage=Decimal("0"),
            fixed_commission_per_trade=Decimal("0"),
            min_commission=Decimal("0.35"),
            max_commission=None,
            broker_name="Interactive Brokers Pro",
        )

        # 3. TD Ameritrade
        # Zero commission for stocks and ETFs (since 2019)
        self._profiles["td_ameritrade"] = CommissionConfig(
            commission_type="FIXED",
            commission_per_share=Decimal("0"),
            commission_percentage=Decimal("0"),
            fixed_commission_per_trade=Decimal("0"),
            min_commission=Decimal("0"),
            max_commission=None,
            broker_name="TD Ameritrade",
        )

        # 4. Robinhood
        # Commission-free trading
        self._profiles["robinhood"] = CommissionConfig(
            commission_type="FIXED",
            commission_per_share=Decimal("0"),
            commission_percentage=Decimal("0"),
            fixed_commission_per_trade=Decimal("0"),
            min_commission=Decimal("0"),
            max_commission=None,
            broker_name="Robinhood",
        )

        # 5. E*TRADE
        # Zero commission for stocks and ETFs
        self._profiles["etrade"] = CommissionConfig(
            commission_type="FIXED",
            commission_per_share=Decimal("0"),
            commission_percentage=Decimal("0"),
            fixed_commission_per_trade=Decimal("0"),
            min_commission=Decimal("0"),
            max_commission=None,
            broker_name="E*TRADE",
        )

        # 6. Fidelity
        # Zero commission for stocks and ETFs
        self._profiles["fidelity"] = CommissionConfig(
            commission_type="FIXED",
            commission_per_share=Decimal("0"),
            commission_percentage=Decimal("0"),
            fixed_commission_per_trade=Decimal("0"),
            min_commission=Decimal("0"),
            max_commission=None,
            broker_name="Fidelity",
        )

        # 7. Charles Schwab
        # Zero commission for stocks and ETFs
        self._profiles["charles_schwab"] = CommissionConfig(
            commission_type="FIXED",
            commission_per_share=Decimal("0"),
            commission_percentage=Decimal("0"),
            fixed_commission_per_trade=Decimal("0"),
            min_commission=Decimal("0"),
            max_commission=None,
            broker_name="Charles Schwab",
        )

        # 8. Legacy Interactive Brokers (pre-2019, for historical backtests)
        # $0.01/share, $1 min, $1% max
        self._profiles["interactive_brokers_legacy"] = CommissionConfig(
            commission_type="PER_SHARE",
            commission_per_share=Decimal("0.01"),
            commission_percentage=Decimal("0"),
            fixed_commission_per_trade=Decimal("0"),
            min_commission=Decimal("1.00"),
            max_commission=None,
            broker_name="Interactive Brokers (Legacy)",
        )

        logger.info("Broker profiles initialized", total_profiles=len(self._profiles))

    def get_profile(self, broker_name: str) -> CommissionConfig:
        """
        Get commission configuration for a specific broker.

        Subtask 11.5: Return CommissionConfig for requested broker
        Subtask 11.5: Raise error if broker not found

        Args:
            broker_name: Broker identifier (lowercase with underscores)
                         e.g., "interactive_brokers_retail", "robinhood"

        Returns:
            CommissionConfig for the requested broker

        Raises:
            ValueError: If broker_name is not found

        Example:
            profiles = BrokerProfiles()
            config = profiles.get_profile("interactive_brokers_retail")
            # config.commission_per_share = Decimal("0.005")

        Author: Story 12.5 Subtask 11.5
        """
        if broker_name not in self._profiles:
            available = ", ".join(self.list_available_profiles())
            error_msg = (
                f"Unknown broker profile: '{broker_name}'. " f"Available profiles: {available}"
            )
            logger.error("Broker profile not found", broker_name=broker_name)
            raise ValueError(error_msg)

        config = self._profiles[broker_name]
        logger.debug(
            "Broker profile retrieved",
            broker_name=broker_name,
            commission_type=config.commission_type,
        )
        return config

    def list_available_profiles(self) -> list[str]:
        """
        List all available broker profile names.

        Subtask 11.6: Return sorted list of broker names

        Returns:
            List of broker profile identifiers

        Example:
            profiles = BrokerProfiles()
            available = profiles.list_available_profiles()
            # ['charles_schwab', 'etrade', 'fidelity', ...]

        Author: Story 12.5 Subtask 11.6
        """
        return sorted(self._profiles.keys())

    def get_default_profile(self) -> CommissionConfig:
        """
        Get default broker profile (Interactive Brokers Retail).

        Subtask 11.7: Return Interactive Brokers Retail as default

        Interactive Brokers Retail is the default because:
        - Most commonly used by active/professional traders
        - Has actual commission costs (unlike zero-commission brokers)
        - Provides realistic cost modeling for backtests
        - Matches AC1 requirement ($0.005/share)

        Returns:
            CommissionConfig for Interactive Brokers Retail

        Example:
            profiles = BrokerProfiles()
            default = profiles.get_default_profile()
            # default.broker_name = "Interactive Brokers Retail"

        Author: Story 12.5 Subtask 11.7
        """
        return self.get_profile("interactive_brokers_retail")

    def get_profile_summary(self, broker_name: str) -> dict[str, str]:
        """
        Get human-readable summary of a broker profile.

        Args:
            broker_name: Broker identifier

        Returns:
            Dictionary with profile summary

        Example:
            profiles = BrokerProfiles()
            summary = profiles.get_profile_summary("interactive_brokers_retail")
            # {
            #     "name": "Interactive Brokers Retail",
            #     "type": "PER_SHARE",
            #     "rate": "$0.005/share",
            #     "min": "$1.00",
            #     "max": "None"
            # }

        Author: Story 12.5 (helper method)
        """
        config = self.get_profile(broker_name)

        summary = {
            "name": config.broker_name,
            "type": config.commission_type,
        }

        if config.commission_type == "PER_SHARE":
            summary["rate"] = f"${config.commission_per_share}/share"
        elif config.commission_type == "PERCENTAGE":
            summary["rate"] = f"{float(config.commission_percentage) * 100}%"
        else:  # FIXED
            summary["rate"] = f"${config.fixed_commission_per_trade}/trade"

        summary["min"] = f"${config.min_commission}"
        summary["max"] = f"${config.max_commission}" if config.max_commission else "None"

        return summary


# Singleton instance for convenient access
_broker_profiles_instance = None


def get_broker_profiles() -> BrokerProfiles:
    """
    Get singleton BrokerProfiles instance.

    Returns:
        Singleton BrokerProfiles instance

    Example:
        from src.backtesting.broker_profiles import get_broker_profiles

        profiles = get_broker_profiles()
        config = profiles.get_profile("interactive_brokers_retail")

    Author: Story 12.5 (convenience function)
    """
    global _broker_profiles_instance
    if _broker_profiles_instance is None:
        _broker_profiles_instance = BrokerProfiles()
    return _broker_profiles_instance
