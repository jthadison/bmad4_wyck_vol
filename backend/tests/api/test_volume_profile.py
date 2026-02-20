"""
Tests for Volume Profile by Wyckoff Phase (P3-F13).

Tests the core compute_volume_profile_by_phase algorithm and the API endpoint.
Key validations:
- Volume conservation: sum(bin volumes) == sum(bar volumes) within tolerance
- POC identification: bin with max volume per phase
- Value area: 70% of phase volume contained within VA bounds
- API endpoint returns 200 with valid structure
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from src.models.ohlcv import OHLCVBar
from src.pattern_engine.volume_profile import compute_volume_profile_by_phase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bar(
    price: float,
    volume: int,
    symbol: str = "TEST",
    timeframe: str = "1d",
    day_offset: int = 0,
) -> OHLCVBar:
    """Create a simple bar at a fixed price level."""
    ts = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=day_offset)
    p = Decimal(str(round(price, 2)))
    spread = Decimal("1.00")
    return OHLCVBar(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=ts,
        open=p,
        high=p + Decimal("0.50"),
        low=p - Decimal("0.50"),
        close=p,
        volume=volume,
        spread=spread,
    )


def _make_bars_and_labels(
    prices_volumes_phases: list[tuple[float, int, str]],
) -> tuple[list[OHLCVBar], list[str]]:
    """Create bars and phase labels from (price, volume, phase) tuples."""
    bars = []
    labels = []
    for i, (price, vol, phase) in enumerate(prices_volumes_phases):
        bars.append(_make_bar(price, vol, day_offset=i))
        labels.append(phase)
    return bars, labels


# ---------------------------------------------------------------------------
# Algorithm Tests
# ---------------------------------------------------------------------------


class TestComputeVolumeProfile:
    """Tests for compute_volume_profile_by_phase core algorithm."""

    def test_conservation_total_volume(self):
        """Sum of all combined bin volumes must equal sum of all bar volumes."""
        bars, labels = _make_bars_and_labels(
            [
                (100.0, 1000, "A"),
                (101.0, 2000, "A"),
                (102.0, 1500, "B"),
                (103.0, 3000, "B"),
                (104.0, 500, "C"),
            ]
        )

        result = compute_volume_profile_by_phase(bars, labels, num_bins=20)

        total_bar_volume = sum(b.volume for b in bars)
        total_bin_volume = sum(bn.volume for bn in result.combined.bins)

        # Tolerance 0.1% for floating-point rounding
        assert abs(total_bin_volume - total_bar_volume) / total_bar_volume < 0.001

    def test_conservation_per_phase(self):
        """Sum of per-phase bin volumes must equal phase total volume."""
        bars, labels = _make_bars_and_labels(
            [
                (100.0, 1000, "A"),
                (101.0, 2000, "A"),
                (105.0, 1500, "B"),
                (106.0, 3000, "B"),
            ]
        )

        result = compute_volume_profile_by_phase(bars, labels, num_bins=30)

        for phase_data in result.phases:
            bin_sum = sum(bn.volume for bn in phase_data.bins)
            assert abs(bin_sum - phase_data.total_volume) < 1.0

    def test_poc_is_max_volume_bin(self):
        """POC must be the bin with the highest volume for each phase."""
        bars, labels = _make_bars_and_labels(
            [
                (100.0, 100, "A"),
                (100.0, 100, "A"),
                (105.0, 5000, "A"),  # This should be POC
                (110.0, 200, "A"),
            ]
        )

        result = compute_volume_profile_by_phase(bars, labels, num_bins=20)
        phase_a = next(p for p in result.phases if p.phase == "A")

        poc_bins = [b for b in phase_a.bins if b.is_poc]
        assert len(poc_bins) == 1

        max_vol_bin = max(phase_a.bins, key=lambda b: b.volume)
        assert poc_bins[0].price_level == max_vol_bin.price_level

    def test_value_area_contains_70_percent(self):
        """Value area bins should contain at least 70% of phase volume."""
        bars, labels = _make_bars_and_labels(
            [
                (100.0, 1000, "A"),
                (101.0, 2000, "A"),
                (102.0, 5000, "A"),
                (103.0, 3000, "A"),
                (104.0, 1000, "A"),
                (105.0, 500, "A"),
                (106.0, 200, "A"),
            ]
        )

        result = compute_volume_profile_by_phase(bars, labels, num_bins=30)
        phase_a = next(p for p in result.phases if p.phase == "A")

        va_volume = sum(b.volume for b in phase_a.bins if b.in_value_area)
        total = phase_a.total_volume

        assert va_volume / total >= 0.70

    def test_pct_of_phase_volume_sums_to_1(self):
        """Percentages within a phase should sum to approximately 1.0."""
        bars, labels = _make_bars_and_labels(
            [
                (100.0, 1000, "B"),
                (105.0, 2000, "B"),
                (110.0, 3000, "B"),
            ]
        )

        result = compute_volume_profile_by_phase(bars, labels, num_bins=25)
        phase_b = next(p for p in result.phases if p.phase == "B")

        pct_sum = sum(b.pct_of_phase_volume for b in phase_b.bins)
        assert abs(pct_sum - 1.0) < 0.01

    def test_multiple_phases_present(self):
        """Result should contain entries for all phases found in labels."""
        bars, labels = _make_bars_and_labels(
            [
                (100.0, 1000, "A"),
                (101.0, 2000, "B"),
                (102.0, 3000, "C"),
                (103.0, 1500, "D"),
                (104.0, 500, "E"),
            ]
        )

        result = compute_volume_profile_by_phase(bars, labels, num_bins=20)

        phase_names = {p.phase for p in result.phases}
        assert phase_names == {"A", "B", "C", "D", "E"}

    def test_combined_includes_all_phases(self):
        """Combined profile should aggregate across all phases."""
        bars, labels = _make_bars_and_labels(
            [
                (100.0, 1000, "A"),
                (101.0, 2000, "B"),
            ]
        )

        result = compute_volume_profile_by_phase(bars, labels, num_bins=20)

        assert result.combined.phase == "COMBINED"
        assert result.combined.bar_count == 2
        assert result.combined.total_volume == 3000.0

    def test_num_bins_respected(self):
        """Number of bins in result should match requested num_bins."""
        bars, labels = _make_bars_and_labels(
            [
                (100.0, 1000, "A"),
                (110.0, 2000, "A"),
            ]
        )

        for n in [20, 50, 75]:
            result = compute_volume_profile_by_phase(bars, labels, num_bins=n)
            assert len(result.combined.bins) == n

    def test_empty_bars_raises(self):
        """Empty bars list should raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            compute_volume_profile_by_phase([], [], num_bins=20)

    def test_length_mismatch_raises(self):
        """Mismatched bars/labels lengths should raise ValueError."""
        bars = [_make_bar(100.0, 1000)]
        with pytest.raises(ValueError, match="mismatch"):
            compute_volume_profile_by_phase(bars, ["A", "B"], num_bins=20)

    def test_current_price_is_last_close(self):
        """current_price should equal the last bar's close."""
        bars, labels = _make_bars_and_labels(
            [
                (100.0, 1000, "A"),
                (105.0, 2000, "A"),
            ]
        )

        result = compute_volume_profile_by_phase(bars, labels, num_bins=20)
        assert result.current_price == float(bars[-1].close)

    def test_poc_sensitivity_to_bin_count(self):
        """POC location should be stable across different bin counts."""
        # Create a clear concentration at 105
        data = [(105.0, 10000, "A")] * 10 + [(100.0, 100, "A")] * 5 + [(110.0, 100, "A")] * 5
        bars, labels = _make_bars_and_labels(data)

        poc_prices = []
        for n in [20, 30, 50, 80]:
            result = compute_volume_profile_by_phase(bars, labels, num_bins=n)
            phase_a = next(p for p in result.phases if p.phase == "A")
            poc_prices.append(phase_a.poc_price)

        # All POC prices should be near 105 (within a few bins)
        for poc in poc_prices:
            assert poc is not None
            assert abs(poc - 105.0) < 3.0


