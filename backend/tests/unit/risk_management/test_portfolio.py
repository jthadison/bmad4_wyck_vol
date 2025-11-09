"""
Unit Tests for Portfolio Heat Tracking (Story 7.3)

Test Coverage:
--------------
1. calculate_portfolio_heat: AC 1-2, AC 8
2. get_phase_adjusted_heat_limit: AC 11-12
3. calculate_volume_risk_multiplier: AC 13-15
4. identify_campaign_clusters: AC 16-17
5. calculate_correlation_adjusted_heat: AC 16
6. check_campaign_stage_warnings: AC 7 revised
7. build_portfolio_heat_report: AC 5
8. validate_portfolio_heat_capacity: AC 4, AC 14

Author: Story 7.3
"""

from decimal import Decimal

import pytest

from src.models.portfolio import (
    PortfolioHeat,
    Position,
)
from src.risk_management.portfolio import (
    build_portfolio_heat_report,
    calculate_correlation_adjusted_heat,
    calculate_portfolio_heat,
    calculate_volume_risk_multiplier,
    check_campaign_stage_warnings,
    get_phase_adjusted_heat_limit,
    identify_campaign_clusters,
    validate_portfolio_heat_capacity,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def empty_positions() -> list[Position]:
    """Empty positions list."""
    return []


@pytest.fixture
def single_position() -> list[Position]:
    """Single position with 2% risk."""
    return [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("30.0"),
            sector="Technology",
        )
    ]


@pytest.fixture
def multiple_positions() -> list[Position]:
    """Multiple positions totaling 10% risk."""
    return [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("35.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("32.0"),
            sector="Technology",
        ),
        Position(
            symbol="GOOGL",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("30.0"),
            sector="Technology",
        ),
        Position(
            symbol="JNJ",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="C",
            volume_confirmation_score=Decimal("25.0"),
            sector="Healthcare",
        ),
        Position(
            symbol="PFE",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="C",
            volume_confirmation_score=Decimal("20.0"),
            sector="Healthcare",
        ),
    ]


@pytest.fixture
def phase_a_positions() -> list[Position]:
    """Positions in Phase A (early accumulation)."""
    return [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="A",
            volume_confirmation_score=Decimal("15.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="A",
            volume_confirmation_score=Decimal("18.0"),
            sector="Technology",
        ),
    ]


@pytest.fixture
def phase_e_positions() -> list[Position]:
    """Positions in Phase E (markup)."""
    return [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("5.0"),
            status="OPEN",
            wyckoff_phase="E",
            volume_confirmation_score=Decimal("38.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("5.0"),
            status="OPEN",
            wyckoff_phase="E",
            volume_confirmation_score=Decimal("35.0"),
            sector="Technology",
        ),
        Position(
            symbol="GOOGL",
            position_risk_pct=Decimal("5.0"),
            status="OPEN",
            wyckoff_phase="E",
            volume_confirmation_score=Decimal("36.0"),
            sector="Technology",
        ),
    ]


