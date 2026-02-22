"""
Unit tests for VolumeAnalysisStage - Story 25.16

Tests verify that VolumeAnalysisStage correctly returns volume analysis data
for input bars and makes that data available to downstream validators.
"""

import pytest
from datetime import datetime, UTC
from decimal import Decimal
from uuid import uuid4

from src.models.ohlcv import OHLCVBar
from src.models.volume_analysis import VolumeAnalysis
from src.orchestrator.pipeline.context import PipelineContext
from src.orchestrator.stages.volume_analysis_stage import VolumeAnalysisStage
from src.pattern_engine.volume_analyzer import VolumeAnalyzer


def create_test_bars(count: int, base_volume: int = 1000, vary_volume: bool = False) -> list[OHLCVBar]:
    """
    Create test OHLCV bars with configurable volume.

    Args:
        count: Number of bars to create
        base_volume: Base volume value
        vary_volume: If True, alternate volume between base and base*1.5

    Returns:
        List of OHLCVBar instances
    """
    bars = []
    for i in range(count):
        volume = base_volume
        if vary_volume and i % 2 == 1:
            volume = int(base_volume * 1.5)

        bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1 + i, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("110.00"),
            low=Decimal("90.00"),
            close=Decimal("105.00"),
            volume=Decimal(str(volume)),
            spread=Decimal("20.00"),  # high - low
        )
        bars.append(bar)
    return bars


@pytest.fixture
def pipeline_context():
    """Create a basic pipeline context for testing."""
    return PipelineContext(
        symbol="TEST",
        timeframe="1d",
        correlation_id=uuid4(),
    )


@pytest.fixture
def volume_analysis_stage():
    """Create a VolumeAnalysisStage with real VolumeAnalyzer."""
    analyzer = VolumeAnalyzer()
    return VolumeAnalysisStage(analyzer)


# ============================================================================
# AC1: Stage Returns Non-Empty Volume Data for Valid Bars
# ============================================================================


@pytest.mark.asyncio
async def test_stage_returns_non_empty_list_for_30_bars(
    volume_analysis_stage, pipeline_context
):
    """
    AC1: Given 30 bars, VolumeAnalysisStage returns non-empty list.

    Verifies that the stage produces volume analysis results for all input bars.
    """
    # Arrange
    bars = create_test_bars(30, vary_volume=True)

    # Act
    result = await volume_analysis_stage.execute(bars, pipeline_context)

    # Assert
    assert result is not None, "Stage returned None instead of list"
    assert isinstance(result, list), f"Expected list, got {type(result)}"
    assert len(result) == 30, f"Expected 30 results, got {len(result)}"
    assert all(isinstance(r, VolumeAnalysis) for r in result), \
        "Not all results are VolumeAnalysis instances"


@pytest.mark.asyncio
async def test_each_result_contains_volume_ratio(
    volume_analysis_stage, pipeline_context
):
    """
    AC1: Each VolumeAnalysis result contains volume_ratio field.

    Tests that the stage populates the volume_ratio field for bars with
    sufficient history (index >= 20).
    """
    # Arrange
    bars = create_test_bars(30, vary_volume=False)

    # Act
    result = await volume_analysis_stage.execute(bars, pipeline_context)

    # Assert
    # First 20 bars: volume_ratio should be None (insufficient history)
    for i in range(20):
        assert result[i].volume_ratio is None, \
            f"Bar {i} should have volume_ratio=None (< 20 bars history)"

    # Bars 20+: volume_ratio should be calculated
    for i in range(20, 30):
        assert result[i].volume_ratio is not None, \
            f"Bar {i} should have calculated volume_ratio"
        assert isinstance(result[i].volume_ratio, Decimal), \
            f"volume_ratio should be Decimal, got {type(result[i].volume_ratio)}"


# ============================================================================
# AC2: Volume Data Available to Validators (Context Storage)
# ============================================================================


