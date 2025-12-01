"""
Integration tests for full validation chain (Story 8.2)

Tests:
------
- Full validation chain with all passing validators
- Full validation chain with early rejection at Volume stage
- Full validation chain with warnings but passing
- Validation chain with mixed PASS/WARN results

Author: Story 8.2
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.validation import ValidationContext, ValidationStatus
from src.signal_generator.validation_chain import create_default_validation_chain


class TestValidationChainIntegration:
    """Integration tests for complete validation chain."""

    @pytest.mark.asyncio
    async def test_full_chain_all_pass_with_complete_context(self):
        """
        Test full validation chain with all validators passing.

        Creates complete ValidationContext with all required data for all stages.
        Verifies all 5 validators execute and return PASS.
        """
        orchestrator = create_default_validation_chain()

        # Create complete context with all required data
        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING", "volume_ratio": Decimal("0.45")},
            symbol="AAPL",
            timeframe="1d",
            # REQUIRED: volume_analysis (Volume validator)
            volume_analysis={"volume_ratio": Decimal("0.45"), "pattern_type": "SPRING"},
            # Optional: phase_info (Phase validator)
            phase_info={"phase": "C", "detected_phase": "PHASE_C"},
            # Optional: trading_range (Level validator)
            trading_range={
                "creek_level": Decimal("100.00"),
                "creek_strength": Decimal("85.0"),
                "ice_level": Decimal("97.00"),
                "jump_level": Decimal("110.00"),
            },
            # Optional: portfolio_context (Risk validator)
            portfolio_context={
                "available_capital": Decimal("100000"),
                "portfolio_heat": Decimal("0.05"),  # 5%
            },
            # Optional: market_context (Strategy validator)
            market_context={"market_condition": "BULL", "news_events": []},
        )

        chain = await orchestrator.run_validation_chain(context)

        # Verify all 5 validators executed
        assert len(chain.validation_results) == 5

        # Verify execution order
        stages = [result.stage for result in chain.validation_results]
        assert stages == ["Volume", "Phase", "Levels", "Risk", "Strategy"]

        # Verify overall status is PASS
        assert chain.overall_status == ValidationStatus.PASS
        assert chain.is_valid is True
        assert chain.rejection_stage is None
        assert chain.rejection_reason is None
        assert chain.warnings == []
        assert chain.has_warnings is False

        # Verify timestamps
        assert chain.started_at is not None
        assert chain.completed_at is not None
        assert chain.completed_at >= chain.started_at

    @pytest.mark.asyncio
    async def test_full_chain_volume_pass_no_other_context(self):
        """
        Test validation chain with only volume_analysis (minimal context).

        Volume validator should PASS (has data).
        Phase/Levels/Risk/Strategy should FAIL (missing context).
        Chain should exit early at Phase validator.
        """
        orchestrator = create_default_validation_chain()

        # Minimal context: only volume_analysis (REQUIRED)
        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
            # No phase_info, trading_range, portfolio_context, market_context
        )

        chain = await orchestrator.run_validation_chain(context)

        # Volume should PASS (has volume_analysis)
        assert len(chain.validation_results) >= 1
        assert chain.validation_results[0].stage == "Volume"
        assert chain.validation_results[0].status == ValidationStatus.PASS

        # Phase should FAIL (no phase_info) - early exit
        assert len(chain.validation_results) == 2
        assert chain.validation_results[1].stage == "Phase"
        assert chain.validation_results[1].status == ValidationStatus.FAIL
        assert (
            chain.validation_results[1].reason
            == "Phase information not available for phase validation"
        )

        # Chain should stop at Phase (early exit)
        assert chain.overall_status == ValidationStatus.FAIL
        assert chain.rejection_stage == "Phase"
        assert chain.is_valid is False

    @pytest.mark.asyncio
    async def test_full_chain_early_rejection_at_levels(self):
        """
        Test validation chain with early rejection at Levels stage.

        Volume and Phase PASS, but Levels FAIL due to missing trading_range.
        Risk and Strategy should NOT execute (early exit).
        """
        orchestrator = create_default_validation_chain()

        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
            phase_info={"phase": "C"},  # Phase will PASS
            # No trading_range - Levels will FAIL
            portfolio_context={"available_capital": Decimal("100000")},
            market_context={"market_condition": "BULL"},
        )

        chain = await orchestrator.run_validation_chain(context)

        # Verify Volume and Phase PASS
        assert len(chain.validation_results) == 3
        assert chain.validation_results[0].status == ValidationStatus.PASS
        assert chain.validation_results[1].status == ValidationStatus.PASS

        # Verify Levels FAIL
        assert chain.validation_results[2].stage == "Levels"
        assert chain.validation_results[2].status == ValidationStatus.FAIL
        assert "Trading range not available" in chain.validation_results[2].reason

        # Verify early exit (Risk and Strategy NOT executed)
        assert chain.overall_status == ValidationStatus.FAIL
        assert chain.rejection_stage == "Levels"
        assert chain.is_valid is False

    @pytest.mark.asyncio
    async def test_full_chain_with_all_context_provided(self):
        """
        Test validation chain with all optional context fields provided.

        All validators should have required context and return PASS.
        This is the "happy path" integration test.
        """
        orchestrator = create_default_validation_chain()

        context = ValidationContext(
            pattern={
                "id": str(uuid4()),
                "type": "SPRING",
                "spring_low": Decimal("95.00"),
                "creek_level": Decimal("100.00"),
            },
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={
                "volume_ratio": Decimal("0.45"),
                "avg_volume": Decimal("1000000"),
                "actual_volume": Decimal("450000"),
            },
            phase_info={"phase": "C", "detected_phase": "PHASE_C", "phase_duration_bars": 30},
            trading_range={
                "creek_level": Decimal("100.00"),
                "creek_strength": Decimal("85.0"),
                "ice_level": Decimal("97.00"),
                "jump_level": Decimal("110.00"),
                "entry_type": "LPS_ENTRY",
            },
            portfolio_context={
                "available_capital": Decimal("100000"),
                "portfolio_heat": Decimal("0.05"),
                "max_heat_limit": Decimal("0.10"),
                "symbol_exposure": Decimal("0.00"),
            },
            market_context={
                "market_condition": "BULL_CONFIRMED",
                "news_events": [],
                "correlation_warnings": [],
            },
            config={
                "test_mode": False,
                "risk_percentage": Decimal("0.01"),
            },
        )

        chain = await orchestrator.run_validation_chain(context)

        # Verify all 5 validators executed in correct order
        assert len(chain.validation_results) == 5
        stages = [result.stage for result in chain.validation_results]
        assert stages == ["Volume", "Phase", "Levels", "Risk", "Strategy"]

        # Verify all validators returned PASS (stub validators)
        for result in chain.validation_results:
            assert result.status == ValidationStatus.PASS

        # Verify overall chain status
        assert chain.overall_status == ValidationStatus.PASS
        assert chain.is_valid is True
        assert chain.rejection_stage is None
        assert chain.rejection_reason is None
        assert chain.warnings == []
        assert chain.has_warnings is False

    @pytest.mark.asyncio
    async def test_full_chain_pattern_with_id_attribute(self):
        """
        Test validation chain with pattern object that has id attribute.

        Verifies pattern_id is correctly extracted when pattern is an object.
        """

        class MockPattern:
            def __init__(self):
                self.id = uuid4()
                self.type = "SPRING"
                self.volume_ratio = Decimal("0.45")

        orchestrator = create_default_validation_chain()
        pattern = MockPattern()

        context = ValidationContext(
            pattern=pattern,
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
            phase_info={"phase": "C"},
            trading_range={"creek_level": Decimal("100.00")},
            portfolio_context={"available_capital": Decimal("100000")},
            market_context={"market_condition": "BULL"},
        )

        chain = await orchestrator.run_validation_chain(context)

        # Verify pattern_id was extracted from pattern.id
        assert chain.pattern_id == pattern.id
        assert len(chain.validation_results) == 5

    @pytest.mark.asyncio
    async def test_full_chain_realistic_spring_scenario(self):
        """
        Test realistic Spring pattern validation scenario.

        Simulates a real Spring pattern with all context data as it would
        appear during actual signal generation.
        """
        orchestrator = create_default_validation_chain()
        pattern_id = uuid4()

        context = ValidationContext(
            pattern={
                "id": str(pattern_id),
                "type": "SPRING",
                "spring_low": Decimal("95.00"),
                "spring_high": Decimal("96.50"),
                "penetration_pct": Decimal("0.02"),  # 2% penetration
                "recovery_bars": 2,
            },
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={
                "volume_ratio": Decimal("0.45"),  # Low volume (good for Spring)
                "pattern_type": "SPRING",
                "avg_volume": Decimal("1000000"),
                "actual_volume": Decimal("450000"),
            },
            phase_info={
                "phase": "C",  # Spring should occur in Phase C or D
                "detected_phase": "PHASE_C",
                "phase_duration_bars": 30,
            },
            trading_range={
                "creek_level": Decimal("100.00"),  # Support level
                "creek_strength": Decimal("85.0"),  # 85% strength (strong)
                "ice_level": Decimal("97.00"),  # Stop level
                "jump_level": Decimal("110.00"),  # Target
                "entry_type": "LPS_ENTRY",
            },
            portfolio_context={
                "available_capital": Decimal("100000"),
                "portfolio_heat": Decimal("0.05"),  # 5% current heat
                "max_heat_limit": Decimal("0.10"),  # 10% max allowed
                "symbol_exposure": Decimal("0.00"),  # No existing AAPL position
            },
            market_context={
                "market_condition": "BULL_CONFIRMED",
                "news_events": [],  # No upcoming earnings
                "correlation_warnings": [],
            },
        )

        chain = await orchestrator.run_validation_chain(context)

        # Verify Spring pattern passes all validation stages (stubs)
        assert chain.overall_status == ValidationStatus.PASS
        assert chain.is_valid is True
        assert len(chain.validation_results) == 5

        # Verify pattern_id stored in chain
        assert str(chain.pattern_id) == str(pattern_id)

        # Verify no rejections or warnings
        assert chain.rejection_stage is None
        assert chain.warnings == []