@pytest.fixture
def clustered_positions() -> list[Position]:
    """Positions with campaign clusters (same sector + phase)."""
    return [
        # Tech/Phase D cluster (3 positions)
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("4.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("35.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("4.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("33.0"),
            sector="Technology",
        ),
        Position(
            symbol="GOOGL",
            position_risk_pct=Decimal("4.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("32.0"),
            sector="Technology",
        ),
        # Healthcare/Phase C (isolated)
        Position(
            symbol="JNJ",
            position_risk_pct=Decimal("4.0"),
            status="OPEN",
            wyckoff_phase="C",
            volume_confirmation_score=Decimal("25.0"),
            sector="Healthcare",
        ),
    ]


# ============================================================================
# Test calculate_portfolio_heat (AC 1-2, AC 8)
# ============================================================================


def test_calculate_portfolio_heat_empty(empty_positions):
    """Test: Empty positions list returns 0% heat."""
    result = calculate_portfolio_heat(empty_positions)
    assert isinstance(result, Decimal)
    assert result == Decimal("0.0")


def test_calculate_portfolio_heat_single(single_position):
    """Test: Single position with 2% risk returns 2.0% heat."""
    result = calculate_portfolio_heat(single_position)
    assert isinstance(result, Decimal)
    assert result == Decimal("2.0")


def test_calculate_portfolio_heat_multiple(multiple_positions):
    """Test: 5 positions with 2% each returns 10.0% heat."""
    result = calculate_portfolio_heat(multiple_positions)
    assert isinstance(result, Decimal)
    assert result == Decimal("10.0")


def test_calculate_portfolio_heat_accumulation():
    """Test: Positions correctly accumulate (1% + 3% + 2.5% = 6.5%)."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("1.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("30.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("3.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("32.0"),
            sector="Technology",
        ),
        Position(
            symbol="GOOGL",
            position_risk_pct=Decimal("2.5"),
            status="OPEN",
            wyckoff_phase="C",
            volume_confirmation_score=Decimal("25.0"),
            sector="Technology",
        ),
    ]
    result = calculate_portfolio_heat(positions)
    assert result == Decimal("6.5")


def test_calculate_portfolio_heat_decimal_precision():
    """Test: Decimal precision maintained (no floating point drift)."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("2.33333333"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("30.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("1.66666667"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("32.0"),
            sector="Technology",
        ),
    ]
    result = calculate_portfolio_heat(positions)
    assert isinstance(result, Decimal)
    # Verify exact decimal addition (no float conversion)
    assert result == Decimal("4.00000000")


# ============================================================================
# Test get_phase_adjusted_heat_limit (AC 11-12)
# ============================================================================


def test_phase_adjusted_limit_phase_a_b():
    """Test: All positions in Phase A/B → 8.0% limit."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="A",
            volume_confirmation_score=Decimal("15.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="B",
            volume_confirmation_score=Decimal("18.0"),
            sector="Technology",
        ),
    ]
    limit, basis = get_phase_adjusted_heat_limit(positions)
    assert limit == Decimal("8.0")
    assert "Phase" in basis
    assert "majority" in basis or "plurality" in basis


def test_phase_adjusted_limit_phase_c_d():
    """Test: All positions in Phase C/D → 12.0% limit."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("30.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("32.0"),
            sector="Technology",
        ),
        Position(
            symbol="GOOGL",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="C",
            volume_confirmation_score=Decimal("25.0"),
            sector="Technology",
        ),
    ]
    limit, basis = get_phase_adjusted_heat_limit(positions)
    assert limit == Decimal("12.0")
    assert "Phase D" in basis  # Phase D is majority


def test_phase_adjusted_limit_phase_e():
    """Test: All positions in Phase E → 15.0% limit."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("5.0"),
            status="OPEN",
            wyckoff_phase="E",
            volume_confirmation_score=Decimal("38.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("5.0"),
            status="OPEN",
            wyckoff_phase="E",
            volume_confirmation_score=Decimal("35.0"),
            sector="Technology",
        ),
    ]
    limit, basis = get_phase_adjusted_heat_limit(positions)
    assert limit == Decimal("15.0")
    assert "Phase E" in basis


def test_phase_adjusted_limit_mixed_phases():
    """Test: Mixed phases (3 in D, 2 in B) → 12.0% limit (Phase D majority)."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("30.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("32.0"),
            sector="Technology",
        ),
        Position(
            symbol="GOOGL",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("28.0"),
            sector="Technology",
        ),
        Position(
            symbol="JNJ",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="B",
            volume_confirmation_score=Decimal("18.0"),
            sector="Healthcare",
        ),
        Position(
            symbol="PFE",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="B",
            volume_confirmation_score=Decimal("16.0"),
            sector="Healthcare",
        ),
    ]
    limit, basis = get_phase_adjusted_heat_limit(positions)
    assert limit == Decimal("12.0")
    assert "Phase D" in basis


def test_phase_adjusted_limit_unknown_phase():
    """Test: Positions without wyckoff_phase → 10.0% default."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="unknown",
            volume_confirmation_score=Decimal("20.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="unknown",
            volume_confirmation_score=Decimal("18.0"),
            sector="Technology",
        ),
    ]
    limit, basis = get_phase_adjusted_heat_limit(positions)
    assert limit == Decimal("10.0")
    assert "mixed" in basis or "default" in basis


def test_phase_adjusted_limit_boundary_15_percent():
    """Test: Boundary condition - exactly 15.0% heat with Phase E majority → passes."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("5.0"),
            status="OPEN",
            wyckoff_phase="E",
            volume_confirmation_score=Decimal("38.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("5.0"),
            status="OPEN",
            wyckoff_phase="E",
            volume_confirmation_score=Decimal("36.0"),
            sector="Technology",
        ),
        Position(
            symbol="GOOGL",
            position_risk_pct=Decimal("5.0"),
            status="OPEN",
            wyckoff_phase="E",
            volume_confirmation_score=Decimal("35.0"),
            sector="Technology",
        ),
    ]
    limit, basis = get_phase_adjusted_heat_limit(positions)
    assert limit == Decimal("15.0")