@pytest.mark.asyncio
async def test_stage_stores_results_in_context(
    volume_analysis_stage, pipeline_context
):
    """
    AC2: VolumeAnalysisStage stores results in pipeline context.

    Verifies that downstream stages can access volume analysis data via context.
    """
    # Arrange
    bars = create_test_bars(30)

    # Act
    await volume_analysis_stage.execute(bars, pipeline_context)

    # Assert
    context_data = pipeline_context.get("volume_analysis")
    assert context_data is not None, "volume_analysis not found in context"
    assert isinstance(context_data, list), \
        f"Context data should be list, got {type(context_data)}"
    assert len(context_data) == 30, \
        f"Context should have 30 entries, got {len(context_data)}"


# ============================================================================
# AC4 / Story 25.16: Empty Bars Handled Gracefully (Returning Empty List)
# ============================================================================


@pytest.mark.asyncio
async def test_empty_bars_returns_empty_list_not_raises(
    volume_analysis_stage, pipeline_context
):
    """
    Story 25.16 - Test 1: Empty bars returns empty list, not raises.

    Verifies that VolumeAnalysisStage.execute() returns an empty list
    when given empty input, rather than raising an exception.
    """
    # Arrange
    empty_bars = []

    # Act
    result = await volume_analysis_stage.execute(empty_bars, pipeline_context)

    # Assert
    assert result == [], f"Expected empty list, got {result}"
    assert isinstance(result, list), f"Expected list type, got {type(result)}"


@pytest.mark.asyncio
async def test_30_bars_returns_nonempty_list(
    volume_analysis_stage, pipeline_context
):
    """
    Story 25.16 - Test 2: 30 bars returns non-empty list.

    Verifies that when given 30 bars, the stage produces 30 VolumeAnalysis results.
    """
    # Arrange
    bars = create_test_bars(30, base_volume=1000, vary_volume=True)

    # Act
    result = await volume_analysis_stage.execute(bars, pipeline_context)

    # Assert
    assert len(result) > 0, "Expected non-empty list for 30 bars"
    assert len(result) == 30, f"Expected 30 results, got {len(result)}"
    assert all(isinstance(r, VolumeAnalysis) for r in result), \
        "All results should be VolumeAnalysis instances"


@pytest.mark.asyncio
async def test_volume_ratio_values_correct(
    volume_analysis_stage, pipeline_context
):
    """
    Story 25.16 - Test 3: Volume ratio calculation produces correct values.

    Verifies that volume_ratio math is accurate:
    - Bars 0-19: volume=100 (history)
    - Bar 20: volume=150
    - Expected ratio: 150/100 = 1.5
    """
    # Arrange: Create bars with known volumes
    bars = []
    for i in range(21):
        volume = 100 if i < 20 else 150
        bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1 + i, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("110.00"),
            low=Decimal("90.00"),
            close=Decimal("105.00"),
            volume=Decimal(str(volume)),
            spread=Decimal("20.00"),  # high - low
        )
        bars.append(bar)

    # Act
    result = await volume_analysis_stage.execute(bars, pipeline_context)

    # Assert
    # First 20 bars should have None for volume_ratio (insufficient history)
    for i in range(20):
        assert result[i].volume_ratio is None, \
            f"Bar {i} should have volume_ratio=None (insufficient history)"

    # Bar 20 should have correct volume_ratio
    bar_20_ratio = result[20].volume_ratio
    assert bar_20_ratio is not None, "Bar 20 should have calculated volume_ratio"

    expected_ratio = Decimal("1.5")
    tolerance = Decimal("0.01")
    assert abs(bar_20_ratio - expected_ratio) < tolerance, \
        f"Expected volume_ratio ~{expected_ratio}, got {bar_20_ratio}"


