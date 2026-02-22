"""
Unit tests for _TradeSignalGenerator (P6a: pattern → TradeSignal conversion).

Validates that validated pattern objects (SpringSignal, SOSSignal, etc.) are
correctly converted to TradeSignal Pydantic models with proper price fields,
risk calculations, confidence scoring, and ValidationChain attachment.
"""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.models.phase_classification import WyckoffPhase
from src.models.signal import TradeSignal
from src.models.validation import ValidationChain
from src.orchestrator.orchestrator_facade import _TradeSignalGenerator
from src.orchestrator.pipeline.context import PipelineContextBuilder
from src.orchestrator.stages.validation_stage import ValidationResults

# =============================
# Helpers
# =============================


def _make_spring_pattern(
    *,
    symbol: str = "AAPL",
    timeframe: str = "1d",
    entry_price: Decimal = Decimal("100.00"),
    stop_loss: Decimal = Decimal("95.00"),
    target_price: Decimal = Decimal("120.00"),
    confidence: int = 85,
    phase: str = "C",
    pattern_type: str = "SPRING",
    recommended_position_size: Decimal = Decimal("100"),
) -> SimpleNamespace:
    """Create a minimal Spring-like pattern object."""
    return SimpleNamespace(
        id=uuid4(),
        symbol=symbol,
        timeframe=timeframe,
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_price=target_price,  # SpringSignal uses target_price
        confidence=confidence,
        phase=phase,
        pattern_type=pattern_type,
        recommended_position_size=recommended_position_size,
    )


def _make_sos_pattern(
    *,
    symbol: str = "MSFT",
    timeframe: str = "1h",
    entry_price: Decimal = Decimal("200.00"),
    stop_loss: Decimal = Decimal("190.00"),
    target: Decimal = Decimal("230.00"),
    confidence: int = 80,
    phase: str = "D",
    pattern_type: str = "SOS",
    recommended_position_size: Decimal = Decimal("50"),
) -> SimpleNamespace:
    """Create a minimal SOS-like pattern object (uses 'target' not 'target_price')."""
    return SimpleNamespace(
        id=uuid4(),
        symbol=symbol,
        timeframe=timeframe,
        entry_price=entry_price,
        stop_loss=stop_loss,
        target=target,  # SOSSignal uses target (not target_price)
        confidence=confidence,
        phase=phase,
        pattern_type=pattern_type,
        recommended_position_size=recommended_position_size,
    )


def _make_context(
    symbol: str = "AAPL",
    timeframe: str = "1d",
    validation_results: ValidationResults | None = None,
):
    """Build a PipelineContext with optional validation_results."""
    builder = PipelineContextBuilder().with_symbol(symbol).with_timeframe(timeframe)
    ctx = builder.build()
    if validation_results is not None:
        ctx.set("validation_results", validation_results)
    return ctx


# =============================
# Tests
# =============================


class TestTradeSignalGeneratorSpring:
    """Test Spring pattern → TradeSignal conversion."""

    @pytest.mark.asyncio
    async def test_spring_all_fields_produces_valid_trade_signal(self):
        """Spring pattern with all fields → valid TradeSignal."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern()
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert isinstance(signal, TradeSignal)
        assert signal.symbol == "AAPL"
        assert signal.pattern_type == "SPRING"
        assert signal.phase == "C"
        assert signal.timeframe == "1d"
        assert signal.entry_price == Decimal("100.00")
        assert signal.stop_loss == Decimal("95.00")
        assert signal.target_levels.primary_target == Decimal("120.00")
        assert signal.status == "PENDING"
        assert signal.position_size == Decimal("100")
        # risk_amount = |100 - 95| * 100 = 500
        assert signal.risk_amount == Decimal("500.00")
        # notional_value = 100 * 100 = 10000
        assert signal.notional_value == Decimal("10000.00")

    @pytest.mark.asyncio
    async def test_spring_r_multiple_correct(self):
        """R-multiple: (120-100)/(100-95) = 4.0."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern(
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            target_price=Decimal("120"),
        )
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert signal.r_multiple == Decimal("4")


class TestTradeSignalGeneratorSOS:
    """Test SOS pattern → TradeSignal conversion."""

    @pytest.mark.asyncio
    async def test_sos_pattern_uses_target_field(self):
        """SOS pattern uses 'target' not 'target_price'."""
        gen = _TradeSignalGenerator()
        pattern = _make_sos_pattern()
        ctx = _make_context(symbol="MSFT", timeframe="1h")

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert isinstance(signal, TradeSignal)
        assert signal.symbol == "MSFT"
        assert signal.pattern_type == "SOS"
        assert signal.phase == "D"
        assert signal.target_levels.primary_target == Decimal("230.00")
        # r_multiple: (230-200)/(200-190) = 3.0
        assert signal.r_multiple == Decimal("3")