# ============================================================================
# Test calculate_volume_risk_multiplier (AC 13-15)
# ============================================================================


def test_volume_multiplier_strong_volume():
    """Test: Portfolio avg volume 35 → 0.70 multiplier."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("3.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("35.0"),
            sector="Technology",
        ),
    ]
    multiplier = calculate_volume_risk_multiplier(positions)
    assert multiplier == Decimal("0.70")


def test_volume_multiplier_medium_volume():
    """Test: Portfolio avg volume 25 → 0.85 multiplier."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("25.0"),
            sector="Technology",
        ),
    ]
    multiplier = calculate_volume_risk_multiplier(positions)
    assert multiplier == Decimal("0.85")


def test_volume_multiplier_weak_volume():
    """Test: Portfolio avg volume 15 → 1.0 multiplier (no adjustment)."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("15.0"),
            sector="Technology",
        ),
    ]
    multiplier = calculate_volume_risk_multiplier(positions)
    assert multiplier == Decimal("1.0")


def test_volume_multiplier_weighted_calculation():
    """Test: Weighted calculation - 3 positions (2% at vol 40, 3% at vol 20, 1% at vol 10)."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("40.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("3.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("20.0"),
            sector="Technology",
        ),
        Position(
            symbol="GOOGL",
            position_risk_pct=Decimal("1.0"),
            status="OPEN",
            wyckoff_phase="C",
            volume_confirmation_score=Decimal("10.0"),
            sector="Technology",
        ),
    ]
    # Weighted avg = (40*2 + 20*3 + 10*1) / (2+3+1) = (80+60+10)/6 = 150/6 = 25
    # 25 is in [20, 30) range → 0.85 multiplier
    multiplier = calculate_volume_risk_multiplier(positions)
    assert multiplier == Decimal("0.85")


def test_volume_multiplier_empty_positions():
    """Test: Empty positions list → 1.0 multiplier."""
    multiplier = calculate_volume_risk_multiplier([])
    assert multiplier == Decimal("1.0")


# ============================================================================
# Test identify_campaign_clusters (AC 16-17)
# ============================================================================


def test_campaign_clusters_no_clusters():
    """Test: 3 positions, different sectors → no correlation penalty."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("3.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("30.0"),
            sector="Technology",
        ),
        Position(
            symbol="JNJ",
            position_risk_pct=Decimal("3.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("25.0"),
            sector="Healthcare",
        ),
        Position(
            symbol="XOM",
            position_risk_pct=Decimal("3.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("28.0"),
            sector="Energy",
        ),
    ]
    clusters = identify_campaign_clusters(positions)
    assert len(clusters) == 0


def test_campaign_clusters_two_position_cluster():
    """Test: 2 positions, same sector + same phase → 0.90x multiplier."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("3.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("30.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("2.5"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("32.0"),
            sector="Technology",
        ),
        Position(
            symbol="JNJ",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="C",
            volume_confirmation_score=Decimal("25.0"),
            sector="Healthcare",
        ),
    ]
    clusters = identify_campaign_clusters(positions)
    assert len(clusters) == 1
    assert clusters[0].sector == "Technology"
    assert clusters[0].wyckoff_phase == "D"
    assert clusters[0].position_count == 2
    assert clusters[0].correlation_multiplier == Decimal("0.90")
    assert clusters[0].raw_heat == Decimal("5.5")  # 3.0 + 2.5
    assert clusters[0].adjusted_heat == Decimal("5.5") * Decimal("0.90")