@pytest.mark.asyncio
async def test_spring_08x_volume_fails_validation_not_crashes():
    """
    Story 25.16 - Test 4: Spring with volume_ratio=0.8 fails validation (not crashes).

    Regression test for the core bug:
    - Before fix: ValidationStage crashed with AttributeError when accessing empty list
    - After fix: ValidationStage returns FAIL (Spring volume_ratio 0.8 > 0.7 threshold)

    Tests the full pipeline:
    1. Create Spring pattern with volume_ratio=0.8 (above 0.7 threshold)
    2. Create matching VolumeAnalysis with single entry
    3. Pass through ValidationStage
    4. Assert result is FAIL (not AttributeError crash)
    """
    from src.models.spring import Spring
    from src.models.validation import ValidationStatus
    from src.orchestrator.stages.validation_stage import ValidationStage
    from src.signal_generator.validation_chain import create_default_validation_chain

    # Arrange: Create Spring pattern with volume_ratio=0.8 (should FAIL)
    spring_bar = OHLCVBar(
        symbol="TEST",
        timeframe="1d",
        timestamp=datetime(2024, 1, 21, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("110.00"),
        low=Decimal("98.00"),  # Penetrates below creek
        close=Decimal("105.00"),
        volume=Decimal("800"),  # 0.8x average volume
        spread=Decimal("12.00"),  # high - low
    )

    spring_pattern = Spring(
        bar=spring_bar,
        bar_index=20,
        penetration_pct=Decimal("0.02"),  # 2% below creek
        volume_ratio=Decimal("0.8"),  # ABOVE 0.7 threshold → should FAIL
        recovery_bars=1,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.00"),
        recovery_price=Decimal("105.00"),
        detection_timestamp=datetime(2024, 1, 21, tzinfo=UTC),
        trading_range_id=uuid4(),
    )

    # Create matching VolumeAnalysis (single entry matching the spring bar)
    volume_analysis = VolumeAnalysis(
        bar=spring_bar,
        volume_ratio=Decimal("0.8"),
        spread_ratio=Decimal("1.0"),
        close_position=Decimal("0.7"),
        effort_result="NORMAL",
    )

    # Create ValidationStage with default validation chain
    orchestrator = create_default_validation_chain()
    validation_stage = ValidationStage(orchestrator)

    # Create pipeline context with volume_analysis
    context = PipelineContext(
        symbol="TEST",
        timeframe="1d",
        correlation_id=uuid4(),
    )
    context.set("volume_analysis", [volume_analysis])
    context.set("phase_info", None)  # Optional
    context.set("current_trading_range", None)  # Optional

    # Act: Run validation on the Spring pattern
    # This should NOT crash with AttributeError on empty list access
    result = await validation_stage.execute([spring_pattern], context)

    # Assert: Validation should FAIL (not crash)
    assert result is not None, "ValidationStage returned None"
    assert len(result.results) == 1, f"Expected 1 validation result, got {len(result.results)}"

    validation_chain = result.results[0]
    assert validation_chain.overall_status == ValidationStatus.FAIL, \
        f"Expected FAIL for Spring with volume_ratio=0.8, got {validation_chain.overall_status}"

    # Verify it failed at volume validation stage (not later stages)
    assert validation_chain.rejection_stage is not None, "rejection_stage should be set"
    assert "volume" in validation_chain.rejection_stage.lower(), \
        f"Expected failure at volume stage, got {validation_chain.rejection_stage}"


# ============================================================================
# Volume Ratio Accuracy Tests
# ============================================================================


@pytest.mark.asyncio
async def test_volume_ratio_calculation_accuracy(
    volume_analysis_stage, pipeline_context
):
    """
    Test volume_ratio calculation accuracy with known values.

    Setup:
    - Bars 0-19: volume=100 (history)
    - Bar 20: volume=150
    - Expected ratio: 150 / 100 = 1.5
    """
    # Arrange: Create bars with controlled volumes
    bars = []
    for i in range(21):
        volume = 100 if i < 20 else 150
        bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1 + i, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("110.00"),
            low=Decimal("90.00"),
            close=Decimal("105.00"),
            volume=Decimal(str(volume)),
            spread=Decimal("20.00"),  # high - low
        )
        bars.append(bar)

    # Act
    result = await volume_analysis_stage.execute(bars, pipeline_context)

    # Assert
    bar_20_ratio = result[20].volume_ratio
    assert bar_20_ratio is not None, "Bar 20 should have volume_ratio"

    expected_ratio = Decimal("1.5")
    assert abs(bar_20_ratio - expected_ratio) < Decimal("0.01"), \
        f"Expected volume_ratio ~{expected_ratio}, got {bar_20_ratio}"


