"""
Tests for Portfolio Correlation Matrix - Feature P2-7

Tests cover:
1. Correlation computation on known return series (math correctness)
2. Diagonal is always 1.0
3. Matrix is symmetric
4. Blocked pairs correctly identified above threshold
5. Empty / single-campaign edge cases
6. API endpoint response schema

Quant note: Pearson correlation is computed on daily RETURNS (pct_change),
not on raw prices. This is the statistically correct approach because
return series are stationary.
"""

import math

import numpy as np
import pytest

from src.api.routes.risk import (
    _build_mock_price_series,
    compute_correlation_matrix,
)
from src.models.correlation_matrix import BlockedPair, CorrelationMatrixResponse


class TestComputeCorrelationMatrix:
    """Unit tests for the compute_correlation_matrix function."""

    def test_diagonal_is_one(self) -> None:
        """Self-correlation must always be 1.0."""
        campaigns = ["AAPL-2024-01", "MSFT-2024-01", "JNJ-2024-01"]
        price_series = _build_mock_price_series(campaigns)
        matrix, _ = compute_correlation_matrix(campaigns, price_series)

        for i in range(len(campaigns)):
            assert matrix[i][i] == 1.0, f"Diagonal [{i}][{i}] should be 1.0"

    def test_matrix_is_symmetric(self) -> None:
        """Pearson correlation is symmetric: matrix[i][j] == matrix[j][i]."""
        campaigns = ["AAPL-2024-01", "MSFT-2024-01", "JNJ-2024-01"]
        price_series = _build_mock_price_series(campaigns)
        matrix, _ = compute_correlation_matrix(campaigns, price_series)

        n = len(campaigns)
        for i in range(n):
            for j in range(n):
                assert math.isclose(
                    matrix[i][j], matrix[j][i], abs_tol=1e-9
                ), f"Matrix not symmetric at [{i}][{j}]: {matrix[i][j]} != {matrix[j][i]}"

    def test_correlation_range(self) -> None:
        """All correlation values must be in [-1.0, 1.0]."""
        campaigns = ["AAPL-2024-01", "MSFT-2024-01", "GOOGL-2024-01", "JNJ-2024-01"]
        price_series = _build_mock_price_series(campaigns)
        matrix, _ = compute_correlation_matrix(campaigns, price_series)

        for row in matrix:
            for val in row:
                assert -1.0 <= val <= 1.0, f"Correlation value {val} out of [-1, 1] range"

    def test_tech_stocks_are_highly_correlated(self) -> None:
        """
        Tech stocks (AAPL, MSFT) should produce high correlation in mock data
        since they share 70% of the same market factor.
        """
        campaigns = ["AAPL-2024-01", "MSFT-2024-01"]
        price_series = _build_mock_price_series(campaigns)
        matrix, _ = compute_correlation_matrix(campaigns, price_series)

        aapl_msft_corr = matrix[0][1]
        assert aapl_msft_corr > 0.5, (
            f"Expected AAPL-MSFT correlation > 0.5, got {aapl_msft_corr}. "
            "Tech stocks should be highly correlated (same market factor)."
        )

    def test_tech_vs_healthcare_low_correlation(self) -> None:
        """
        Tech vs non-tech (JNJ) should produce low correlation in mock data.
        """
        campaigns = ["AAPL-2024-01", "JNJ-2024-01"]
        price_series = _build_mock_price_series(campaigns)
        matrix, _ = compute_correlation_matrix(campaigns, price_series)

        aapl_jnj_corr = matrix[0][1]
        assert aapl_jnj_corr < 0.5, (
            f"Expected AAPL-JNJ correlation < 0.5, got {aapl_jnj_corr}. "
            "Tech vs healthcare should be weakly correlated."
        )

    def test_blocked_pairs_above_threshold(self) -> None:
        """
        Pairs with correlation > threshold (0.6) must appear in blocked_pairs.
        """
        # Use perfect correlation: identical price series
        campaigns = ["A-2024-01", "B-2024-01"]
        prices = [float(100 + i) for i in range(61)]
        price_series = {"A-2024-01": prices, "B-2024-01": prices}

        matrix, blocked = compute_correlation_matrix(campaigns, price_series, threshold=0.6)

        # Identical series -> correlation = 1.0 -> should be blocked
        assert len(blocked) == 1
        assert blocked[0].campaign_a == "A-2024-01"
        assert blocked[0].campaign_b == "B-2024-01"
        assert blocked[0].correlation == 1.0

    def test_no_blocked_pairs_below_threshold(self) -> None:
        """
        Pairs with low correlation should NOT appear in blocked_pairs.

        Use a truly orthogonal return pair: one series has only positive returns
        on even days, the other only on odd days. Their Pearson correlation is 0.
        """
        n = 61
        # Build prices from two completely orthogonal return series:
        # series A: +0.01 on even indices, 0 on odd
        # series B: +0.01 on odd indices, 0 on even
        returns_a = [0.01 if i % 2 == 0 else 0.0 for i in range(n - 1)]
        returns_b = [0.01 if i % 2 != 0 else 0.0 for i in range(n - 1)]

        prices_a = [100.0]
        prices_b = [100.0]
        for r in returns_a:
            prices_a.append(prices_a[-1] * (1.0 + r))
        for r in returns_b:
            prices_b.append(prices_b[-1] * (1.0 + r))

        campaigns = ["A-2024-01", "B-2024-01"]
        price_series = {"A-2024-01": prices_a, "B-2024-01": prices_b}

        _, blocked = compute_correlation_matrix(campaigns, price_series, threshold=0.6)

        # Orthogonal returns -> correlation = 0 -> not blocked
        assert len(blocked) == 0

    def test_empty_campaigns(self) -> None:
        """Empty campaign list returns empty matrix and no blocked pairs."""
        matrix, blocked = compute_correlation_matrix([], {})

        assert matrix == []
        assert blocked == []

    def test_single_campaign(self) -> None:
        """Single campaign returns 1x1 identity matrix, no blocked pairs."""
        campaigns = ["AAPL-2024-01"]
        price_series = _build_mock_price_series(campaigns)
        matrix, blocked = compute_correlation_matrix(campaigns, price_series)

        assert matrix == [[1.0]]
        assert blocked == []

    def test_matrix_dimensions(self) -> None:
        """Matrix must be NxN matching the number of campaigns."""
        n = 4
        campaigns = [f"C{i}-2024-01" for i in range(n)]
        price_series = {c: [100.0 + float(i) for i in range(61)] for c in campaigns}

        matrix, _ = compute_correlation_matrix(campaigns, price_series)

        assert len(matrix) == n
        for row in matrix:
            assert len(row) == n


