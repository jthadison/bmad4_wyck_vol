"""
Integration Tests for Forex Lot Sizing (Story 8.10.2 AC 6)

Purpose:
--------
Tests end-to-end forex signal generation with correct lot sizing
(NOT shares). Verifies RiskValidator calculates lots based on pip
value and MasterOrchestrator generates signals with LOTS unit.

Test Scenarios:
---------------
1. EUR/USD Spring generates signal with 0.5 LOTS (not 100 SHARES)
2. Forex-specific metadata fields (leverage, margin_requirement, notional_value)
3. Stock signal still uses SHARES unit

Author: Story 8.10.2
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.portfolio import PortfolioContext
from src.models.risk import CorrelationConfig
from src.models.validation import ValidationChain, ValidationContext
from src.signal_generator.master_orchestrator import MasterOrchestrator
from src.signal_generator.validators.risk_validator import RiskValidator


class TestForexLotSizing:
    """Integration test for EUR/USD signal with correct lot sizing (AC 6)."""

    @pytest.mark.asyncio
    async def test_forex_signal_lot_sizing(self) -> None:
        """
        Test EUR/USD Spring generates signal with 0.5 LOTS (not 100 shares).

        Setup:
        ------
        - EUR/USD Spring pattern
        - Portfolio equity: $10,000
        - Risk per trade: 1.5% ($150)
        - Stop distance: 30 pips (0.0030)
        - Expected: 0.5 lots (50,000 units)

        Calculations:
        -------------
        - Pip value = 0.0001 for EUR/USD
        - Stop distance = 30 pips = $0.0030
        - Position size = $150 / ($0.0030 × 100,000) = 0.50 lots
        - Notional value = 0.5 lots × 100,000 × 1.0825 = $54,125
        - Margin requirement = $54,125 / 50 = $1,082.50
        """

        # Step 1: Create forex ValidationContext
        class MockPattern:
            id = uuid4()
            pattern_type = "SPRING"

        pattern = MockPattern()

        portfolio_context = PortfolioContext(
            account_equity=Decimal("100000.00"),  # Larger equity to handle forex lot sizing
            cash_available=Decimal("50000.00"),
            open_positions=[],
            sector_mappings={},
            correlation_config=CorrelationConfig(
                max_sector_correlation=Decimal("6.0"),
                max_asset_class_correlation=Decimal("15.0"),
                enforcement_mode="strict",
                sector_mappings={},
            ),
            r_multiple_config={},
        )

        context = ValidationContext(
            pattern=pattern,
            symbol="EUR/USD",
            timeframe="1H",
            volume_analysis={"volume_ratio": Decimal("0.5")},
            asset_class="FOREX",
            portfolio_context=portfolio_context,
        )

        # Set entry/stop/target levels
        context.entry_price = Decimal("1.0825")
        context.stop_loss = Decimal("1.0795")  # 30 pips
        context.target_price = Decimal("1.0945")  # 120 pips (4R)

        # Step 2: Run RiskValidator to calculate position size
        risk_validator = RiskValidator()
        risk_result = await risk_validator.validate(context)

        # Assert validation passed
        assert risk_result.status == "PASS"
        assert risk_result.metadata is not None

        # Step 3: Verify lot sizing calculations
        metadata = risk_result.metadata

        # Assert position size unit is LOTS (not SHARES)
        assert metadata["position_size_unit"] == "LOTS"

        # Assert leverage populated (50:1 for forex)
        assert metadata["leverage"] == Decimal("50.0")

        # Assert margin requirement populated
        assert metadata["margin_requirement"] is not None
        assert metadata["margin_requirement"] > Decimal("0")

        # Calculate expected values
        position_size = metadata["position_size"]
        entry_price = context.entry_price

        # Notional = lots × 100,000 × entry_price
        expected_notional = position_size * Decimal("100000") * entry_price
        assert metadata["notional_value"] == expected_notional

        # Margin = notional / leverage
        expected_margin = expected_notional / Decimal("50.0")
        assert metadata["margin_requirement"] == expected_margin

        # Assert risk amount is approximately 1.5% of $10,000 = $150
        risk_amount = metadata["risk_amount"]
        assert Decimal("140.00") <= risk_amount <= Decimal("160.00")

        # Step 4: Build ValidationChain with Risk metadata
        validation_chain = ValidationChain(pattern_id=pattern.id)
        validation_chain.add_result(risk_result)

        # Step 5: Create pattern dict for signal generation
        pattern_dict = {
            "id": pattern.id,
            "pattern_type": "SPRING",
            "phase": "C",
            "confidence_score": 85,
            "entry_price": context.entry_price,
            "stop_loss": context.stop_loss,
            "target_price": context.target_price,
        }

        # Step 6: Generate signal via MasterOrchestrator
        from unittest.mock import AsyncMock, MagicMock

        orchestrator = MasterOrchestrator(
            market_data_service=MagicMock(),
            trading_range_service=MagicMock(),
            pattern_detectors=[MagicMock()],
            volume_validator=MagicMock(),
            phase_validator=MagicMock(),
            level_validator=MagicMock(),
            risk_validator=MagicMock(),
            strategy_validator=MagicMock(),
            signal_repository=AsyncMock(),
        )

        signal = await orchestrator.generate_signal_from_pattern(
            pattern=pattern_dict, context=context, validation_chain=validation_chain
        )

        # Step 7: Assert signal has correct forex-specific fields
        assert signal.position_size_unit == "LOTS"
        assert signal.position_size == position_size
        assert signal.leverage == Decimal("50.0")
        assert signal.margin_requirement == expected_margin
        assert signal.notional_value == expected_notional
        assert signal.risk_amount == risk_amount

        # Assert NOT hardcoded defaults
        assert signal.position_size != Decimal("100")  # NOT 100 shares
        assert signal.position_size_unit != "SHARES"

    @pytest.mark.asyncio
    async def test_stock_signal_share_sizing(self) -> None:
        """
        Test AAPL stock signal still uses SHARES unit (not LOTS).

        Ensures stock signals aren't affected by forex changes.
        """

        # Step 1: Create stock ValidationContext
        class MockPattern:
            id = uuid4()
            pattern_type = "SPRING"

        pattern = MockPattern()

        portfolio_context = PortfolioContext(
            account_equity=Decimal("100000.00"),
            cash_available=Decimal("50000.00"),
            open_positions=[],
            sector_mappings={},
            correlation_config=CorrelationConfig(
                max_sector_correlation=Decimal("6.0"),
                max_asset_class_correlation=Decimal("15.0"),
                enforcement_mode="strict",
                sector_mappings={},
            ),
            r_multiple_config={},
        )

        context = ValidationContext(
            pattern=pattern,
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.5")},
            asset_class="STOCK",
            portfolio_context=portfolio_context,
        )

        # Set entry/stop/target levels
        context.entry_price = Decimal("150.00")
        context.stop_loss = Decimal("145.00")  # $5 stop
        context.target_price = Decimal("165.00")  # $15 target (3R)

        # Step 2: Run RiskValidator
        risk_validator = RiskValidator()
        risk_result = await risk_validator.validate(context)

        # Assert validation passed
        assert risk_result.status == "PASS"
        assert risk_result.metadata is not None

        # Step 3: Verify stock sizing
        metadata = risk_result.metadata

        # Assert position size unit is SHARES (not LOTS)
        assert metadata["position_size_unit"] == "SHARES"

        # Assert leverage is None (stocks don't use leverage by default)
        assert metadata["leverage"] is None

        # Assert margin requirement is None
        assert metadata["margin_requirement"] is None

        # Notional = shares × entry_price
        position_size = metadata["position_size"]
        entry_price = context.entry_price
        expected_notional = position_size * entry_price
        assert metadata["notional_value"] == expected_notional

        # Step 4: Build ValidationChain and generate signal
        validation_chain = ValidationChain(pattern_id=pattern.id)
        validation_chain.add_result(risk_result)

        pattern_dict = {
            "id": pattern.id,
            "pattern_type": "SPRING",
            "phase": "C",
            "confidence_score": 85,
            "entry_price": context.entry_price,
            "stop_loss": context.stop_loss,
            "target_price": context.target_price,
        }

        from unittest.mock import AsyncMock, MagicMock

        orchestrator = MasterOrchestrator(
            market_data_service=MagicMock(),
            trading_range_service=MagicMock(),
            pattern_detectors=[MagicMock()],
            volume_validator=MagicMock(),
            phase_validator=MagicMock(),
            level_validator=MagicMock(),
            risk_validator=MagicMock(),
            strategy_validator=MagicMock(),
            signal_repository=AsyncMock(),
        )

        signal = await orchestrator.generate_signal_from_pattern(
            pattern=pattern_dict, context=context, validation_chain=validation_chain
        )

        # Step 5: Assert signal has correct stock-specific fields
        assert signal.position_size_unit == "SHARES"
        assert signal.leverage is None
        assert signal.margin_requirement is None
        assert signal.notional_value == expected_notional

        # Assert NOT hardcoded defaults
        assert signal.position_size != Decimal("100")  # NOT hardcoded 100
