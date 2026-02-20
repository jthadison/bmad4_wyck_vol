"""
Tests for the backtest comparison endpoint (Feature P2-9).

Tests cover:
- POST /api/v1/backtest/compare happy path with 2-4 valid run IDs
- 404 when a run_id is not found
- 400 validation when fewer than 2 or more than 4 run_ids supplied
- Equity curve is indexed to a common base value (10000)
- Parameter diffs correctly identify differing config parameters
- _index_equity_curve helper function
- _extract_param_diff helper function
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.api.routes.backtest.compare import _extract_param_diff, _index_equity_curve

# ---------------------------------------------------------------------------
# Unit tests for pure helper functions (no database needed)
# ---------------------------------------------------------------------------


class TestIndexEquityCurve:
    """Unit tests for the _index_equity_curve helper."""

    def test_empty_curve_returns_empty(self) -> None:
        result = _index_equity_curve([])
        assert result == []

    def test_single_point_returns_base_value(self) -> None:
        curve = [{"timestamp": "2024-01-01T00:00:00Z", "portfolio_value": "50000"}]
        result = _index_equity_curve(curve, base_value=10000.0)
        assert len(result) == 1
        assert result[0]["equity"] == 10000.0

    def test_two_points_indexed_correctly(self) -> None:
        curve = [
            {"timestamp": "2024-01-01T00:00:00Z", "portfolio_value": "10000"},
            {"timestamp": "2024-01-02T00:00:00Z", "portfolio_value": "11000"},
        ]
        result = _index_equity_curve(curve, base_value=10000.0)
        assert result[0]["equity"] == 10000.0
        # 11000 / 10000 * 10000 = 11000
        assert result[1]["equity"] == 11000.0

    def test_different_initial_capitals_produce_same_base(self) -> None:
        """Curves with different initial capitals should both start at base_value."""
        curve_100k = [
            {"timestamp": "2024-01-01T00:00:00Z", "portfolio_value": "100000"},
            {"timestamp": "2024-01-02T00:00:00Z", "portfolio_value": "110000"},
        ]
        curve_50k = [
            {"timestamp": "2024-01-01T00:00:00Z", "portfolio_value": "50000"},
            {"timestamp": "2024-01-02T00:00:00Z", "portfolio_value": "55000"},
        ]
        result_100k = _index_equity_curve(curve_100k)
        result_50k = _index_equity_curve(curve_50k)
        # Both should start at 10000 and end at 11000 (same 10% gain)
        assert result_100k[0]["equity"] == 10000.0
        assert result_50k[0]["equity"] == 10000.0
        assert result_100k[1]["equity"] == result_50k[1]["equity"]

    def test_timestamp_preserved_in_date_field(self) -> None:
        curve = [{"timestamp": "2024-06-15T00:00:00Z", "portfolio_value": "10000"}]
        result = _index_equity_curve(curve)
        assert result[0]["date"] == "2024-06-15T00:00:00Z"

    def test_zero_first_value_falls_back_to_base(self) -> None:
        """If first portfolio_value is 0, avoid division by zero."""
        curve = [
            {"timestamp": "2024-01-01T00:00:00Z", "portfolio_value": "0"},
            {"timestamp": "2024-01-02T00:00:00Z", "portfolio_value": "10000"},
        ]
        result = _index_equity_curve(curve)
        # Should not raise; first point at base_value
        assert result[0]["equity"] == 10000.0


class TestExtractParamDiff:
    """Unit tests for the _extract_param_diff helper."""

    def test_no_diff_when_configs_identical(self) -> None:
        configs = [
            ("run-1", {"symbol": "AAPL", "timeframe": "1d"}),
            ("run-2", {"symbol": "AAPL", "timeframe": "1d"}),
        ]
        result = _extract_param_diff(configs)
        assert result == []

    def test_detects_single_differing_param(self) -> None:
        configs = [
            ("run-1", {"symbol": "AAPL", "timeframe": "1d"}),
            ("run-2", {"symbol": "TSLA", "timeframe": "1d"}),
        ]
        result = _extract_param_diff(configs)
        assert len(result) == 1
        assert result[0]["param"] == "symbol"
        assert result[0]["values"]["run-1"] == "AAPL"
        assert result[0]["values"]["run-2"] == "TSLA"

    def test_detects_multiple_differing_params(self) -> None:
        configs = [
            ("run-1", {"symbol": "AAPL", "timeframe": "1d", "max_position_size": "0.02"}),
            ("run-2", {"symbol": "AAPL", "timeframe": "4h", "max_position_size": "0.05"}),
        ]
        result = _extract_param_diff(configs)
        param_names = {d["param"] for d in result}
        assert "timeframe" in param_names
        assert "max_position_size" in param_names

    def test_single_config_returns_empty(self) -> None:
        configs = [("run-1", {"symbol": "AAPL"})]
        result = _extract_param_diff(configs)
        assert result == []

    def test_empty_configs_returns_empty(self) -> None:
        result = _extract_param_diff([])
        assert result == []

    def test_three_runs_diff(self) -> None:
        configs = [
            ("run-1", {"timeframe": "1d"}),
            ("run-2", {"timeframe": "4h"}),
            ("run-3", {"timeframe": "1h"}),
        ]
        result = _extract_param_diff(configs)
        assert len(result) == 1
        assert result[0]["param"] == "timeframe"
        assert result[0]["values"]["run-3"] == "1h"


# ---------------------------------------------------------------------------
# Integration-style tests for the endpoint (mocking repository)
# ---------------------------------------------------------------------------


def _make_mock_result(run_id, symbol="AAPL", timeframe="1d", win_rate="0.65"):
    """Build a minimal mock BacktestResult for testing."""
    from src.models.backtest.config import BacktestConfig
    from src.models.backtest.metrics import BacktestMetrics
    from src.models.backtest.results import BacktestResult, EquityCurvePoint

    cfg = BacktestConfig(
        symbol=symbol,
        timeframe=timeframe,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 6, 30),
        initial_capital=Decimal("100000"),
        max_position_size=Decimal("0.02"),
    )
    summary = BacktestMetrics(
        total_signals=10,
        win_rate=Decimal(win_rate),
        average_r_multiple=Decimal("1.5"),
        profit_factor=Decimal("2.0"),
        max_drawdown=Decimal("0.10"),
        total_return_pct=Decimal("15.0"),
        cagr=Decimal("30.0"),
        sharpe_ratio=Decimal("1.8"),
        total_trades=10,
        winning_trades=7,
        losing_trades=3,
    )
    equity_curve = [
        EquityCurvePoint(
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            equity_value=Decimal("100000"),
            portfolio_value=Decimal("100000"),
            cash=Decimal("100000"),
        ),
        EquityCurvePoint(
            timestamp=datetime(2024, 6, 30, tzinfo=UTC),
            equity_value=Decimal("115000"),
            portfolio_value=Decimal("115000"),
            cash=Decimal("115000"),
        ),
    ]
    return BacktestResult(
        backtest_run_id=run_id,
        symbol=symbol,
        timeframe=timeframe,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 6, 30),
        config=cfg,
        equity_curve=equity_curve,
        trades=[],
        summary=summary,
    )


@pytest.mark.asyncio
class TestCompareEndpoint:
    """Tests for the /compare endpoint with mocked repository."""

    async def _call_compare(self, run_ids: list, repo_results: dict):
        """Helper to call the compare endpoint logic directly."""
        from src.api.routes.backtest.compare import CompareRequest, compare_backtests

        mock_session = MagicMock()

        async def mock_get_result(run_id):
            return repo_results.get(run_id)

        with patch("src.api.routes.backtest.compare.BacktestRepository") as MockRepo:
            mock_repo_instance = AsyncMock()
            mock_repo_instance.get_result = mock_get_result
            MockRepo.return_value = mock_repo_instance

            request = CompareRequest(run_ids=run_ids)
            result = await compare_backtests(request, session=mock_session)
            return result

    async def test_two_runs_returns_comparison(self) -> None:
        id1, id2 = uuid4(), uuid4()
        repo = {
            id1: _make_mock_result(id1, symbol="AAPL", timeframe="1d"),
            id2: _make_mock_result(id2, symbol="AAPL", timeframe="4h"),
        }
        result = await self._call_compare([id1, id2], repo)
        assert "runs" in result
        assert "parameter_diffs" in result
        assert len(result["runs"]) == 2

    async def test_run_colors_assigned(self) -> None:
        id1, id2 = uuid4(), uuid4()
        repo = {
            id1: _make_mock_result(id1),
            id2: _make_mock_result(id2),
        }
        result = await self._call_compare([id1, id2], repo)
        colors = [r["color"] for r in result["runs"]]
        # First run gets blue, second orange
        assert colors[0] == "#3B82F6"
        assert colors[1] == "#F97316"

    async def test_equity_curve_starts_at_10000(self) -> None:
        id1, id2 = uuid4(), uuid4()
        repo = {
            id1: _make_mock_result(id1),
            id2: _make_mock_result(id2),
        }
        result = await self._call_compare([id1, id2], repo)
        for run in result["runs"]:
            assert run["equity_curve"][0]["equity"] == 10000.0

    async def test_param_diff_detected(self) -> None:
        id1, id2 = uuid4(), uuid4()
        repo = {
            id1: _make_mock_result(id1, timeframe="1d"),
            id2: _make_mock_result(id2, timeframe="4h"),
        }
        result = await self._call_compare([id1, id2], repo)
        diff_params = [d["param"] for d in result["parameter_diffs"]]
        assert "timeframe" in diff_params

    async def test_404_when_run_not_found(self) -> None:
        from fastapi import HTTPException

        id1, id2 = uuid4(), uuid4()
        repo = {id1: _make_mock_result(id1)}  # id2 missing

        with pytest.raises(HTTPException) as exc_info:
            await self._call_compare([id1, id2], repo)

        assert exc_info.value.status_code == 404

    async def test_metrics_included_per_run(self) -> None:
        id1, id2 = uuid4(), uuid4()
        repo = {
            id1: _make_mock_result(id1),
            id2: _make_mock_result(id2),
        }
        result = await self._call_compare([id1, id2], repo)
        for run in result["runs"]:
            assert "metrics" in run
            metrics = run["metrics"]
            assert "total_return_pct" in metrics
            assert "max_drawdown" in metrics
            assert "sharpe_ratio" in metrics
            assert "win_rate" in metrics
            assert "profit_factor" in metrics

    async def test_four_runs_supported(self) -> None:
        ids = [uuid4() for _ in range(4)]
        repo = {run_id: _make_mock_result(run_id) for run_id in ids}
        result = await self._call_compare(ids, repo)
        assert len(result["runs"]) == 4

    async def test_run_label_includes_symbol_and_dates(self) -> None:
        id1, id2 = uuid4(), uuid4()
        repo = {
            id1: _make_mock_result(id1, symbol="TSLA"),
            id2: _make_mock_result(id2, symbol="AAPL"),
        }
        result = await self._call_compare([id1, id2], repo)
        assert "TSLA" in result["runs"][0]["label"]
        assert "AAPL" in result["runs"][1]["label"]


class TestCompareRequestValidation:
    """Tests for Pydantic model validation on CompareRequest."""

    def test_requires_at_least_two_run_ids(self) -> None:
        from pydantic import ValidationError

        from src.api.routes.backtest.compare import CompareRequest

        with pytest.raises(ValidationError):
            CompareRequest(run_ids=[uuid4()])

    def test_rejects_more_than_four_run_ids(self) -> None:
        from pydantic import ValidationError

        from src.api.routes.backtest.compare import CompareRequest

        with pytest.raises(ValidationError):
            CompareRequest(run_ids=[uuid4() for _ in range(5)])

    def test_accepts_two_to_four_run_ids(self) -> None:
        from src.api.routes.backtest.compare import CompareRequest

        for n in (2, 3, 4):
            req = CompareRequest(run_ids=[uuid4() for _ in range(n)])
            assert len(req.run_ids) == n