@pytest.mark.asyncio
async def test_low_volume_ratio_below_spring_threshold(
    volume_analysis_stage, pipeline_context
):
    """
    Test low volume scenario (Spring pattern).

    Setup:
    - Bars 0-19: volume=1000
    - Bar 20: volume=500 (0.5x average, well below 0.7 threshold)
    - Expected: volume_ratio = 0.5
    """
    # Arrange
    bars = []
    for i in range(21):
        volume = 1000 if i < 20 else 500
        bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1 + i, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("110.00"),
            low=Decimal("90.00"),
            close=Decimal("105.00"),
            volume=Decimal(str(volume)),
            spread=Decimal("20.00"),  # high - low
        )
        bars.append(bar)

    # Act
    result = await volume_analysis_stage.execute(bars, pipeline_context)

    # Assert
    bar_20_ratio = result[20].volume_ratio
    assert bar_20_ratio is not None
    assert bar_20_ratio < Decimal("0.7"), \
        f"Low volume bar should have ratio < 0.7, got {bar_20_ratio}"
    assert abs(bar_20_ratio - Decimal("0.5")) < Decimal("0.01"), \
        f"Expected volume_ratio ~0.5, got {bar_20_ratio}"


@pytest.mark.asyncio
async def test_high_volume_ratio_above_sos_threshold(
    volume_analysis_stage, pipeline_context
):
    """
    Test high volume scenario (SOS pattern).

    Setup:
    - Bars 0-19: volume=1000
    - Bar 20: volume=2000 (2.0x average, above 1.5 threshold)
    - Expected: volume_ratio = 2.0
    """
    # Arrange
    bars = []
    for i in range(21):
        volume = 1000 if i < 20 else 2000
        bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1 + i, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("110.00"),
            low=Decimal("90.00"),
            close=Decimal("105.00"),
            volume=Decimal(str(volume)),
            spread=Decimal("20.00"),  # high - low
        )
        bars.append(bar)

    # Act
    result = await volume_analysis_stage.execute(bars, pipeline_context)

    # Assert
    bar_20_ratio = result[20].volume_ratio
    assert bar_20_ratio is not None
    assert bar_20_ratio > Decimal("1.5"), \
        f"High volume bar should have ratio > 1.5, got {bar_20_ratio}"
    assert abs(bar_20_ratio - Decimal("2.0")) < Decimal("0.01"), \
        f"Expected volume_ratio ~2.0, got {bar_20_ratio}"


# ============================================================================
# Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_zero_volume_bars_handled(
    volume_analysis_stage, pipeline_context
):
    """
    Test handling of zero-volume bars.

    VolumeAnalyzer should return None for volume_ratio when average volume is zero
    (division by zero protection).
    """
    # Arrange: All bars have zero volume
    bars = []
    for i in range(25):
        bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1 + i, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("110.00"),
            low=Decimal("90.00"),
            close=Decimal("105.00"),
            volume=Decimal("0"),
        )
        bars.append(bar)

    # Act
    result = await volume_analysis_stage.execute(bars, pipeline_context)

    # Assert: All volume_ratios should be None (division by zero protection)
    for i, analysis in enumerate(result):
        assert analysis.volume_ratio is None, \
            f"Bar {i} with zero volume history should have volume_ratio=None"


@pytest.mark.asyncio
async def test_single_bar_insufficient_history(
    volume_analysis_stage, pipeline_context
):
    """
    Test single bar (insufficient history for 20-bar average).

    volume_ratio should be None when index < 20.
    """
    # Arrange
    bars = create_test_bars(1)

    # Act
    result = await volume_analysis_stage.execute(bars, pipeline_context)

    # Assert
    assert len(result) == 1
    assert result[0].volume_ratio is None, \
        "Single bar should have volume_ratio=None (insufficient history)"


# ============================================================================
# Type Validation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_invalid_bars_type_raises_type_error(
    volume_analysis_stage, pipeline_context
):
    """Test that non-list input raises TypeError."""
    with pytest.raises(TypeError, match="Expected list\\[OHLCVBar\\]"):
        await volume_analysis_stage.execute("not a list", pipeline_context)


@pytest.mark.asyncio
async def test_invalid_bar_items_raises_type_error(
    volume_analysis_stage, pipeline_context
):
    """Test that list with non-OHLCVBar items raises TypeError."""
    invalid_bars = ["not", "ohlcv", "bars"]

    with pytest.raises(TypeError, match="Expected OHLCVBar items"):
        await volume_analysis_stage.execute(invalid_bars, pipeline_context)
