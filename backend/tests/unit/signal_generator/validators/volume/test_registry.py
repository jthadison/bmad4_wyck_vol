"""
Unit tests for VolumeStrategyRegistry (Story 18.6.1)

Tests:
------
- Strategy registration and retrieval
- Pattern type lookup (case-insensitive)
- Registry clearing and counting
- Duplicate registration handling

Author: Story 18.6.1
"""

from decimal import Decimal

import pytest

from src.models.validation import (
    StageValidationResult,
    ValidationContext,
    ValidationStatus,
    VolumeValidationConfig,
)
from src.signal_generator.validators.volume.base import VolumeValidationStrategy
from src.signal_generator.validators.volume.registry import VolumeStrategyRegistry


class MockSpringStrategy(VolumeValidationStrategy):
    """Mock Spring strategy for testing."""

    @property
    def pattern_type(self) -> str:
        return "SPRING"

    @property
    def volume_threshold_type(self) -> str:
        return "max"

    @property
    def default_stock_threshold(self) -> Decimal:
        return Decimal("0.7")

    @property
    def default_forex_threshold(self) -> Decimal:
        return Decimal("0.85")

    def validate(
        self, context: ValidationContext, config: VolumeValidationConfig
    ) -> StageValidationResult:
        return self.create_result(ValidationStatus.PASS)


class MockSOSStrategy(VolumeValidationStrategy):
    """Mock SOS strategy for testing."""

    @property
    def pattern_type(self) -> str:
        return "SOS"

    @property
    def volume_threshold_type(self) -> str:
        return "min"

    @property
    def default_stock_threshold(self) -> Decimal:
        return Decimal("1.5")

    @property
    def default_forex_threshold(self) -> Decimal:
        return Decimal("1.8")

    def validate(
        self, context: ValidationContext, config: VolumeValidationConfig
    ) -> StageValidationResult:
        return self.create_result(ValidationStatus.PASS)


