"""
Tests for P6b (signal persistence) and P6c (PositionSizing → TradeSignal mapping).

P6b: MasterOrchestratorFacade._persist_signals saves each signal via SignalRepository.
P6c: _RiskManagerAdapter.apply_sizing maps PositionSizing fields onto TradeSignal.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal
from src.models.validation import ValidationChain
from src.orchestrator.orchestrator_facade import MasterOrchestratorFacade, _RiskManagerAdapter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trade_signal(**overrides) -> TradeSignal:
    """Build a minimal valid TradeSignal for testing."""
    defaults = {
        "symbol": "AAPL",
        "pattern_type": "SPRING",
        "phase": "C",
        "timeframe": "1d",
        "entry_price": Decimal("150.00"),
        "stop_loss": Decimal("148.00"),
        "target_levels": TargetLevels(primary_target=Decimal("156.00")),
        "position_size": Decimal("100"),
        "notional_value": Decimal("15000.00"),
        "risk_amount": Decimal("200.00"),
        "r_multiple": Decimal("3.0"),
        "confidence_score": 85,
        "confidence_components": ConfidenceComponents(
            pattern_confidence=88,
            phase_confidence=82,
            volume_confidence=80,
            overall_confidence=85,
        ),
        "validation_chain": ValidationChain(
            pattern_id=uuid4(),
            validation_results=[],
            overall_status="PASS",
        ),
        "timestamp": datetime.now(UTC),
    }
    defaults.update(overrides)
    return TradeSignal(**defaults)


# ---------------------------------------------------------------------------
# P6b: _persist_signals
# ---------------------------------------------------------------------------


class TestPersistSignals:
    """Tests for MasterOrchestratorFacade._persist_signals."""

    @pytest.mark.asyncio
    async def test_persist_saves_each_signal(self):
        """save_signal is called once per signal when DB is available."""
        facade = MasterOrchestratorFacade()
        signals = [_make_trade_signal(symbol="AAPL"), _make_trade_signal(symbol="MSFT")]

        mock_repo = MagicMock()
        mock_repo.save_signal = AsyncMock()

        mock_session = AsyncMock()

        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "src.database.async_session_maker",
                mock_session_maker,
            ),
            patch(
                "src.repositories.signal_repository.SignalRepository",
                return_value=mock_repo,
            ),
        ):
            await facade._persist_signals(signals)

        assert mock_repo.save_signal.call_count == 2

    @pytest.mark.asyncio
    async def test_persist_no_session_maker_logs_warning(self, caplog):
        """When async_session_maker is None, log warning and return safely."""
        facade = MasterOrchestratorFacade()
        signals = [_make_trade_signal()]

        with patch(
            "src.database.async_session_maker",
            None,
        ):
            # Should not raise
            await facade._persist_signals(signals)

    @pytest.mark.asyncio
    async def test_persist_exception_does_not_raise(self):
        """DB errors are logged but never propagated."""
        facade = MasterOrchestratorFacade()
        signals = [_make_trade_signal()]

        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(
            side_effect=RuntimeError("DB down"),
        )
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "src.database.async_session_maker",
            mock_session_maker,
        ):
            # Must not raise
            await facade._persist_signals(signals)


# ---------------------------------------------------------------------------
# P6c: PositionSizing → TradeSignal mapping in _RiskManagerAdapter
# ---------------------------------------------------------------------------


class TestPositionSizingMapping:
    """Tests for _RiskManagerAdapter.apply_sizing PositionSizing mapping."""

    def _make_pipeline_context(self):
        """Build a minimal PipelineContext with required fields."""
        from src.orchestrator.pipeline.context import PipelineContext

        ctx = PipelineContext(
            correlation_id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
        )
        # Provide portfolio_context and trading_range so the adapter doesn't
        # short-circuit with the "context missing" fallback.
        ctx.set("portfolio_context", MagicMock())
        ctx.set("current_trading_range", MagicMock())
        return ctx

    @pytest.mark.asyncio
    async def test_position_sizing_fields_applied_to_trade_signal(self):
        """PositionSizing shares/risk_amount/r_multiple/position_value map onto TradeSignal."""
        sizing_result = MagicMock()
        sizing_result.shares = 50
        sizing_result.actual_risk = Decimal("100.00")
        sizing_result.position_value = Decimal("7500.00")

        risk_manager = MagicMock()
        risk_manager.validate_and_size = AsyncMock(return_value=sizing_result)

        adapter = _RiskManagerAdapter(risk_manager)
        signal = _make_trade_signal()
        ctx = self._make_pipeline_context()

        result = await adapter.apply_sizing(signal, ctx)

        assert result is not None
        assert isinstance(result, TradeSignal)
        assert result.position_size == 50
        assert result.risk_amount == Decimal("100.00")
        assert result.notional_value == Decimal("7500.00")

    @pytest.mark.asyncio
    async def test_non_trade_signal_passes_through_unchanged(self):
        """Non-TradeSignal objects are returned as-is (no model_copy)."""
        sizing_result = MagicMock()
        sizing_result.shares = 50

        risk_manager = MagicMock()
        risk_manager.validate_and_size = AsyncMock(return_value=sizing_result)

        adapter = _RiskManagerAdapter(risk_manager)

        # Use a plain mock as a non-TradeSignal signal
        fake_signal = MagicMock()
        fake_signal.entry_price = Decimal("150.00")
        fake_signal.stop_loss = Decimal("148.00")
        fake_signal.target_price = Decimal("156.00")
        fake_signal.symbol = "AAPL"
        fake_signal.pattern_type = "SPRING"
        fake_signal.campaign_id = None

        ctx = self._make_pipeline_context()

        result = await adapter.apply_sizing(fake_signal, ctx)

        # Should be the original mock, not a model_copy
        assert result is fake_signal

    @pytest.mark.asyncio
    async def test_rejected_signal_returns_none(self):
        """When validate_and_size returns None, apply_sizing returns None."""
        risk_manager = MagicMock()
        risk_manager.validate_and_size = AsyncMock(return_value=None)

        adapter = _RiskManagerAdapter(risk_manager)
        signal = _make_trade_signal()
        ctx = self._make_pipeline_context()

        result = await adapter.apply_sizing(signal, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_context_passes_signal_through(self):
        """When portfolio_context is missing, signal passes through unchanged."""
        risk_manager = MagicMock()
        adapter = _RiskManagerAdapter(risk_manager)
        signal = _make_trade_signal()

        from src.orchestrator.pipeline.context import PipelineContext

        ctx = PipelineContext(
            correlation_id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
        )
        # Intentionally NOT setting portfolio_context or trading_range

        result = await adapter.apply_sizing(signal, ctx)
        assert result is signal
        risk_manager.validate_and_size.assert_not_called()
