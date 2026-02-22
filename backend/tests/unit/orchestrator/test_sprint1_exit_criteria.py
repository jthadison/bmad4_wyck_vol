"""
Sprint 1 Exit Criteria Integration Test

Verifies the wired pipeline (VolumeAnalysisStage → ValidationStage with
StrategyBasedVolumeValidator) produces validated signals for valid bar data.

Sprint exit criterion: Any call to analyze_symbol() with valid bar data returns
at least one validated signal.

These tests prove the full path:
    bars → VolumeAnalysisStage → volume_analysis list → timestamp matching
    → ValidationStage → StrategyBasedVolumeValidator → PASS or FAIL

Author: Story 25.4 (Sprint 1 exit criteria)
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.ohlcv import OHLCVBar
from src.models.validation import ValidationStatus
from src.models.volume_analysis import VolumeAnalysis
from src.orchestrator.pipeline.context import PipelineContext
from src.orchestrator.stages.validation_stage import ValidationStage
from src.orchestrator.stages.volume_analysis_stage import VolumeAnalysisStage
from src.pattern_engine.volume_analyzer import VolumeAnalyzer
from src.signal_generator.validation_chain import ValidationChainOrchestrator
from src.signal_generator.validators.base import BaseValidator
from src.signal_generator.validators.volume.strategy_adapter import StrategyBasedVolumeValidator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bars(count: int = 30, last_volume: int | None = None) -> list[OHLCVBar]:
    """Create count bars with uniform volume=1000, optionally overriding the last bar."""
    bars = []
    for i in range(count):
        volume = 1000
        if last_volume is not None and i == count - 1:
            volume = last_volume
        bars.append(
            OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2024, 1, 1 + i, tzinfo=UTC),
                open=Decimal("100.00"),
                high=Decimal("110.00"),
                low=Decimal("90.00"),
                close=Decimal("105.00"),
                volume=Decimal(str(volume)),
                spread=Decimal("20.00"),
            )
        )
    return bars


class _AlwaysPassValidator(BaseValidator):
    """Stub validator that always returns PASS - used to isolate volume validation."""

    def __init__(self, stage: str) -> None:
        self._stage = stage

    @property
    def validator_id(self) -> str:
        return f"STUB_{self._stage.upper()}"

    @property
    def stage_name(self) -> str:
        return self._stage

    async def validate(self, context):
        return self.create_result(ValidationStatus.PASS)


def _make_spring_pattern(bar: OHLCVBar, volume_ratio: Decimal):
    """Create a minimal mock Spring pattern for use with ValidationStage."""
    from unittest.mock import MagicMock

    pattern = MagicMock()
    pattern.bar = bar
    pattern.volume_ratio = volume_ratio
    pattern.pattern_type = "SPRING"
    pattern.id = uuid4()
    return pattern


# ---------------------------------------------------------------------------
# Test A: Valid Spring (low volume) passes volume validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_spring_passes_volume_validation():
    """
    Sprint exit criterion Test A: Valid Spring with low volume passes volume validation.

    Setup:
    - 30 bars, bars 0-28 have volume=1000
    - Bar 29 has volume=400 (0.40x average → well below 0.7 threshold)

    Expected: ValidationStatus.PASS from StrategyBasedVolumeValidator
    """
    # --- Arrange ---
    bars = _make_bars(count=30, last_volume=400)

    # Run VolumeAnalysisStage to get real VolumeAnalysis list
    ctx = PipelineContext(symbol="TEST", timeframe="1d", correlation_id=uuid4())
    analyzer = VolumeAnalyzer()
    stage = VolumeAnalysisStage(analyzer)
    volume_analysis: list[VolumeAnalysis] = await stage.execute(bars, ctx)

    # Bar 29 is the Spring bar; get the computed volume_ratio
    spring_bar = bars[29]
    spring_va = volume_analysis[29]
    assert spring_va.volume_ratio is not None, "Bar 29 should have a computed volume_ratio"
    assert spring_va.volume_ratio < Decimal(
        "0.7"
    ), f"Expected volume_ratio < 0.7 for valid Spring, got {spring_va.volume_ratio}"

    # Build mock Spring pattern aligned to bar 29's timestamp
    spring_pattern = _make_spring_pattern(spring_bar, spring_va.volume_ratio)

    # Build ValidationStage using ONLY StrategyBasedVolumeValidator;
    # all other stages stubbed to PASS so we can isolate volume validation.
    orchestrator = ValidationChainOrchestrator(
        validators=[
            StrategyBasedVolumeValidator(),
            _AlwaysPassValidator("Phase"),
            _AlwaysPassValidator("Level"),
            _AlwaysPassValidator("Risk"),
            _AlwaysPassValidator("Strategy"),
        ]
    )
    validation_stage = ValidationStage(orchestrator)

    pipeline_ctx = PipelineContext(symbol="TEST", timeframe="1d", correlation_id=uuid4())
    pipeline_ctx.set("volume_analysis", volume_analysis)
    pipeline_ctx.set("phase_info", None)
    pipeline_ctx.set("current_trading_range", None)

    # --- Act ---
    result = await validation_stage.execute([spring_pattern], pipeline_ctx)

    # --- Assert ---
    assert result.total_count == 1
    chain = result.results[0]
    assert chain.overall_status == ValidationStatus.PASS, (
        f"Expected PASS for valid Spring (volume_ratio={spring_va.volume_ratio}), "
        f"got {chain.overall_status}. Rejection stage: {chain.rejection_stage}, "
        f"reason: {chain.rejection_reason}"
    )


# ---------------------------------------------------------------------------
# Test B: Invalid Spring (high volume) is rejected (regression guard)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_spring_rejected_by_volume_validation():
    """
    Sprint exit criterion Test B: Spring with high volume is rejected by volume validation.

    Setup:
    - 30 bars, bars 0-28 have volume=1000
    - Bar 29 has volume=900 (0.90x average → above 0.7 threshold)

    Expected: ValidationStatus.FAIL with rejection_stage containing "volume"
    """
    # --- Arrange ---
    bars = _make_bars(count=30, last_volume=900)

    ctx = PipelineContext(symbol="TEST", timeframe="1d", correlation_id=uuid4())
    analyzer = VolumeAnalyzer()
    stage = VolumeAnalysisStage(analyzer)
    volume_analysis: list[VolumeAnalysis] = await stage.execute(bars, ctx)

    spring_bar = bars[29]
    spring_va = volume_analysis[29]
    assert spring_va.volume_ratio is not None, "Bar 29 should have a computed volume_ratio"
    assert spring_va.volume_ratio > Decimal(
        "0.7"
    ), f"Expected volume_ratio > 0.7 for invalid Spring, got {spring_va.volume_ratio}"

    spring_pattern = _make_spring_pattern(spring_bar, spring_va.volume_ratio)

    orchestrator = ValidationChainOrchestrator(
        validators=[
            StrategyBasedVolumeValidator(),
            _AlwaysPassValidator("Phase"),
            _AlwaysPassValidator("Level"),
            _AlwaysPassValidator("Risk"),
            _AlwaysPassValidator("Strategy"),
        ]
    )
    validation_stage = ValidationStage(orchestrator)

    pipeline_ctx = PipelineContext(symbol="TEST", timeframe="1d", correlation_id=uuid4())
    pipeline_ctx.set("volume_analysis", volume_analysis)
    pipeline_ctx.set("phase_info", None)
    pipeline_ctx.set("current_trading_range", None)

    # --- Act ---
    result = await validation_stage.execute([spring_pattern], pipeline_ctx)

    # --- Assert ---
    assert result.total_count == 1
    chain = result.results[0]
    assert chain.overall_status == ValidationStatus.FAIL, (
        f"Expected FAIL for invalid Spring (volume_ratio={spring_va.volume_ratio}), "
        f"got {chain.overall_status}"
    )
    assert chain.rejection_stage is not None, "rejection_stage should be set on FAIL"
    assert (
        "volume" in chain.rejection_stage.lower()
    ), f"Expected rejection at volume stage, got '{chain.rejection_stage}'"