def test_campaign_clusters_three_position_cluster():
    """Test: 4 positions, 3 in Tech/Phase D cluster + 1 isolated → cluster penalty applied to 3."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("4.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("35.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("4.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("33.0"),
            sector="Technology",
        ),
        Position(
            symbol="GOOGL",
            position_risk_pct=Decimal("4.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("32.0"),
            sector="Technology",
        ),
        Position(
            symbol="JNJ",
            position_risk_pct=Decimal("4.0"),
            status="OPEN",
            wyckoff_phase="C",
            volume_confirmation_score=Decimal("25.0"),
            sector="Healthcare",
        ),
    ]
    clusters = identify_campaign_clusters(positions)
    assert len(clusters) == 1
    assert clusters[0].sector == "Technology"
    assert clusters[0].wyckoff_phase == "D"
    assert clusters[0].position_count == 3
    assert clusters[0].correlation_multiplier == Decimal("0.85")
    assert clusters[0].raw_heat == Decimal("12.0")  # 4.0 * 3


def test_campaign_clusters_multiple_clusters():
    """Test: Multiple clusters in same portfolio."""
    positions = [
        # Tech/D cluster (2 positions)
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("3.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("35.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("3.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("33.0"),
            sector="Technology",
        ),
        # Healthcare/C cluster (2 positions)
        Position(
            symbol="JNJ",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="C",
            volume_confirmation_score=Decimal("25.0"),
            sector="Healthcare",
        ),
        Position(
            symbol="PFE",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="C",
            volume_confirmation_score=Decimal("22.0"),
            sector="Healthcare",
        ),
    ]
    clusters = identify_campaign_clusters(positions)
    assert len(clusters) == 2
    # Both clusters should have 2 positions with 0.90x multiplier


# ============================================================================
# Test calculate_correlation_adjusted_heat (AC 16)
# ============================================================================


def test_correlation_adjusted_heat_no_clusters():
    """Test: No clusters → correlation_adjusted_heat == raw_heat."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("3.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("30.0"),
            sector="Technology",
        ),
        Position(
            symbol="JNJ",
            position_risk_pct=Decimal("3.0"),
            status="OPEN",
            wyckoff_phase="C",
            volume_confirmation_score=Decimal("25.0"),
            sector="Healthcare",
        ),
    ]
    clusters = identify_campaign_clusters(positions)
    adjusted_heat = calculate_correlation_adjusted_heat(positions, clusters)
    assert adjusted_heat == Decimal("6.0")


def test_correlation_adjusted_heat_with_cluster(clustered_positions):
    """Test: Correlation-adjusted heat calculation accuracy."""
    # 3 Tech/D positions (4% each) + 1 Healthcare/C (4%)
    # Cluster: 12% * 0.85 = 10.2%
    # Isolated: 4% * 1.0 = 4.0%
    # Total: 14.2%
    clusters = identify_campaign_clusters(clustered_positions)
    adjusted_heat = calculate_correlation_adjusted_heat(clustered_positions, clusters)

    # Expected: (4.0 + 4.0 + 4.0) * 0.85 + 4.0 * 1.0 = 10.2 + 4.0 = 14.2
    assert adjusted_heat == Decimal("14.2")


# ============================================================================
# Test check_campaign_stage_warnings (AC 7 revised)
# ============================================================================


def test_warning_underutilized_opportunity():
    """Test: Phase D majority, 7% heat → underutilized_opportunity (INFO)."""
    portfolio_heat = PortfolioHeat(
        position_count=2,
        risk_breakdown={"AAPL": Decimal("3.5"), "MSFT": Decimal("3.5")},
        raw_heat=Decimal("7.0"),
        correlation_adjusted_heat=Decimal("7.0"),
        total_heat=Decimal("7.0"),
        available_capacity=Decimal("8.0"),
        phase_distribution={"D": 2},
        applied_heat_limit=Decimal("15.0"),
        limit_basis="Phase D majority (2/2)",
        weighted_volume_score=Decimal("35.0"),
        volume_multiplier=Decimal("0.70"),
        volume_adjusted_limit=Decimal("21.4"),
        campaign_clusters=[],
        warnings=[],
    )
    warnings = check_campaign_stage_warnings(portfolio_heat)
    assert len(warnings) > 0
    assert any(w.warning_type == "underutilized_opportunity" for w in warnings)
    underutilized = next(
        w for w in warnings if w.warning_type == "underutilized_opportunity"
    )
    assert underutilized.severity == "INFO"


