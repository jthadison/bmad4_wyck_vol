"""
Tests for the Walk-Forward Parameter Stability endpoint (Feature 10).

Tests cover:
- GET /api/v1/backtest/walk-forward/{id}/stability returns correct structure
- robustness_score computed correctly (profitable_window_pct, worst_oos_drawdown,
  avg_is_oos_sharpe_ratio)
- 404 returned for unknown walk-forward ID
- 404 returned for still-running test

Uses monkeypatch to override repository.get_result without requiring a live DB.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.api.routes.backtest.walk_forward import walk_forward_runs
from src.database import get_db
from src.models.backtest import WalkForwardConfig, WalkForwardResult
from src.models.backtest.config import BacktestConfig
from src.models.backtest.metrics import BacktestMetrics
from src.models.backtest.walk_forward import ValidationWindow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_metrics(
    sharpe: float = 1.5, total_return: float = 0.10, max_drawdown: float = 0.05
) -> BacktestMetrics:
    return BacktestMetrics(
        sharpe_ratio=Decimal(str(sharpe)),
        total_return_pct=Decimal(str(total_return)),
        max_drawdown=Decimal(str(max_drawdown)),
    )


def _make_backtest_config() -> BacktestConfig:
    from datetime import date

    return BacktestConfig(
        symbol="AAPL",
        initial_capital=Decimal("100000"),
        start_date=date(2022, 1, 1),
        end_date=date(2023, 12, 31),
    )


def _make_walk_forward_result(n_windows: int = 3) -> WalkForwardResult:
    from datetime import date

    cfg = WalkForwardConfig(
        symbols=["AAPL"],
        overall_start_date=date(2022, 1, 1),
        overall_end_date=date(2023, 12, 31),
        train_period_months=6,
        validate_period_months=3,
        backtest_config=_make_backtest_config(),
    )

    windows = []
    for i in range(n_windows):
        windows.append(
            ValidationWindow(
                window_number=i + 1,
                train_start_date=date(2022, 1 + i * 3, 1),
                train_end_date=date(2022, 3 + i * 3, 28),
                validate_start_date=date(2022, 4 + i * 3, 1),
                validate_end_date=date(2022, 6 + i * 3, 30),
                train_metrics=_make_metrics(sharpe=2.0, total_return=0.12, max_drawdown=0.06),
                validate_metrics=_make_metrics(
                    sharpe=1.3,
                    # First window profitable, others negative
                    total_return=0.05 if i == 0 else -0.02,
                    max_drawdown=0.10,
                ),
                train_backtest_id=uuid4(),
                validate_backtest_id=uuid4(),
                performance_ratio=Decimal("0.65"),
                degradation_detected=False,
            )
        )

    return WalkForwardResult(
        config=cfg,
        windows=windows,
        stability_score=Decimal("0.15"),
    )


def _mock_db_session():
    """Return a mock async DB session that can be used as a FastAPI dependency."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.close = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWalkForwardStabilityEndpoint:
    """Tests for GET /api/v1/backtest/walk-forward/{id}/stability."""

    @pytest.mark.asyncio
    async def test_returns_404_for_running_test(self):
        running_id = uuid4()
        walk_forward_runs[running_id] = {"status": "RUNNING"}
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(f"/api/v1/backtest/walk-forward/{running_id}/stability")
            assert resp.status_code == 404
            data = resp.json()
            assert "still running" in data["detail"].lower()
        finally:
            walk_forward_runs.pop(running_id, None)

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_id(self, monkeypatch):
        """Unknown ID with no DB should return 404."""
        unknown_id = uuid4()

        # Mock DB session dependency to avoid real DB call
        async def mock_get_result(self, uid: UUID):  # noqa: ARG001
            return None

        from src.repositories import walk_forward_repository as repo_mod

        monkeypatch.setattr(repo_mod.WalkForwardRepository, "get_result", mock_get_result)

        # Override the get_db dependency to return a mock session
        async def mock_db():
            yield _mock_db_session()

        app.dependency_overrides[get_db] = mock_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(f"/api/v1/backtest/walk-forward/{unknown_id}/stability")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_response_structure_via_mock_repository(self, monkeypatch):
        """Verify the endpoint returns the expected JSON structure."""
        wf_result = _make_walk_forward_result(n_windows=3)
        wf_id = wf_result.walk_forward_id

        async def mock_get_result(self, uid: UUID):  # noqa: ARG001
            return wf_result if uid == wf_id else None

        from src.repositories import walk_forward_repository as repo_mod

        monkeypatch.setattr(repo_mod.WalkForwardRepository, "get_result", mock_get_result)

        async def mock_db():
            yield _mock_db_session()

        app.dependency_overrides[get_db] = mock_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(f"/api/v1/backtest/walk-forward/{wf_id}/stability")

            assert resp.status_code == 200
            data = resp.json()

            # Top-level keys
            assert data["walk_forward_id"] == str(wf_id)
            assert "windows" in data
            assert "parameter_stability" in data
            assert "robustness_score" in data
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_windows_contain_required_fields(self, monkeypatch):
        wf_result = _make_walk_forward_result(n_windows=2)
        wf_id = wf_result.walk_forward_id

        async def mock_get_result(self, uid: UUID):  # noqa: ARG001
            return wf_result if uid == wf_id else None

        from src.repositories import walk_forward_repository as repo_mod

        monkeypatch.setattr(repo_mod.WalkForwardRepository, "get_result", mock_get_result)

        async def mock_db():
            yield _mock_db_session()

        app.dependency_overrides[get_db] = mock_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(f"/api/v1/backtest/walk-forward/{wf_id}/stability")

            data = resp.json()
            windows = data["windows"]
            assert len(windows) == 2

            required_fields = {
                "window_index",
                "is_start",
                "is_end",
                "oos_start",
                "oos_end",
                "is_sharpe",
                "oos_sharpe",
                "is_return",
                "oos_return",
                "is_drawdown",
                "oos_drawdown",
                "optimal_params",
            }
            for w in windows:
                missing = required_fields - set(w.keys())
                assert not missing, f"Window missing fields: {missing}"
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_robustness_score_profitable_window_pct(self, monkeypatch):
        """Only 1 of 3 windows has positive OOS return -> 33% profitable."""
        wf_result = _make_walk_forward_result(n_windows=3)
        wf_id = wf_result.walk_forward_id

        async def mock_get_result(self, uid: UUID):  # noqa: ARG001
            return wf_result if uid == wf_id else None

        from src.repositories import walk_forward_repository as repo_mod

        monkeypatch.setattr(repo_mod.WalkForwardRepository, "get_result", mock_get_result)

        async def mock_db():
            yield _mock_db_session()

        app.dependency_overrides[get_db] = mock_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(f"/api/v1/backtest/walk-forward/{wf_id}/stability")

            data = resp.json()
            score = data["robustness_score"]
            # Window 0 has oos_return=0.05 (profitable), windows 1 and 2 have -0.02
            assert abs(score["profitable_window_pct"] - 1 / 3) < 0.01
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_robustness_score_worst_oos_drawdown(self, monkeypatch):
        """All windows have oos_drawdown=0.10 -> worst should be 0.10."""
        wf_result = _make_walk_forward_result(n_windows=3)
        wf_id = wf_result.walk_forward_id

        async def mock_get_result(self, uid: UUID):  # noqa: ARG001
            return wf_result if uid == wf_id else None

        from src.repositories import walk_forward_repository as repo_mod

        monkeypatch.setattr(repo_mod.WalkForwardRepository, "get_result", mock_get_result)

        async def mock_db():
            yield _mock_db_session()

        app.dependency_overrides[get_db] = mock_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(f"/api/v1/backtest/walk-forward/{wf_id}/stability")

            data = resp.json()
            score = data["robustness_score"]
            assert abs(score["worst_oos_drawdown"] - 0.10) < 0.001
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_robustness_score_is_oos_sharpe_ratio(self, monkeypatch):
        """IS sharpe=2.0, OOS sharpe=1.3 -> ratio approx 2.0/1.3 ~1.538."""
        wf_result = _make_walk_forward_result(n_windows=3)
        wf_id = wf_result.walk_forward_id

        async def mock_get_result(self, uid: UUID):  # noqa: ARG001
            return wf_result if uid == wf_id else None

        from src.repositories import walk_forward_repository as repo_mod

        monkeypatch.setattr(repo_mod.WalkForwardRepository, "get_result", mock_get_result)

        async def mock_db():
            yield _mock_db_session()

        app.dependency_overrides[get_db] = mock_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(f"/api/v1/backtest/walk-forward/{wf_id}/stability")

            data = resp.json()
            score = data["robustness_score"]
            expected_ratio = 2.0 / 1.3
            assert abs(score["avg_is_oos_sharpe_ratio"] - expected_ratio) < 0.05
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_parameter_stability_keys(self, monkeypatch):
        """parameter_stability should include train/validate period months."""
        wf_result = _make_walk_forward_result(n_windows=3)
        wf_id = wf_result.walk_forward_id

        async def mock_get_result(self, uid: UUID):  # noqa: ARG001
            return wf_result if uid == wf_id else None

        from src.repositories import walk_forward_repository as repo_mod

        monkeypatch.setattr(repo_mod.WalkForwardRepository, "get_result", mock_get_result)

        async def mock_db():
            yield _mock_db_session()

        app.dependency_overrides[get_db] = mock_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(f"/api/v1/backtest/walk-forward/{wf_id}/stability")

            data = resp.json()
            ps = data["parameter_stability"]
            assert "train_period_months" in ps
            assert "validate_period_months" in ps
            # Should have one value per window
            assert len(ps["train_period_months"]) == 3
        finally:
            app.dependency_overrides.pop(get_db, None)