# ---------------------------------------------------------------------------
# API Endpoint Tests
# ---------------------------------------------------------------------------


class TestVolumeProfileEndpoint:
    """Tests for GET /api/v1/patterns/{symbol}/volume-profile."""

    @pytest.fixture
    def app(self):
        from src.api.main import app

        return app

    @pytest.mark.asyncio
    async def test_endpoint_returns_200(self, app):
        """Endpoint should return 200 with valid parameters."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/api/v1/patterns/AAPL/volume-profile",
                params={"timeframe": "1d", "bars": 50, "num_bins": 20},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "AAPL"
        assert data["num_bins"] == 20
        assert len(data["phases"]) > 0
        assert data["combined"]["phase"] == "COMBINED"

    @pytest.mark.asyncio
    async def test_endpoint_default_params(self, app):
        """Endpoint should work with default parameters."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/v1/patterns/SPY/volume-profile")

        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "SPY"
        assert data["num_bins"] == 50

    @pytest.mark.asyncio
    async def test_endpoint_validates_bars_range(self, app):
        """Bars parameter below minimum should return 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/api/v1/patterns/AAPL/volume-profile",
                params={"bars": 5},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_endpoint_validates_num_bins_range(self, app):
        """num_bins below minimum should return 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/api/v1/patterns/AAPL/volume-profile",
                params={"num_bins": 5},
            )

        assert resp.status_code == 422
