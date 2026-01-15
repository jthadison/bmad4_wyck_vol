"""
Unit tests for VolumeValidationStrategy base class (Story 18.6.1)

Tests:
------
- VolumeValidationStrategy abstract class cannot be instantiated
- Concrete strategies must implement required abstract methods
- create_result() helper method works correctly
- Logging helper methods work correctly
- get_threshold() default implementation works

Author: Story 18.6.1
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.models.validation import (
    StageValidationResult,
    ValidationContext,
    ValidationStatus,
    VolumeValidationConfig,
)
from src.signal_generator.validators.volume.base import VolumeValidationStrategy


class TestVolumeValidationStrategyABC:
    """Test VolumeValidationStrategy abstract class."""

    def test_abstract_class_cannot_be_instantiated(self):
        """Test VolumeValidationStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            VolumeValidationStrategy()

    def test_concrete_strategy_must_implement_pattern_type(self):
        """Test concrete strategy must implement pattern_type property."""

        class IncompleteStrategy(VolumeValidationStrategy):
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

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteStrategy()

    def test_concrete_strategy_must_implement_volume_threshold_type(self):
        """Test concrete strategy must implement volume_threshold_type property."""

        class IncompleteStrategy(VolumeValidationStrategy):
            @property
            def pattern_type(self) -> str:
                return "SPRING"

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

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteStrategy()

    def test_concrete_strategy_must_implement_default_stock_threshold(self):
        """Test concrete strategy must implement default_stock_threshold property."""

        class IncompleteStrategy(VolumeValidationStrategy):
            @property
            def pattern_type(self) -> str:
                return "SPRING"

            @property
            def volume_threshold_type(self) -> str:
                return "max"

            @property
            def default_forex_threshold(self) -> Decimal:
                return Decimal("0.85")

            def validate(
                self, context: ValidationContext, config: VolumeValidationConfig
            ) -> StageValidationResult:
                return self.create_result(ValidationStatus.PASS)

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteStrategy()

    def test_concrete_strategy_must_implement_default_forex_threshold(self):
        """Test concrete strategy must implement default_forex_threshold property."""

        class IncompleteStrategy(VolumeValidationStrategy):
            @property
            def pattern_type(self) -> str:
                return "SPRING"

            @property
            def volume_threshold_type(self) -> str:
                return "max"

            @property
            def default_stock_threshold(self) -> Decimal:
                return Decimal("0.7")

            def validate(
                self, context: ValidationContext, config: VolumeValidationConfig
            ) -> StageValidationResult:
                return self.create_result(ValidationStatus.PASS)

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteStrategy()

    def test_concrete_strategy_must_implement_validate(self):
        """Test concrete strategy must implement validate method."""

        class IncompleteStrategy(VolumeValidationStrategy):
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

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteStrategy()


class MockPattern:
    """Mock pattern for testing."""

    def __init__(self):
        self.id = uuid4()
        self.pattern_type = "SPRING"
        self.pattern_bar_timestamp = datetime.now(UTC)


class MockVolumeAnalysis:
    """Mock volume analysis for testing."""

    def __init__(self):
        self.volume_ratio = Decimal("0.65")
        self.bar = MagicMock(volume=1000)


class CompleteStrategy(VolumeValidationStrategy):
    """Complete concrete strategy for testing."""

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


class TestConcreteVolumeValidationStrategy:
    """Test concrete VolumeValidationStrategy implementation."""

    def test_concrete_strategy_can_be_instantiated(self):
        """Test concrete strategy with all methods can be instantiated."""
        strategy = CompleteStrategy()
        assert strategy.pattern_type == "SPRING"
        assert strategy.volume_threshold_type == "max"
        assert strategy.default_stock_threshold == Decimal("0.7")
        assert strategy.default_forex_threshold == Decimal("0.85")

    def test_class_constants(self):
        """Test class-level constants are set correctly."""
        strategy = CompleteStrategy()
        assert strategy.VALIDATOR_ID == "VOLUME_VALIDATOR"
        assert strategy.STAGE_NAME == "Volume"

    def test_validate_method(self):
        """Test validate method works correctly."""
        strategy = CompleteStrategy()
        context = ValidationContext(
            pattern=MockPattern(),
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=MockVolumeAnalysis(),
        )
        config = VolumeValidationConfig()

        result = strategy.validate(context, config)
        assert result.status == ValidationStatus.PASS

    def test_create_result_pass(self):
        """Test create_result() helper for PASS status."""
        strategy = CompleteStrategy()
        result = strategy.create_result(ValidationStatus.PASS)

        assert result.stage == "Volume"
        assert result.status == ValidationStatus.PASS
        assert result.reason is None
        assert result.validator_id == "VOLUME_VALIDATOR"
        assert result.metadata is None
        assert isinstance(result.timestamp, datetime)
        assert result.timestamp.tzinfo is not None

    def test_create_result_fail_with_reason(self):
        """Test create_result() helper for FAIL status with reason."""
        strategy = CompleteStrategy()
        result = strategy.create_result(
            ValidationStatus.FAIL,
            reason="Volume too high",
            metadata={"volume_ratio": 0.75, "threshold": 0.70},
        )

        assert result.status == ValidationStatus.FAIL
        assert result.reason == "Volume too high"
        assert result.metadata == {"volume_ratio": 0.75, "threshold": 0.70}

    def test_create_result_timestamp_is_utc(self):
        """Test create_result() creates UTC-aware timestamp."""
        strategy = CompleteStrategy()
        result = strategy.create_result(ValidationStatus.PASS)

        assert result.timestamp.tzinfo == UTC

    def test_get_threshold_returns_stock_for_stock(self):
        """Test get_threshold returns stock threshold for STOCK asset class."""
        strategy = CompleteStrategy()
        context = ValidationContext(
            pattern=MockPattern(),
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=MockVolumeAnalysis(),
            asset_class="STOCK",
        )
        config = VolumeValidationConfig()

        threshold = strategy.get_threshold(context, config)
        assert threshold == Decimal("0.7")

    def test_get_threshold_returns_forex_for_forex(self):
        """Test get_threshold returns forex threshold for FOREX asset class."""
        strategy = CompleteStrategy()
        context = ValidationContext(
            pattern=MockPattern(),
            symbol="EUR_USD",
            timeframe="1h",
            volume_analysis=MockVolumeAnalysis(),
            asset_class="FOREX",
        )
        config = VolumeValidationConfig()

        threshold = strategy.get_threshold(context, config)
        assert threshold == Decimal("0.85")


class TestVolumeValidationStrategyLogging:
    """Test logging helper methods."""

    def test_log_validation_start(self, caplog):
        """Test log_validation_start logs correctly."""
        strategy = CompleteStrategy()
        context = ValidationContext(
            pattern=MockPattern(),
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=MockVolumeAnalysis(),
        )

        # Should not raise any errors
        strategy.log_validation_start(context)

    def test_log_validation_passed(self, caplog):
        """Test log_validation_passed logs correctly."""
        strategy = CompleteStrategy()
        context = ValidationContext(
            pattern=MockPattern(),
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=MockVolumeAnalysis(),
        )

        # Should not raise any errors
        strategy.log_validation_passed(context, Decimal("0.65"), Decimal("0.70"))

    def test_log_validation_failed(self, caplog):
        """Test log_validation_failed logs correctly."""
        strategy = CompleteStrategy()
        context = ValidationContext(
            pattern=MockPattern(),
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=MockVolumeAnalysis(),
        )

        # Should not raise any errors
        strategy.log_validation_failed(context, Decimal("0.75"), Decimal("0.70"), "Volume too high")