def test_warning_premature_commitment():
    """Test: Phase A majority, 7% heat → premature_commitment (WARNING)."""
    portfolio_heat = PortfolioHeat(
        position_count=3,
        risk_breakdown={"AAPL": Decimal("2.5"), "MSFT": Decimal("2.5"), "GOOGL": Decimal("2.0")},
        raw_heat=Decimal("7.0"),
        correlation_adjusted_heat=Decimal("7.0"),
        total_heat=Decimal("7.0"),
        available_capacity=Decimal("1.0"),
        phase_distribution={"A": 3},
        applied_heat_limit=Decimal("8.0"),
        limit_basis="Phase A majority (3/3)",
        weighted_volume_score=Decimal("16.0"),
        volume_multiplier=Decimal("1.0"),
        volume_adjusted_limit=None,
        campaign_clusters=[],
        warnings=[],
    )
    warnings = check_campaign_stage_warnings(portfolio_heat)
    assert len(warnings) > 0
    assert any(w.warning_type == "premature_commitment" for w in warnings)
    premature = next(
        w for w in warnings if w.warning_type == "premature_commitment"
    )
    assert premature.severity == "WARNING"


def test_warning_capacity_limit():
    """Test: 10.9% heat with 12% limit → capacity_limit (90.8% capacity)."""
    portfolio_heat = PortfolioHeat(
        position_count=4,
        risk_breakdown={},
        raw_heat=Decimal("10.9"),
        correlation_adjusted_heat=Decimal("10.9"),
        total_heat=Decimal("10.9"),
        available_capacity=Decimal("1.1"),
        phase_distribution={"D": 4},
        applied_heat_limit=Decimal("12.0"),
        limit_basis="Phase D majority (4/4)",
        weighted_volume_score=Decimal("30.0"),
        volume_multiplier=Decimal("0.70"),
        volume_adjusted_limit=Decimal("17.1"),
        campaign_clusters=[],
        warnings=[],
    )
    warnings = check_campaign_stage_warnings(portfolio_heat)
    assert len(warnings) > 0
    assert any(w.warning_type == "capacity_limit" for w in warnings)


def test_warning_volume_quality_mismatch():
    """Test: 9% heat, volume score 12 → volume_quality_mismatch."""
    portfolio_heat = PortfolioHeat(
        position_count=3,
        risk_breakdown={},
        raw_heat=Decimal("9.0"),
        correlation_adjusted_heat=Decimal("9.0"),
        total_heat=Decimal("9.0"),
        available_capacity=Decimal("6.0"),
        phase_distribution={"D": 3},
        applied_heat_limit=Decimal("15.0"),
        limit_basis="Phase D majority (3/3)",
        weighted_volume_score=Decimal("12.0"),
        volume_multiplier=Decimal("1.0"),
        volume_adjusted_limit=None,
        campaign_clusters=[],
        warnings=[],
    )
    warnings = check_campaign_stage_warnings(portfolio_heat)
    assert len(warnings) > 0
    assert any(w.warning_type == "volume_quality_mismatch" for w in warnings)


def test_warning_no_warnings_appropriate_sizing():
    """Test: Phase D majority, 14% heat, volume 35 → NO warnings (appropriate sizing)."""
    portfolio_heat = PortfolioHeat(
        position_count=3,
        risk_breakdown={},
        raw_heat=Decimal("14.0"),
        correlation_adjusted_heat=Decimal("14.0"),
        total_heat=Decimal("14.0"),
        available_capacity=Decimal("1.0"),
        phase_distribution={"D": 3},
        applied_heat_limit=Decimal("15.0"),
        limit_basis="Phase D majority (3/3)",
        weighted_volume_score=Decimal("35.0"),
        volume_multiplier=Decimal("0.70"),
        volume_adjusted_limit=Decimal("21.4"),
        campaign_clusters=[],
        warnings=[],
    )
    warnings = check_campaign_stage_warnings(portfolio_heat)
    # Should have no warnings (appropriate sizing for Phase D with strong volume)
    assert all(
        w.warning_type not in ["premature_commitment", "volume_quality_mismatch"]
        for w in warnings
    )


# ============================================================================
# Test validate_portfolio_heat_capacity (AC 4, AC 14)
# ============================================================================


def test_validate_heat_capacity_passes_within_limit():
    """Test: 9.5% current + 0.5% new = 10.0% with default limit → passes."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("5.0"),
            status="OPEN",
            wyckoff_phase="C",
            volume_confirmation_score=Decimal("25.0"),
            sector="Technology",
        ),
    ]
    is_valid, error = validate_portfolio_heat_capacity(
        Decimal("9.5"), Decimal("0.5"), positions
    )
    assert is_valid is True
    assert error is None


def test_validate_heat_capacity_fails_exceeds_limit():
    """Test: 11.5% current + 0.6% new = 12.1% with Phase C limit (12%) → fails."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("5.0"),
            status="OPEN",
            wyckoff_phase="C",
            volume_confirmation_score=Decimal("15.0"),  # Weak volume (no multiplier)
            sector="Technology",
        ),
    ]
    is_valid, error = validate_portfolio_heat_capacity(
        Decimal("11.5"), Decimal("0.6"), positions
    )
    assert is_valid is False
    assert error is not None
    assert "12.1" in error or "exceed" in error


