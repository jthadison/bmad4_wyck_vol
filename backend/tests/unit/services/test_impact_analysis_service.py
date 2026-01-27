"""
Unit tests for ImpactAnalysisService.

Tests impact calculation algorithms and pattern evaluation.
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

# Issue #238: Fixed message mismatches
from src.models.config import (
    CauseFactors,
    PatternConfidence,
    RiskLimits,
    SystemConfiguration,
    VolumeThresholds,
)
from src.services.impact_analysis_service import ImpactAnalysisService


@pytest.fixture
def mock_session():
    """Create mock database session."""
    return AsyncMock()


@pytest.fixture
def impact_service(mock_session):
    """Create ImpactAnalysisService with mock session."""
    return ImpactAnalysisService(mock_session)


@pytest.fixture
def current_config():
    """Create current configuration."""
    return SystemConfiguration(
        volume_thresholds=VolumeThresholds(
            spring_volume_min=Decimal("0.7"),
            spring_volume_max=Decimal("1.0"),
            sos_volume_min=Decimal("2.0"),
            lps_volume_min=Decimal("0.5"),
            utad_volume_max=Decimal("0.7"),
        ),
        risk_limits=RiskLimits(
            max_risk_per_trade=Decimal("2.0"),
            max_campaign_risk=Decimal("5.0"),
            max_portfolio_heat=Decimal("10.0"),
        ),
        cause_factors=CauseFactors(
            min_cause_factor=Decimal("2.0"), max_cause_factor=Decimal("3.0")
        ),
        pattern_confidence=PatternConfidence(
            min_spring_confidence=70,
            min_sos_confidence=70,
            min_lps_confidence=70,
            min_utad_confidence=70,
        ),
    )


@pytest.fixture
def sample_patterns():
    """Create sample pattern data for testing."""
    return [
        {
            "id": str(uuid4()),
            "symbol": "EURUSD",
            "pattern_type": "Spring",
            "detection_time": datetime(2025, 12, 1, 10, 0),
            "volume_ratio": 0.8,
            "confidence_score": 75,
            "cause_factor": 2.2,
            "metadata": {},
        },
        {
            "id": str(uuid4()),
            "symbol": "EURUSD",
            "pattern_type": "SOS",
            "detection_time": datetime(2025, 12, 2, 10, 0),
            "volume_ratio": 2.1,
            "confidence_score": 80,
            "cause_factor": 2.5,
            "metadata": {},
        },
        {
            "id": str(uuid4()),
            "symbol": "GBPUSD",
            "pattern_type": "Spring",
            "detection_time": datetime(2025, 12, 3, 10, 0),
            "volume_ratio": 0.6,
            "confidence_score": 65,
            "cause_factor": 2.1,
            "metadata": {},
        },
        {
            "id": str(uuid4()),
            "symbol": "GBPUSD",
            "pattern_type": "LPS",
            "detection_time": datetime(2025, 12, 4, 10, 0),
            "volume_ratio": 0.6,
            "confidence_score": 72,
            "cause_factor": 2.3,
            "metadata": {},
        },
    ]


class TestPatternQualification:
    """Tests for pattern qualification logic."""

    def test_spring_qualifies_with_valid_volume_and_confidence(
        self, impact_service, current_config
    ):
        """Test that spring pattern qualifies with valid parameters."""
        pattern = {
            "pattern_type": "Spring",
            "volume_ratio": 0.8,
            "confidence_score": 75,
            "cause_factor": 2.2,
        }

        result = impact_service._pattern_qualifies(pattern, current_config)
        assert result is True

    def test_spring_disqualified_by_high_volume(self, impact_service, current_config):
        """Test that spring is disqualified if volume too high."""
        pattern = {
            "pattern_type": "Spring",
            "volume_ratio": 1.1,  # Above max
            "confidence_score": 75,
            "cause_factor": 2.2,
        }

        result = impact_service._pattern_qualifies(pattern, current_config)
        assert result is False

    def test_spring_disqualified_by_low_confidence(self, impact_service, current_config):
        """Test that spring is disqualified if confidence too low."""
        pattern = {
            "pattern_type": "Spring",
            "volume_ratio": 0.8,
            "confidence_score": 65,  # Below 70 threshold
            "cause_factor": 2.2,
        }

        result = impact_service._pattern_qualifies(pattern, current_config)
        assert result is False

    def test_sos_qualifies_with_high_volume(self, impact_service, current_config):
        """Test that SOS qualifies with high volume."""
        pattern = {
            "pattern_type": "SOS",
            "volume_ratio": 2.1,
            "confidence_score": 80,
            "cause_factor": 2.5,
        }

        result = impact_service._pattern_qualifies(pattern, current_config)
        assert result is True

    def test_sos_disqualified_by_low_volume(self, impact_service, current_config):
        """Test that SOS is disqualified if volume too low."""
        pattern = {
            "pattern_type": "SOS",
            "volume_ratio": 1.3,  # Below 2.0 threshold
            "confidence_score": 80,
            "cause_factor": 2.5,
        }

        result = impact_service._pattern_qualifies(pattern, current_config)
        assert result is False

    def test_cause_factor_disqualifies_pattern(self, impact_service, current_config):
        """Test that invalid cause factor disqualifies pattern."""
        pattern = {
            "pattern_type": "Spring",
            "volume_ratio": 0.8,
            "confidence_score": 75,
            "cause_factor": 1.5,  # Below min of 2.0
        }

        result = impact_service._pattern_qualifies(pattern, current_config)
        assert result is False


class TestImpactAnalysis:
    """Tests for impact analysis calculations."""

    @pytest.mark.asyncio
    async def test_relaxed_volume_increases_signals(
        self, impact_service, current_config, sample_patterns
    ):
        """Test that relaxing volume threshold increases signal count."""
        # Mock pattern fetch
        impact_service._fetch_historical_patterns = AsyncMock(return_value=sample_patterns)

        # Create proposed config with relaxed spring volume
        proposed_config = current_config.model_copy(deep=True)
        proposed_config.volume_thresholds.spring_volume_min = Decimal("0.5")  # Lowered from 0.7

        result = await impact_service.analyze_config_impact(current_config, proposed_config)

        # Should have positive delta (more signals with relaxed threshold)
        assert result.signal_count_delta >= 0
        assert result.proposed_signal_count >= result.current_signal_count

    @pytest.mark.asyncio
    async def test_tightened_confidence_decreases_signals(
        self, impact_service, current_config, sample_patterns
    ):
        """Test that tightening confidence threshold decreases signal count."""
        # Mock pattern fetch
        impact_service._fetch_historical_patterns = AsyncMock(return_value=sample_patterns)

        # Create proposed config with higher confidence threshold
        proposed_config = current_config.model_copy(deep=True)
        proposed_config.pattern_confidence.min_spring_confidence = 80  # Raised from 70

        result = await impact_service.analyze_config_impact(current_config, proposed_config)

        # Should have negative delta (fewer signals with stricter threshold)
        assert result.signal_count_delta <= 0

    @pytest.mark.asyncio
    async def test_risk_impact_assessment(self, impact_service, current_config, sample_patterns):
        """Test risk impact assessment."""
        # Mock pattern fetch
        impact_service._fetch_historical_patterns = AsyncMock(return_value=sample_patterns)

        # Create proposed config with increased risk
        proposed_config = current_config.model_copy(deep=True)
        proposed_config.risk_limits.max_risk_per_trade = Decimal("2.5")

        result = await impact_service.analyze_config_impact(current_config, proposed_config)

        # Should report risk increase
        assert "Increased per-trade risk" in result.risk_impact

    @pytest.mark.asyncio
    async def test_win_rate_calculation(self, impact_service, current_config, sample_patterns):
        """Test win rate estimation."""
        # Mock pattern fetch
        impact_service._fetch_historical_patterns = AsyncMock(return_value=sample_patterns)

        result = await impact_service.analyze_config_impact(current_config, current_config)

        # Should calculate win rates
        assert result.current_win_rate is not None
        assert result.proposed_win_rate is not None
        assert Decimal("0.50") <= result.current_win_rate <= Decimal("0.85")

    @pytest.mark.asyncio
    async def test_confidence_range_calculation(
        self, impact_service, current_config, sample_patterns
    ):
        """Test confidence range calculation."""
        # Mock pattern fetch
        impact_service._fetch_historical_patterns = AsyncMock(return_value=sample_patterns)

        result = await impact_service.analyze_config_impact(current_config, current_config)

        # Should include confidence range
        assert "min" in result.confidence_range
        assert "max" in result.confidence_range
        assert result.confidence_range["min"] >= Decimal("0.0")
        assert result.confidence_range["max"] <= Decimal("1.0")

    @pytest.mark.asyncio
    async def test_recommendations_generated(self, impact_service, current_config, sample_patterns):
        """Test that recommendations are generated for changes."""
        # Mock pattern fetch
        impact_service._fetch_historical_patterns = AsyncMock(return_value=sample_patterns)

        # Create proposed config with relaxed spring volume
        proposed_config = current_config.model_copy(deep=True)
        proposed_config.volume_thresholds.spring_volume_min = Decimal("0.5")

        result = await impact_service.analyze_config_impact(current_config, proposed_config)

        # Should include recommendations
        assert len(result.recommendations) > 0
        assert any("spring volume" in rec.message.lower() for rec in result.recommendations)


class TestWinRateEstimation:
    """Tests for win rate estimation algorithm."""

    def test_win_rate_inversely_proportional_to_signal_count(self, impact_service):
        """Test that win rate decreases with more signals."""
        # Test with fewer patterns (should have higher win rate)
        patterns_few = [{"id": str(uuid4())} for _ in range(30)]
        win_rate_few = impact_service._calculate_win_rate(patterns_few)

        # Test with more patterns (should have lower win rate)
        patterns_many = [{"id": str(uuid4())} for _ in range(60)]
        win_rate_many = impact_service._calculate_win_rate(patterns_many)

        assert win_rate_few > win_rate_many

    def test_win_rate_clamped_to_reasonable_range(self, impact_service):
        """Test that win rate is clamped between 0.50 and 0.85."""
        # Test with very few patterns (should clamp to max)
        patterns_very_few = [{"id": str(uuid4())} for _ in range(5)]
        win_rate = impact_service._calculate_win_rate(patterns_very_few)
        assert win_rate <= Decimal("0.85")

        # Test with very many patterns (should clamp to min)
        patterns_very_many = [{"id": str(uuid4())} for _ in range(200)]
        win_rate = impact_service._calculate_win_rate(patterns_very_many)
        assert win_rate >= Decimal("0.50")

    def test_win_rate_none_for_empty_patterns(self, impact_service):
        """Test that win rate is None for empty pattern list."""
        win_rate = impact_service._calculate_win_rate([])
        assert win_rate is None