class TestTradeSignalGeneratorMissingFields:
    """Test patterns with missing required price fields."""

    @pytest.mark.asyncio
    async def test_missing_entry_price_returns_none(self):
        """Pattern missing entry_price → returns None."""
        gen = _TradeSignalGenerator()
        pattern = SimpleNamespace(
            id=uuid4(),
            stop_loss=Decimal("95"),
            target_price=Decimal("120"),
            # no entry_price
        )
        ctx = _make_context()

        result = await gen.generate_signal(pattern, None, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_stop_loss_returns_none(self):
        """Pattern missing stop_loss → returns None."""
        gen = _TradeSignalGenerator()
        pattern = SimpleNamespace(
            id=uuid4(),
            entry_price=Decimal("100"),
            target_price=Decimal("120"),
            # no stop_loss
        )
        ctx = _make_context()

        result = await gen.generate_signal(pattern, None, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_target_returns_none(self):
        """Pattern missing both target_price and target → returns None."""
        gen = _TradeSignalGenerator()
        pattern = SimpleNamespace(
            id=uuid4(),
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            # no target_price, no target
        )
        ctx = _make_context()

        result = await gen.generate_signal(pattern, None, ctx)
        assert result is None


class TestTradeSignalGeneratorRMultiple:
    """Test R-multiple calculation edge cases."""

    @pytest.mark.asyncio
    async def test_r_multiple_long(self):
        """LONG: target=120, entry=100, stop=95 → r_multiple=4.0."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern(
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            target_price=Decimal("120"),
        )
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert signal.r_multiple == Decimal("4")

    @pytest.mark.asyncio
    async def test_r_multiple_zero_denominator_returns_none(self):
        """Entry == stop → zero risk → returns None."""
        gen = _TradeSignalGenerator()
        pattern = SimpleNamespace(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            entry_price=Decimal("100"),
            stop_loss=Decimal("100"),  # Same as entry!
            target_price=Decimal("120"),
            confidence=85,
            phase="C",
            pattern_type="SPRING",
            recommended_position_size=Decimal("100"),
        )
        ctx = _make_context()

        result = await gen.generate_signal(pattern, None, ctx)
        assert result is None


class TestTradeSignalGeneratorConfidence:
    """Test confidence score rejection and capping."""

    @pytest.mark.asyncio
    async def test_confidence_below_70_rejected(self):
        """Confidence below 70 → rejected (returns None)."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern(confidence=50)
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is None

    @pytest.mark.asyncio
    async def test_confidence_clamped_to_max_95(self):
        """Confidence above 95 → clamped to 95."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern(confidence=99)
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert signal.confidence_score == 95

    @pytest.mark.asyncio
    async def test_confidence_in_range_unchanged(self):
        """Confidence in [70, 95] → unchanged."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern(confidence=85)
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert signal.confidence_score == 85

    @pytest.mark.asyncio
    async def test_confidence_default_when_none(self):
        """Pattern with no confidence attr but valid volume_ratio → derives confidence."""
        gen = _TradeSignalGenerator()
        pattern = SimpleNamespace(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            target_price=Decimal("120"),
            phase="C",
            pattern_type="SPRING",
            recommended_position_size=Decimal("100"),
            volume_ratio=0.35,  # Mid-range Spring volume → confidence ~75
            # no 'confidence' field
        )
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        # Confidence derived from volume_ratio: 95 - (0.35/0.7)*25 = 95 - 12.5 = 82.5 → 82
        assert signal.confidence_score == 82


class TestTradeSignalGeneratorValidationChain:
    """Test ValidationChain attachment from context."""

    @pytest.mark.asyncio
    async def test_chain_from_context_attached(self):
        """ValidationChain from ValidationResults is attached to signal."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern()

        # Build ValidationResults with a chain for this pattern
        vr = ValidationResults()
        chain = ValidationChain(pattern_id=pattern.id)
        vr.add(chain, pattern)

        ctx = _make_context(validation_results=vr)

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert signal.validation_chain is chain

    @pytest.mark.asyncio
    async def test_pattern_missing_from_validation_results_falls_back(self):
        """Pattern not in ValidationResults → creates minimal chain."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern()
        other_pattern = _make_spring_pattern()

        # ValidationResults contains a different pattern
        vr = ValidationResults()
        chain = ValidationChain(pattern_id=other_pattern.id)
        vr.add(chain, other_pattern)

        ctx = _make_context(validation_results=vr)

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        # Should have a chain, but it won't be the one from VR
        assert signal.validation_chain is not chain
        assert signal.validation_chain.pattern_id == pattern.id

    @pytest.mark.asyncio
    async def test_no_validation_results_in_context(self):
        """No validation_results in context → creates minimal chain."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern()
        ctx = _make_context()  # No validation_results

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert signal.validation_chain is not None
        assert signal.validation_chain.pattern_id == pattern.id


class TestTradeSignalGeneratorTimestamps:
    """Test timestamp fields."""

    @pytest.mark.asyncio
    async def test_timestamp_and_created_at_are_utc(self):
        """Signal timestamp and created_at should be UTC."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern()
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert signal.timestamp.tzinfo is not None
        assert signal.created_at.tzinfo is not None


class TestTradeSignalGeneratorPatternTypeNormalization:
    """Test pattern_type normalization and rejection."""

    @pytest.mark.asyncio
    async def test_unknown_pattern_type_rejected(self):
        """Unknown pattern_type → rejected (returns None)."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern(pattern_type="UNKNOWN_TYPE")
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is None

    @pytest.mark.asyncio
    async def test_selling_climax_pattern_rejected(self):
        """SC (Selling Climax) must never become a buy signal."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern(pattern_type="SC")
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is None

    @pytest.mark.asyncio
    async def test_automatic_rally_pattern_rejected(self):
        """AR (Automatic Rally) must never become a buy signal."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern(pattern_type="AR")
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is None

    @pytest.mark.asyncio
    async def test_lowercase_pattern_type_normalized(self):
        """Lowercase 'spring' → 'SPRING'."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern(pattern_type="spring")
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert signal.pattern_type == "SPRING"


class TestTradeSignalGeneratorPhaseInference:
    """Test phase inference from pattern_type when pattern has no phase."""

    @pytest.mark.asyncio
    async def test_spring_infers_phase_c(self):
        """Spring with no phase attr → infers phase C."""
        gen = _TradeSignalGenerator()
        pattern = SimpleNamespace(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            target_price=Decimal("120"),
            confidence=85,
            pattern_type="SPRING",
            recommended_position_size=Decimal("100"),
            # no 'phase' attribute
        )
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert signal.phase == "C"

    @pytest.mark.asyncio
    async def test_sos_infers_phase_d(self):
        """SOS with no phase attr → infers phase D."""
        gen = _TradeSignalGenerator()
        pattern = SimpleNamespace(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            target=Decimal("120"),
            confidence=85,
            pattern_type="SOS",
            recommended_position_size=Decimal("100"),
            # no 'phase' attribute
        )
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert signal.phase == "D"

    @pytest.mark.asyncio
    async def test_lps_infers_phase_e(self):
        """LPS with no phase attr → infers phase E."""
        gen = _TradeSignalGenerator()
        pattern = SimpleNamespace(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            target_price=Decimal("120"),
            confidence=85,
            pattern_type="LPS",
            recommended_position_size=Decimal("100"),
            # no 'phase' attribute
        )
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert signal.phase == "E"

    @pytest.mark.asyncio
    async def test_explicit_phase_not_overridden(self):
        """Pattern with explicit phase → keeps it, does not infer."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern(phase="D")
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert signal.phase == "D"

    @pytest.mark.asyncio
    async def test_wyckoff_phase_enum_extracted_correctly(self):
        """WyckoffPhase.E enum → phase string 'E', not 'WyckoffPhase.E'."""
        gen = _TradeSignalGenerator()
        pattern = SimpleNamespace(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            target_price=Decimal("120"),
            confidence=85,
            pattern_type="LPS",
            phase=WyckoffPhase.E,
            recommended_position_size=Decimal("100"),
        )
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert signal.phase == "E"

    @pytest.mark.asyncio
    async def test_wyckoff_phase_enum_c(self):
        """WyckoffPhase.C enum → phase string 'C'."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern()
        # Override phase with the actual enum
        pattern.phase = WyckoffPhase.C
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert signal.phase == "C"


class TestTradeSignalGeneratorCampaignId:
    """Test campaign_id threading from pattern to signal."""

    @pytest.mark.asyncio
    async def test_campaign_id_threaded_from_pattern(self):
        """Pattern with campaign_id → signal carries it."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern()
        pattern.campaign_id = "AAPL-2024-03-13-C"
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert signal.campaign_id == "AAPL-2024-03-13-C"

    @pytest.mark.asyncio
    async def test_campaign_id_none_when_absent(self):
        """Pattern without campaign_id → signal.campaign_id is None."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern()
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None
        assert signal.campaign_id is None

    async def test_non_tradeable_pattern_rejected(self):
        """Pattern with is_tradeable=False is rejected before price extraction."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern()
        pattern.is_tradeable = False
        pattern.rejection_reason = "session filter: outside London session"
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is None

    async def test_tradeable_true_pattern_accepted(self):
        """Pattern with is_tradeable=True proceeds normally."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern()
        pattern.is_tradeable = True
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None

    async def test_pattern_without_is_tradeable_accepted(self):
        """Pattern with no is_tradeable attribute defaults to tradeable (True)."""
        gen = _TradeSignalGenerator()
        pattern = _make_spring_pattern()
        # Ensure is_tradeable is absent (SimpleNamespace doesn't have it by default)
        if hasattr(pattern, "is_tradeable"):
            del pattern.is_tradeable
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None


# =============================
# UTAD Tests (P0-1)
# =============================


def _make_utad_pattern(
    *,
    symbol: str = "AAPL",
    timeframe: str = "1d",
    breakout_price: Decimal | None = Decimal("155.00"),
    ice_level: Decimal | None = Decimal("150.00"),
    failure_price: Decimal | None = Decimal("145.00"),
    volume_ratio: float = 2.5,
    confidence: int = 85,
    phase: str = "D",
    pattern_type: str = "UTAD",
    is_tradeable: bool = True,
) -> SimpleNamespace:
    """Create a minimal UTAD-like pattern object matching UTADDetector output shape."""
    return SimpleNamespace(
        id=uuid4(),
        symbol=symbol,
        timeframe=timeframe,
        breakout_price=breakout_price,
        ice_level=ice_level,
        failure_price=failure_price,
        volume_ratio=volume_ratio,
        confidence=confidence,
        phase=phase,
        pattern_type=pattern_type,
        is_tradeable=is_tradeable,
    )


class TestTradeSignalGeneratorUTAD:
    """Test UTAD pattern -> TradeSignal conversion (P0-1 fix)."""

    @pytest.mark.asyncio
    async def test_utad_field_mapping_produces_signal(self):
        """UTAD output fields map to entry/stop/target correctly.

        UTAD short setup:
          entry  = failure_price (145) — short entry after price fails below Ice
          stop   = ice_level * 1.01 (151.50) — must be above entry for SHORT
          target = failure_price - (breakout_price - failure_price) = 145 - 10 = 135
        """
        gen = _TradeSignalGenerator()
        pattern = _make_utad_pattern()
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)

        assert signal is not None, "UTAD must produce a TradeSignal (not None)"
        assert signal.pattern_type == "UTAD"
        assert signal.entry_price == Decimal("145.00")
        assert signal.stop_loss == Decimal("150.00") * Decimal("1.01")
        # target = 145 - (155 - 145) = 135
        assert signal.target_levels.primary_target == Decimal("135.00")

    @pytest.mark.asyncio
    async def test_utad_without_failure_price_returns_none(self):
        """UTAD missing failure_price cannot produce a signal."""
        gen = _TradeSignalGenerator()
        pattern = _make_utad_pattern(failure_price=None)
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)
        assert signal is None

    @pytest.mark.asyncio
    async def test_utad_confidence_meets_minimum(self):
        """UTAD confidence_score >= 70."""
        gen = _TradeSignalGenerator()
        pattern = _make_utad_pattern()
        ctx = _make_context()

        signal = await gen.generate_signal(pattern, None, ctx)
        assert signal is not None
        assert signal.confidence_score >= 70

    @pytest.mark.asyncio
    async def test_utad_with_mock_trading_range_still_produces_signal(self):
        """UTAD signal is produced even when trading_range has calculate_jump_level()."""
        gen = _TradeSignalGenerator()
        context = MagicMock()
        context.symbol = "AAPL"
        context.timeframe = "1d"
        context.get = MagicMock(return_value=None)

        # Mock trading_range with calculate_jump_level() — this previously could bypass UTAD block
        mock_tr = MagicMock()
        mock_tr.calculate_jump_level.return_value = Decimal("160.00")  # long-biased wrong value

        pattern = _make_utad_pattern()  # uses the existing helper
        signal = await gen.generate_signal(pattern, mock_tr, context)

        assert (
            signal is not None
        ), "UTAD signal must be produced even when trading_range has calculate_jump_level"
        assert signal.entry_price == Decimal("145.00")  # failure_price, not jump_level
        assert signal.pattern_type == "UTAD"

    @pytest.mark.asyncio
    async def test_utad_with_ice_level_none_returns_none(self):
        """UTAD with ice_level=None cannot produce a valid signal (no stop can be computed)."""
        gen = _TradeSignalGenerator()
        context = MagicMock()
        context.symbol = "AAPL"
        context.timeframe = "1d"
        context.get = MagicMock(return_value=None)

        pattern = _make_utad_pattern()
        pattern.ice_level = None

        signal = await gen.generate_signal(pattern, None, context)
        assert signal is None

    @pytest.mark.asyncio
    async def test_utad_with_breakout_price_none_returns_none(self):
        """UTAD with breakout_price=None cannot produce a valid signal (no target can be computed)."""
        gen = _TradeSignalGenerator()
        context = MagicMock()
        context.symbol = "AAPL"
        context.timeframe = "1d"
        context.get = MagicMock(return_value=None)

        pattern = _make_utad_pattern()
        pattern.breakout_price = None

        signal = await gen.generate_signal(pattern, None, context)
        assert signal is None