class TestBlockedPairModel:
    """Unit tests for the BlockedPair Pydantic model."""

    def test_blocked_pair_fields(self) -> None:
        """BlockedPair stores all required fields correctly."""
        pair = BlockedPair(
            campaign_a="AAPL-2024-01",
            campaign_b="MSFT-2024-01",
            correlation=0.78,
            reason="High correlation exceeds 0.6 threshold",
        )

        assert pair.campaign_a == "AAPL-2024-01"
        assert pair.campaign_b == "MSFT-2024-01"
        assert pair.correlation == 0.78
        assert "0.6" in pair.reason

    def test_correlation_bounds_enforced(self) -> None:
        """Pydantic should reject correlation values outside [-1, 1]."""
        with pytest.raises(Exception):
            BlockedPair(
                campaign_a="A",
                campaign_b="B",
                correlation=1.5,  # Invalid
                reason="test",
            )


class TestCorrelationMatrixResponse:
    """Unit tests for the CorrelationMatrixResponse Pydantic model."""

    def test_response_serialization(self) -> None:
        """CorrelationMatrixResponse serializes to dict correctly."""
        from datetime import UTC, datetime

        campaigns = ["AAPL-2024-01", "MSFT-2024-01"]
        matrix = [[1.0, 0.75], [0.75, 1.0]]
        blocked = [
            BlockedPair(
                campaign_a="AAPL-2024-01",
                campaign_b="MSFT-2024-01",
                correlation=0.75,
                reason="Exceeds threshold",
            )
        ]

        response = CorrelationMatrixResponse(
            campaigns=campaigns,
            matrix=matrix,
            blocked_pairs=blocked,
            heat_threshold=0.6,
            last_updated=datetime.now(UTC),
        )

        data = response.model_dump()
        assert data["campaigns"] == campaigns
        assert data["matrix"] == matrix
        assert len(data["blocked_pairs"]) == 1
        assert data["heat_threshold"] == 0.6

    def test_default_heat_threshold(self) -> None:
        """Default heat_threshold should be 0.6 per CLAUDE.md correlated risk rules."""
        from datetime import UTC, datetime

        response = CorrelationMatrixResponse(
            campaigns=[],
            matrix=[],
            blocked_pairs=[],
            last_updated=datetime.now(UTC),
        )

        assert response.heat_threshold == 0.6


class TestBuildMockPriceSeries:
    """Tests for the mock price series generator."""

    def test_returns_series_for_all_campaigns(self) -> None:
        """Each campaign should get a price series."""
        campaigns = ["AAPL-2024-01", "JNJ-2024-01"]
        series = _build_mock_price_series(campaigns)

        assert set(series.keys()) == set(campaigns)

    def test_series_length_is_61(self) -> None:
        """Each price series should have 61 entries (60 returns after pct_change)."""
        campaigns = ["AAPL-2024-01"]
        series = _build_mock_price_series(campaigns)

        assert len(series["AAPL-2024-01"]) == 61

    def test_prices_positive(self) -> None:
        """All prices must be positive (price can't go below zero)."""
        campaigns = ["AAPL-2024-01", "MSFT-2024-01", "JNJ-2024-01"]
        series = _build_mock_price_series(campaigns)

        for campaign, prices in series.items():
            for price in prices:
                assert price > 0, f"Price <= 0 in {campaign} series"

    def test_deterministic(self) -> None:
        """Same campaign always produces the same price series."""
        campaigns = ["AAPL-2024-01"]
        series1 = _build_mock_price_series(campaigns)
        series2 = _build_mock_price_series(campaigns)

        np.testing.assert_array_almost_equal(
            series1["AAPL-2024-01"],
            series2["AAPL-2024-01"],
        )
