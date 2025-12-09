"""
Unit Tests for Risk Dashboard API (Story 10.6)

Tests for:
- GET /api/v1/risk/dashboard endpoint
- Risk dashboard data aggregation
- Campaign risk calculation with Wyckoff phase distribution
- Correlated risk calculation by sector
- Proximity warning generation
- Data model serialization

Author: Story 10.6
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.portfolio import Position
from src.models.risk_dashboard import (
    CampaignRiskSummary,
    CorrelatedRiskSummary,
    RiskDashboardData,
)


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_positions():
    """Create mock open positions for testing."""
    campaign_id_1 = UUID("12345678-1234-5678-1234-567812345678")
    campaign_id_2 = UUID("87654321-4321-8765-4321-876543218765")

    return [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("2.3"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("35.0"),
            sector="Technology",
            campaign_id=campaign_id_1,
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("1.8"),
            status="OPEN",
            wyckoff_phase="C",
            volume_confirmation_score=Decimal("28.0"),
            sector="Technology",
            campaign_id=campaign_id_1,
        ),
        Position(
            symbol="JNJ",
            position_risk_pct=Decimal("1.5"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("30.0"),
            sector="Healthcare",
            campaign_id=campaign_id_2,
        ),
        Position(
            symbol="PFE",
            position_risk_pct=Decimal("1.6"),
            status="OPEN",
            wyckoff_phase="C",
            volume_confirmation_score=Decimal("25.0"),
            sector="Healthcare",
            campaign_id=campaign_id_2,
        ),
    ]


# ============================================================================
# API Endpoint Tests
# ============================================================================


@patch("src.api.routes.risk.get_open_positions", new_callable=AsyncMock)
@patch("src.api.routes.risk.get_heat_history_7d", new_callable=AsyncMock)
def test_get_risk_dashboard_success(mock_heat_history, mock_positions_func, client, mock_positions):
    """Test GET /api/v1/risk/dashboard returns complete dashboard data (AC: 1-10)."""
    # Setup mocks
    mock_positions_func.return_value = mock_positions
    mock_heat_history.return_value = []

    # Call endpoint
    response = client.get("/api/v1/risk/dashboard")

    # Assert response
    assert response.status_code == 200

    data = response.json()

    # Check core fields present (AC: 1-3)
    assert "total_heat" in data
    assert "total_heat_limit" in data
    assert "available_capacity" in data
    assert "estimated_signals_capacity" in data
    assert "per_trade_risk_range" in data

    # Check risk breakdown fields (AC: 4-5)
    assert "campaign_risks" in data
    assert "correlated_risks" in data

    # Check warning and history fields (AC: 6-7)
    assert "proximity_warnings" in data
    assert "heat_history_7d" in data
    assert "last_updated" in data


@patch("src.api.routes.risk.get_open_positions", new_callable=AsyncMock)
@patch("src.api.routes.risk.get_heat_history_7d", new_callable=AsyncMock)
def test_risk_dashboard_calculates_total_heat(
    mock_heat_history, mock_positions_func, client, mock_positions
):
    """Test dashboard correctly calculates total portfolio heat (AC: 1)."""
    mock_positions_func.return_value = mock_positions
    mock_heat_history.return_value = []

    response = client.get("/api/v1/risk/dashboard")
    data = response.json()

    # Total heat should be sum of all position risks
    # 2.3 + 1.8 + 1.5 + 1.6 = 7.2
    assert data["total_heat"] == "7.2"
    assert data["total_heat_limit"] == "10.0"


@patch("src.api.routes.risk.get_open_positions", new_callable=AsyncMock)
@patch("src.api.routes.risk.get_heat_history_7d", new_callable=AsyncMock)
def test_risk_dashboard_calculates_available_capacity(
    mock_heat_history, mock_positions_func, client, mock_positions
):
    """Test dashboard correctly calculates available capacity (AC: 3)."""
    mock_positions_func.return_value = mock_positions
    mock_heat_history.return_value = []

    response = client.get("/api/v1/risk/dashboard")
    data = response.json()

    # Available capacity = 10.0 - 7.2 = 2.8
    assert data["available_capacity"] == "2.8"
    assert data["estimated_signals_capacity"] >= 0  # Should estimate number of signals


@patch("src.api.routes.risk.get_open_positions", new_callable=AsyncMock)
@patch("src.api.routes.risk.get_heat_history_7d", new_callable=AsyncMock)
def test_risk_dashboard_includes_campaign_risks(
    mock_heat_history, mock_positions_func, client, mock_positions
):
    """Test dashboard includes campaign risk summaries (AC: 4-5)."""
    mock_positions_func.return_value = mock_positions
    mock_heat_history.return_value = []

    response = client.get("/api/v1/risk/dashboard")
    data = response.json()

    # Should have 2 campaigns
    assert len(data["campaign_risks"]) == 2

    # Check first campaign structure
    campaign = data["campaign_risks"][0]
    assert "campaign_id" in campaign
    assert "risk_allocated" in campaign
    assert "positions_count" in campaign
    assert "campaign_limit" in campaign

    # MVP CRITICAL: Check phase_distribution field present (AC: 4-5)
    assert "phase_distribution" in campaign
    assert isinstance(campaign["phase_distribution"], dict)


@patch("src.api.routes.risk.get_open_positions", new_callable=AsyncMock)
@patch("src.api.routes.risk.get_heat_history_7d", new_callable=AsyncMock)
def test_risk_dashboard_phase_distribution_accuracy(
    mock_heat_history, mock_positions_func, client, mock_positions
):
    """Test campaign phase distribution is accurately calculated (MVP CRITICAL)."""
    mock_positions_func.return_value = mock_positions
    mock_heat_history.return_value = []

    response = client.get("/api/v1/risk/dashboard")
    data = response.json()

    # Find campaign with AAPL+MSFT (phases D and C)
    tech_campaign = None
    for campaign in data["campaign_risks"]:
        phase_dist = campaign["phase_distribution"]
        if "C" in phase_dist and "D" in phase_dist:
            tech_campaign = campaign
            break

    assert tech_campaign is not None, "Technology campaign should exist with C and D phases"
    assert tech_campaign["phase_distribution"]["C"] == 1  # MSFT in Phase C
    assert tech_campaign["phase_distribution"]["D"] == 1  # AAPL in Phase D
    assert tech_campaign["positions_count"] == 2


@patch("src.api.routes.risk.get_open_positions", new_callable=AsyncMock)
@patch("src.api.routes.risk.get_heat_history_7d", new_callable=AsyncMock)
def test_risk_dashboard_includes_correlated_risks(
    mock_heat_history, mock_positions_func, client, mock_positions
):
    """Test dashboard includes correlated risk summaries by sector (AC: 4)."""
    mock_positions_func.return_value = mock_positions
    mock_heat_history.return_value = []

    response = client.get("/api/v1/risk/dashboard")
    data = response.json()

    # Should have 2 sectors (Technology, Healthcare)
    assert len(data["correlated_risks"]) == 2

    # Check sector structure
    sector = data["correlated_risks"][0]
    assert "sector" in sector
    assert "risk_allocated" in sector
    assert "sector_limit" in sector
    assert sector["sector_limit"] == "6.0"  # Fixed sector limit


@patch("src.api.routes.risk.get_open_positions", new_callable=AsyncMock)
@patch("src.api.routes.risk.get_heat_history_7d", new_callable=AsyncMock)
def test_risk_dashboard_generates_proximity_warnings(
    mock_heat_history, mock_positions_func, client
):
    """Test dashboard generates proximity warnings at 80% threshold (AC: 6)."""
    # Create positions that exceed 80% threshold (>8% portfolio heat)
    high_risk_positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("8.5"),  # Exceeds 8% threshold
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("35.0"),
            sector="Technology",
            campaign_id=None,
        ),
    ]

    mock_positions_func.return_value = high_risk_positions
    mock_heat_history.return_value = []

    response = client.get("/api/v1/risk/dashboard")
    data = response.json()

    # Should have proximity warning for portfolio heat
    assert len(data["proximity_warnings"]) > 0
    assert any("Portfolio heat at" in warning for warning in data["proximity_warnings"])


@patch("src.api.routes.risk.get_open_positions", new_callable=AsyncMock)
@patch("src.api.routes.risk.get_heat_history_7d", new_callable=AsyncMock)
def test_risk_dashboard_empty_positions(mock_heat_history, mock_positions_func, client):
    """Test dashboard handles empty positions list gracefully."""
    mock_positions_func.return_value = []
    mock_heat_history.return_value = []

    response = client.get("/api/v1/risk/dashboard")
    data = response.json()

    # Should return valid dashboard with zero heat
    assert response.status_code == 200
    assert data["total_heat"] == "0.0"
    assert data["available_capacity"] == "10.0"
    assert len(data["campaign_risks"]) == 0
    assert len(data["correlated_risks"]) == 0
    assert len(data["proximity_warnings"]) == 0


# ============================================================================
# Campaign Risk Calculation Tests
# ============================================================================


def test_calculate_campaign_risks_aggregates_by_campaign(mock_positions):
    """Test campaign risk calculation aggregates positions by campaign_id."""
    from src.api.routes.risk import calculate_campaign_risks

    campaign_risks = calculate_campaign_risks(mock_positions)

    # Should have 2 campaigns
    assert len(campaign_risks) == 2

    # Check risk allocation
    # Campaign 1: AAPL (2.3) + MSFT (1.8) = 4.1
    # Campaign 2: JNJ (1.5) + PFE (1.6) = 3.1
    risks = sorted([c.risk_allocated for c in campaign_risks], reverse=True)
    assert risks[0] == Decimal("4.1")
    assert risks[1] == Decimal("3.1")


def test_calculate_campaign_risks_includes_phase_distribution(mock_positions):
    """Test campaign risk calculation includes Wyckoff phase distribution (MVP CRITICAL)."""
    from src.api.routes.risk import calculate_campaign_risks

    campaign_risks = calculate_campaign_risks(mock_positions)

    # Check all campaigns have phase_distribution
    for campaign in campaign_risks:
        assert hasattr(campaign, "phase_distribution")
        assert isinstance(campaign.phase_distribution, dict)
        assert len(campaign.phase_distribution) > 0


def test_calculate_campaign_risks_empty_list():
    """Test campaign risk calculation handles empty positions list."""
    from src.api.routes.risk import calculate_campaign_risks

    campaign_risks = calculate_campaign_risks([])
    assert len(campaign_risks) == 0


# ============================================================================
# Correlated Risk Calculation Tests
# ============================================================================


def test_calculate_correlated_risks_aggregates_by_sector(mock_positions):
    """Test correlated risk calculation aggregates positions by sector."""
    from src.api.routes.risk import calculate_correlated_risks

    correlated_risks = calculate_correlated_risks(mock_positions)

    # Should have 2 sectors
    assert len(correlated_risks) == 2

    # Check risk allocation
    # Technology: AAPL (2.3) + MSFT (1.8) = 4.1
    # Healthcare: JNJ (1.5) + PFE (1.6) = 3.1
    sector_risks = {s.sector: s.risk_allocated for s in correlated_risks}
    assert sector_risks["Technology"] == Decimal("4.1")
    assert sector_risks["Healthcare"] == Decimal("3.1")


def test_calculate_correlated_risks_sets_sector_limit():
    """Test correlated risk calculation sets correct sector limit (6.0%)."""
    from src.api.routes.risk import calculate_correlated_risks

    positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("30.0"),
            sector="Technology",
            campaign_id=None,
        ),
    ]

    correlated_risks = calculate_correlated_risks(positions)
    assert len(correlated_risks) == 1
    assert correlated_risks[0].sector_limit == Decimal("6.0")


# ============================================================================
# Proximity Warning Tests
# ============================================================================


def test_generate_proximity_warnings_portfolio_threshold():
    """Test proximity warning generated when portfolio heat >80% (>8%)."""
    from src.api.routes.risk import generate_proximity_warnings

    warnings = generate_proximity_warnings(
        total_heat=Decimal("8.5"),
        campaign_risks=[],
        correlated_risks=[],
    )

    assert len(warnings) == 1
    assert "Portfolio heat at" in warnings[0]
    assert "capacity" in warnings[0]


def test_generate_proximity_warnings_campaign_threshold():
    """Test proximity warning generated when campaign risk >80% (>4%)."""
    from src.api.routes.risk import generate_proximity_warnings

    campaign_risks = [
        CampaignRiskSummary(
            campaign_id="C-12345678",
            risk_allocated=Decimal("4.2"),  # Exceeds 4% threshold
            positions_count=2,
            campaign_limit=Decimal("5.0"),
            phase_distribution={"D": 2},
        )
    ]

    warnings = generate_proximity_warnings(
        total_heat=Decimal("5.0"),
        campaign_risks=campaign_risks,
        correlated_risks=[],
    )

    assert len(warnings) == 1
    assert "Campaign C-12345678 at" in warnings[0]


def test_generate_proximity_warnings_sector_threshold():
    """Test proximity warning generated when sector risk >80% (>4.8%)."""
    from src.api.routes.risk import generate_proximity_warnings

    correlated_risks = [
        CorrelatedRiskSummary(
            sector="Technology",
            risk_allocated=Decimal("5.0"),  # Exceeds 4.8% threshold
            sector_limit=Decimal("6.0"),
        )
    ]

    warnings = generate_proximity_warnings(
        total_heat=Decimal("5.0"),
        campaign_risks=[],
        correlated_risks=correlated_risks,
    )

    assert len(warnings) == 1
    assert "Technology sector at" in warnings[0]


def test_generate_proximity_warnings_multiple_warnings():
    """Test multiple proximity warnings generated when multiple limits exceeded."""
    from src.api.routes.risk import generate_proximity_warnings

    campaign_risks = [
        CampaignRiskSummary(
            campaign_id="C-1",
            risk_allocated=Decimal("4.5"),
            positions_count=2,
            campaign_limit=Decimal("5.0"),
            phase_distribution={"D": 2},
        )
    ]

    correlated_risks = [
        CorrelatedRiskSummary(
            sector="Technology",
            risk_allocated=Decimal("5.2"),
            sector_limit=Decimal("6.0"),
        )
    ]

    warnings = generate_proximity_warnings(
        total_heat=Decimal("8.5"),  # Portfolio warning
        campaign_risks=campaign_risks,  # Campaign warning
        correlated_risks=correlated_risks,  # Sector warning
    )

    # Should have 3 warnings
    assert len(warnings) == 3


def test_generate_proximity_warnings_no_warnings_below_threshold():
    """Test no proximity warnings generated when all limits below 80%."""
    from src.api.routes.risk import generate_proximity_warnings

    campaign_risks = [
        CampaignRiskSummary(
            campaign_id="C-1",
            risk_allocated=Decimal("2.0"),  # Well below threshold
            positions_count=1,
            campaign_limit=Decimal("5.0"),
            phase_distribution={"D": 1},
        )
    ]

    warnings = generate_proximity_warnings(
        total_heat=Decimal("3.0"),  # Below 8% threshold
        campaign_risks=campaign_risks,
        correlated_risks=[],
    )

    assert len(warnings) == 0


# ============================================================================
# Data Model Serialization Tests
# ============================================================================


def test_risk_dashboard_data_serializes_to_json():
    """Test RiskDashboardData model serializes correctly to JSON."""
    from datetime import UTC, datetime

    data = RiskDashboardData(
        total_heat=Decimal("7.2"),
        total_heat_limit=Decimal("10.0"),
        available_capacity=Decimal("2.8"),
        estimated_signals_capacity=3,
        per_trade_risk_range="0.5-1.0% per signal",
        campaign_risks=[],
        correlated_risks=[],
        proximity_warnings=[],
        heat_history_7d=[],
        last_updated=datetime.now(UTC),
    )

    # Should serialize without errors
    json_data = data.model_dump()
    assert json_data["total_heat"] == Decimal("7.2")
    assert json_data["estimated_signals_capacity"] == 3


def test_campaign_risk_summary_serializes_phase_distribution():
    """Test CampaignRiskSummary correctly serializes phase_distribution dict."""
    summary = CampaignRiskSummary(
        campaign_id="C-1",
        risk_allocated=Decimal("2.3"),
        positions_count=2,
        campaign_limit=Decimal("5.0"),
        phase_distribution={"C": 1, "D": 1},
    )

    json_data = summary.model_dump()
    assert json_data["phase_distribution"] == {"C": 1, "D": 1}