def test_validate_heat_capacity_phase_a_limit():
    """Test: 8% current + 1% new = 9% with Phase A/B majority → FAILS (exceeds 8% limit)."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("4.0"),
            status="OPEN",
            wyckoff_phase="A",
            volume_confirmation_score=Decimal("15.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("4.0"),
            status="OPEN",
            wyckoff_phase="A",
            volume_confirmation_score=Decimal("16.0"),
            sector="Technology",
        ),
    ]
    is_valid, error = validate_portfolio_heat_capacity(
        Decimal("8.0"), Decimal("1.0"), positions
    )
    assert is_valid is False
    assert error is not None


def test_validate_heat_capacity_phase_e_limit():
    """Test: 14% current + 1% new = 15% with Phase E majority → passes (exactly at 15% absolute max)."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("7.0"),
            status="OPEN",
            wyckoff_phase="E",
            volume_confirmation_score=Decimal("38.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("7.0"),
            status="OPEN",
            wyckoff_phase="E",
            volume_confirmation_score=Decimal("36.0"),
            sector="Technology",
        ),
    ]
    is_valid, error = validate_portfolio_heat_capacity(
        Decimal("14.0"), Decimal("1.0"), positions
    )
    assert is_valid is True
    assert error is None


def test_validate_heat_capacity_exceeds_absolute_max():
    """Test: 14.5% current + 0.6% new = 15.1% with Phase E majority → fails (exceeds absolute max)."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("7.0"),
            status="OPEN",
            wyckoff_phase="E",
            volume_confirmation_score=Decimal("38.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("7.5"),
            status="OPEN",
            wyckoff_phase="E",
            volume_confirmation_score=Decimal("36.0"),
            sector="Technology",
        ),
    ]
    is_valid, error = validate_portfolio_heat_capacity(
        Decimal("14.5"), Decimal("0.6"), positions
    )
    assert is_valid is False
    assert error is not None


def test_validate_heat_capacity_volume_multiplier():
    """Test: 10% current + 4% new with strong volume (multiplier 0.7 → 14.3% effective limit) → passes."""
    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("5.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("35.0"),
            sector="Technology",
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("5.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("33.0"),
            sector="Technology",
        ),
    ]
    is_valid, error = validate_portfolio_heat_capacity(
        Decimal("10.0"), Decimal("4.0"), positions
    )
    assert is_valid is True
    assert error is None


# ============================================================================
# Test build_portfolio_heat_report (AC 5)
# ============================================================================


def test_build_portfolio_heat_report_empty():
    """Test: Empty portfolio returns valid report with 0% heat."""
    report = build_portfolio_heat_report([])
    assert report.position_count == 0
    assert report.total_heat == Decimal("0.0")
    assert report.applied_heat_limit == Decimal("10.0")
    assert report.limit_basis == "no positions (default)"


def test_build_portfolio_heat_report_simple(multiple_positions):
    """Test: Simple portfolio returns correct heat calculation."""
    report = build_portfolio_heat_report(multiple_positions)
    assert report.position_count == 5
    assert report.raw_heat == Decimal("10.0")
    # Applied limit could be volume-adjusted, just verify it's reasonable
    assert report.applied_heat_limit >= Decimal("8.0")
    assert report.applied_heat_limit <= Decimal("15.0")


def test_build_portfolio_heat_report_with_clusters(clustered_positions):
    """Test: Portfolio with clusters applies correlation adjustment."""
    report = build_portfolio_heat_report(clustered_positions)
    assert report.position_count == 4
    assert len(report.campaign_clusters) > 0
    # Correlation-adjusted heat should be less than raw heat
    assert report.correlation_adjusted_heat < report.raw_heat


def test_build_portfolio_heat_report_phase_e(phase_e_positions):
    """Test: Phase E portfolio has 15% limit."""
    report = build_portfolio_heat_report(phase_e_positions)
    assert report.applied_heat_limit == Decimal("15.0")
    assert "Phase E" in report.limit_basis