class MockAlternateSpringStrategy(VolumeValidationStrategy):
    """Alternative Spring strategy for testing replacement behavior."""

    @property
    def pattern_type(self) -> str:
        return "SPRING"

    @property
    def volume_threshold_type(self) -> str:
        return "max"

    @property
    def default_stock_threshold(self) -> Decimal:
        return Decimal("0.6")  # Different threshold

    @property
    def default_forex_threshold(self) -> Decimal:
        return Decimal("0.80")

    def validate(
        self, context: ValidationContext, config: VolumeValidationConfig
    ) -> StageValidationResult:
        return self.create_result(ValidationStatus.PASS)


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear registry before and after each test."""
    VolumeStrategyRegistry.clear()
    yield
    VolumeStrategyRegistry.clear()


class TestVolumeStrategyRegistry:
    """Test VolumeStrategyRegistry class."""

    def test_registry_starts_empty(self):
        """Test registry is empty at start."""
        assert VolumeStrategyRegistry.count() == 0
        assert VolumeStrategyRegistry.get_registered_patterns() == []

    def test_register_single_strategy(self):
        """Test registering a single strategy."""
        strategy = MockSpringStrategy()
        VolumeStrategyRegistry.register(strategy)

        assert VolumeStrategyRegistry.count() == 1
        assert VolumeStrategyRegistry.has("SPRING")
        assert VolumeStrategyRegistry.get("SPRING") is strategy

    def test_register_multiple_strategies(self):
        """Test registering multiple strategies."""
        spring = MockSpringStrategy()
        sos = MockSOSStrategy()

        VolumeStrategyRegistry.register(spring)
        VolumeStrategyRegistry.register(sos)

        assert VolumeStrategyRegistry.count() == 2
        assert VolumeStrategyRegistry.has("SPRING")
        assert VolumeStrategyRegistry.has("SOS")
        assert VolumeStrategyRegistry.get("SPRING") is spring
        assert VolumeStrategyRegistry.get("SOS") is sos

    def test_get_nonexistent_pattern_returns_none(self):
        """Test getting a non-registered pattern returns None."""
        assert VolumeStrategyRegistry.get("NONEXISTENT") is None

    def test_has_returns_false_for_nonexistent(self):
        """Test has() returns False for non-registered patterns."""
        assert not VolumeStrategyRegistry.has("NONEXISTENT")

    def test_get_is_case_insensitive(self):
        """Test get() is case-insensitive."""
        strategy = MockSpringStrategy()
        VolumeStrategyRegistry.register(strategy)

        assert VolumeStrategyRegistry.get("SPRING") is strategy
        assert VolumeStrategyRegistry.get("spring") is strategy
        assert VolumeStrategyRegistry.get("Spring") is strategy
        assert VolumeStrategyRegistry.get("sPrInG") is strategy

    def test_has_is_case_insensitive(self):
        """Test has() is case-insensitive."""
        VolumeStrategyRegistry.register(MockSpringStrategy())

        assert VolumeStrategyRegistry.has("SPRING")
        assert VolumeStrategyRegistry.has("spring")
        assert VolumeStrategyRegistry.has("Spring")

    def test_register_replaces_existing_strategy(self):
        """Test registering same pattern type replaces existing strategy."""
        original = MockSpringStrategy()
        replacement = MockAlternateSpringStrategy()

        VolumeStrategyRegistry.register(original)
        assert VolumeStrategyRegistry.get("SPRING") is original
        assert VolumeStrategyRegistry.get("SPRING").default_stock_threshold == Decimal("0.7")

        VolumeStrategyRegistry.register(replacement)
        assert VolumeStrategyRegistry.count() == 1  # Still only one
        assert VolumeStrategyRegistry.get("SPRING") is replacement
        assert VolumeStrategyRegistry.get("SPRING").default_stock_threshold == Decimal("0.6")

    def test_get_all_returns_copy(self):
        """Test get_all() returns a copy of strategies dict."""
        spring = MockSpringStrategy()
        sos = MockSOSStrategy()

        VolumeStrategyRegistry.register(spring)
        VolumeStrategyRegistry.register(sos)

        all_strategies = VolumeStrategyRegistry.get_all()
        assert len(all_strategies) == 2
        assert all_strategies["SPRING"] is spring
        assert all_strategies["SOS"] is sos

        # Modifying returned dict should not affect registry
        all_strategies["TEST"] = MockSpringStrategy()
        assert VolumeStrategyRegistry.count() == 2

    def test_get_registered_patterns(self):
        """Test get_registered_patterns() returns list of pattern types."""
        VolumeStrategyRegistry.register(MockSpringStrategy())
        VolumeStrategyRegistry.register(MockSOSStrategy())

        patterns = VolumeStrategyRegistry.get_registered_patterns()
        assert sorted(patterns) == ["SOS", "SPRING"]

    def test_clear_removes_all_strategies(self):
        """Test clear() removes all registered strategies."""
        VolumeStrategyRegistry.register(MockSpringStrategy())
        VolumeStrategyRegistry.register(MockSOSStrategy())

        assert VolumeStrategyRegistry.count() == 2

        VolumeStrategyRegistry.clear()

        assert VolumeStrategyRegistry.count() == 0
        assert VolumeStrategyRegistry.get("SPRING") is None
        assert VolumeStrategyRegistry.get("SOS") is None

    def test_count_returns_correct_count(self):
        """Test count() returns correct number of strategies."""
        assert VolumeStrategyRegistry.count() == 0

        VolumeStrategyRegistry.register(MockSpringStrategy())
        assert VolumeStrategyRegistry.count() == 1

        VolumeStrategyRegistry.register(MockSOSStrategy())
        assert VolumeStrategyRegistry.count() == 2

        VolumeStrategyRegistry.clear()
        assert VolumeStrategyRegistry.count() == 0


class TestVolumeStrategyRegistryIntegration:
    """Integration tests for VolumeStrategyRegistry with validation."""

    def test_retrieved_strategy_validates_correctly(self):
        """Test retrieved strategy can perform validation."""
        from datetime import UTC, datetime
        from unittest.mock import MagicMock
        from uuid import uuid4

        VolumeStrategyRegistry.register(MockSpringStrategy())

        # Create mock context
        pattern = MagicMock()
        pattern.id = uuid4()
        pattern.pattern_type = "SPRING"
        pattern.pattern_bar_timestamp = datetime.now(UTC)

        volume_analysis = MagicMock()
        volume_analysis.volume_ratio = Decimal("0.65")
        volume_analysis.bar = MagicMock(volume=1000)

        context = ValidationContext(
            pattern=pattern,
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=volume_analysis,
        )
        config = VolumeValidationConfig()

        # Get strategy from registry and validate
        strategy = VolumeStrategyRegistry.get("SPRING")
        assert strategy is not None

        result = strategy.validate(context, config)
        assert result.status == ValidationStatus.PASS
        assert result.stage == "Volume"
        assert result.validator_id == "VOLUME_VALIDATOR"
