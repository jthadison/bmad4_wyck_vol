"""
Unit Tests for Engine Package Interfaces (Story 18.9.1)

Tests for protocol definitions and EngineConfig dataclass.
Validates that protocols can be implemented and config validation works.

Author: Story 18.9.1
"""

from decimal import Decimal
from typing import Optional

import pytest

from src.backtesting.engine import CostModel, EngineConfig, SignalDetector
from src.models.backtest import BacktestOrder
from src.models.ohlcv import OHLCVBar


class TestEngineConfig:
    """Tests for EngineConfig dataclass."""

    def test_default_values(self):
        """AC4: EngineConfig has sensible defaults."""
        config = EngineConfig()

        assert config.initial_capital == Decimal("100000")
        assert config.max_position_size == Decimal("0.02")
        assert config.enable_cost_model is True
        assert config.risk_per_trade == Decimal("0.02")
        assert config.max_open_positions == 5

    def test_custom_values(self):
        """AC4: EngineConfig accepts custom values."""
        config = EngineConfig(
            initial_capital=Decimal("50000"),
            max_position_size=Decimal("0.05"),
            enable_cost_model=False,
            risk_per_trade=Decimal("0.01"),
            max_open_positions=3,
        )

        assert config.initial_capital == Decimal("50000")
        assert config.max_position_size == Decimal("0.05")
        assert config.enable_cost_model is False
        assert config.risk_per_trade == Decimal("0.01")
        assert config.max_open_positions == 3

    def test_initial_capital_must_be_positive(self):
        """AC4: EngineConfig validates initial_capital > 0."""
        with pytest.raises(ValueError, match="initial_capital must be positive"):
            EngineConfig(initial_capital=Decimal("0"))

        with pytest.raises(ValueError, match="initial_capital must be positive"):
            EngineConfig(initial_capital=Decimal("-1000"))

    def test_max_position_size_must_be_in_valid_range(self):
        """AC4: EngineConfig validates 0 < max_position_size <= 1."""
        with pytest.raises(ValueError, match="max_position_size must be in"):
            EngineConfig(max_position_size=Decimal("0"))

        with pytest.raises(ValueError, match="max_position_size must be in"):
            EngineConfig(max_position_size=Decimal("1.5"))

        # Edge case: exactly 1.0 should be valid
        config = EngineConfig(max_position_size=Decimal("1.0"))
        assert config.max_position_size == Decimal("1.0")

    def test_risk_per_trade_must_be_in_valid_range(self):
        """AC4: EngineConfig validates 0 < risk_per_trade <= 1."""
        with pytest.raises(ValueError, match="risk_per_trade must be in"):
            EngineConfig(risk_per_trade=Decimal("0"))

        with pytest.raises(ValueError, match="risk_per_trade must be in"):
            EngineConfig(risk_per_trade=Decimal("1.1"))

    def test_max_open_positions_must_be_in_valid_range(self):
        """AC4: EngineConfig validates 1 <= max_open_positions <= 100."""
        # Test lower bound
        with pytest.raises(ValueError, match="max_open_positions must be in"):
            EngineConfig(max_open_positions=0)

        with pytest.raises(ValueError, match="max_open_positions must be in"):
            EngineConfig(max_open_positions=-1)

        # Test upper bound
        with pytest.raises(ValueError, match="max_open_positions must be in"):
            EngineConfig(max_open_positions=101)

        # Edge cases: exactly 1 and 100 should be valid
        config_min = EngineConfig(max_open_positions=1)
        assert config_min.max_open_positions == 1

        config_max = EngineConfig(max_open_positions=100)
        assert config_max.max_open_positions == 100


class TestSignalDetectorProtocol:
    """Tests for SignalDetector protocol."""

    def test_protocol_can_be_implemented(self):
        """AC2: SignalDetector protocol can be implemented."""

        class MockSignalDetector:
            """Mock implementation of SignalDetector."""

            def detect(self, bars: list[OHLCVBar], index: int) -> Optional[dict]:
                if index >= 5 and bars[index].volume_ratio > Decimal("1.5"):
                    return {"type": "SPRING", "confidence": 0.85}
                return None

        detector = MockSignalDetector()

        # Verify it satisfies the protocol
        assert hasattr(detector, "detect")
        assert callable(detector.detect)

        # Verify it works
        result = detector.detect([], 0)
        assert result is None

    def test_protocol_type_checking(self):
        """AC2: SignalDetector protocol provides type hints."""

        def use_detector(detector: SignalDetector) -> None:
            """Function that accepts any SignalDetector."""
            pass

        class ValidDetector:
            def detect(self, bars, index):
                return None

        # This should not raise - ValidDetector has correct interface
        detector = ValidDetector()
        use_detector(detector)


class TestCostModelProtocol:
    """Tests for CostModel protocol."""

    def test_protocol_can_be_implemented(self):
        """AC3: CostModel protocol can be implemented."""

        class MockCostModel:
            """Mock implementation of CostModel."""

            def calculate_commission(self, order: BacktestOrder) -> Decimal:
                # $0.005 per share, min $1.00
                return max(
                    Decimal("1.00"),
                    Decimal(order.quantity) * Decimal("0.005"),
                )

            def calculate_slippage(self, order: BacktestOrder, bar: OHLCVBar) -> Decimal:
                # 0.02% of price
                return bar.close * Decimal("0.0002")

        cost_model = MockCostModel()

        # Verify it satisfies the protocol
        assert hasattr(cost_model, "calculate_commission")
        assert hasattr(cost_model, "calculate_slippage")
        assert callable(cost_model.calculate_commission)
        assert callable(cost_model.calculate_slippage)

    def test_protocol_type_checking(self):
        """AC3: CostModel protocol provides type hints."""

        def use_cost_model(model: CostModel) -> None:
            """Function that accepts any CostModel."""
            pass

        class ValidCostModel:
            def calculate_commission(self, order):
                return Decimal("1.00")

            def calculate_slippage(self, order, bar):
                return Decimal("0.10")

        # This should not raise - ValidCostModel has correct interface
        model = ValidCostModel()
        use_cost_model(model)


class TestPublicExports:
    """Tests for package public exports."""

    def test_all_exports_available(self):
        """AC5: Package __init__.py exports all public interfaces."""
        from src.backtesting.engine import (
            BacktestEngine,
            CostModel,
            EngineConfig,
            SignalDetector,
        )

        # All exports should be importable
        assert EngineConfig is not None
        assert SignalDetector is not None
        assert CostModel is not None
        assert BacktestEngine is not None

    def test_exports_match_all_list(self):
        """AC5: Exports match __all__ list."""
        import src.backtesting.engine as engine_module

        expected_exports = {
            "EngineConfig",
            "SignalDetector",
            "CostModel",
            "BacktestEngine",
            "UnifiedBacktestEngine",  # Story 18.9.2
        }
        actual_exports = set(engine_module.__all__)

        assert actual_exports == expected_exports

    def test_backtest_engine_backward_compatibility(self):
        """Existing imports of BacktestEngine still work."""
        from src.backtesting.engine import BacktestEngine

        # BacktestEngine should be the preview engine class
        assert hasattr(BacktestEngine, "run_preview")
        assert hasattr(BacktestEngine, "cancel")
