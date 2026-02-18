"""
Unit Tests for Paper Trading Validator and Comparison (Story 23.8b)

Tests validation configuration, result comparison logic, metric calculations,
tolerance checking, and report generation.

Author: Story 23.8b
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.backtest_baseline_loader import BacktestBaseline
from src.models.backtest import BacktestMetrics
from src.trading.paper_trading_comparison import (
    DeviationSeverity,
    _classify_deviation,
    _compute_deviation,
    compare_symbol_metrics,
    generate_comparison_report,
)
from src.trading.paper_trading_validator import (
    PaperTradingValidator,
    ValidationRunConfig,
    ValidationRunState,
    ValidationRunStatus,
    ValidationSymbolConfig,
)

# --- Validator Tests ---


class TestPaperTradingValidator:
    """Tests for PaperTradingValidator."""

    def test_initial_state_no_run(self) -> None:
        validator = PaperTradingValidator()
        assert validator.current_run is None

    def test_start_run_default_config(self) -> None:
        validator = PaperTradingValidator()
        run = validator.start_run()
        assert run.status == ValidationRunStatus.RUNNING
        assert run.started_at is not None
        assert len(run.config.symbols) == 2
        assert run.signals_generated == 0

    def test_start_run_custom_config(self) -> None:
        validator = PaperTradingValidator()
        config = ValidationRunConfig(
            symbols=[ValidationSymbolConfig(symbol="AAPL")],
            duration_days=7,
            tolerance_pct=Decimal("5.0"),
        )
        run = validator.start_run(config)
        assert run.config.symbols[0].symbol == "AAPL"
        assert run.config.duration_days == 7
        assert run.config.tolerance_pct == Decimal("5.0")

    def test_start_run_while_active_raises(self) -> None:
        validator = PaperTradingValidator()
        validator.start_run()
        with pytest.raises(ValueError, match="already active"):
            validator.start_run()

    def test_stop_run(self) -> None:
        validator = PaperTradingValidator()
        validator.start_run()
        result = validator.stop_run()
        assert result is not None
        assert result.status == ValidationRunStatus.COMPLETED
        assert result.completed_at is not None

    def test_stop_run_no_active(self) -> None:
        validator = PaperTradingValidator()
        result = validator.stop_run()
        assert result is None

    def test_record_signal_executed(self) -> None:
        validator = PaperTradingValidator()
        validator.start_run()
        validator.record_signal("EURUSD", executed=True)
        assert validator.current_run is not None
        assert validator.current_run.signals_generated == 1
        assert validator.current_run.signals_executed == 1
        assert validator.current_run.signals_rejected == 0

    def test_record_signal_rejected(self) -> None:
        validator = PaperTradingValidator()
        validator.start_run()
        validator.record_signal("EURUSD", executed=False)
        assert validator.current_run is not None
        assert validator.current_run.signals_generated == 1
        assert validator.current_run.signals_executed == 0
        assert validator.current_run.signals_rejected == 1

    def test_record_signal_no_active_run_is_noop(self) -> None:
        validator = PaperTradingValidator()
        # Should not raise
        validator.record_signal("EURUSD", executed=True)

    def test_record_metrics(self) -> None:
        validator = PaperTradingValidator()
        validator.start_run()
        metrics = {"win_rate": 65.0, "profit_factor": 1.9}
        validator.record_metrics("SPX500", metrics)
        assert validator.current_run is not None
        assert validator.current_run.symbol_metrics["SPX500"] == metrics

    def test_record_metrics_no_active_run_is_noop(self) -> None:
        validator = PaperTradingValidator()
        validator.record_metrics("SPX500", {"win_rate": 65.0})
        # Should not raise

    def test_get_status_no_run(self) -> None:
        validator = PaperTradingValidator()
        status = validator.get_status()
        assert status["active"] is False

    def test_get_status_with_run(self) -> None:
        validator = PaperTradingValidator()
        validator.start_run()
        validator.record_signal("EURUSD", executed=True)
        status = validator.get_status()
        assert status["active"] is True
        assert status["status"] == "RUNNING"
        assert status["signals_generated"] == 1
        assert "EURUSD" in status["symbols"]

    def test_can_start_new_run_after_stop(self) -> None:
        validator = PaperTradingValidator()
        validator.start_run()
        validator.stop_run()
        # Should be able to start a new run
        run = validator.start_run()
        assert run.status == ValidationRunStatus.RUNNING


# --- Comparison Tests ---


def _make_baseline(
    symbol: str = "SPX500",
    win_rate: str = "0.617",
    avg_r: str = "1.24",
    profit_factor: str = "1.85",
    max_drawdown: str = "0.082",
    total_trades: int = 47,
) -> BacktestBaseline:
    """Helper to create a BacktestBaseline for testing."""
    metrics = BacktestMetrics(
        win_rate=Decimal(win_rate),
        average_r_multiple=Decimal(avg_r),
        profit_factor=Decimal(profit_factor),
        max_drawdown=Decimal(max_drawdown),
        total_trades=total_trades,
        total_signals=total_trades,
    )
    return BacktestBaseline(
        symbol=symbol,
        metrics=metrics,
        tolerance_pct=Decimal("5.0"),
        baseline_version="23.3.0",
        established_at="2026-02-09T00:00:00Z",
        date_range={"start": "2024-01-01", "end": "2025-12-31"},
    )


class TestDeviationClassification:
    """Tests for deviation classification."""

    def test_ok_within_tolerance(self) -> None:
        assert _classify_deviation(5.0, 10.0) == DeviationSeverity.OK

    def test_warning_above_tolerance(self) -> None:
        assert _classify_deviation(15.0, 10.0) == DeviationSeverity.WARNING

    def test_error_above_double_tolerance(self) -> None:
        assert _classify_deviation(25.0, 10.0) == DeviationSeverity.ERROR

    def test_negative_deviation(self) -> None:
        assert _classify_deviation(-15.0, 10.0) == DeviationSeverity.WARNING

    def test_zero_deviation(self) -> None:
        assert _classify_deviation(0.0, 10.0) == DeviationSeverity.OK

    def test_exact_tolerance_boundary(self) -> None:
        # At exactly the tolerance boundary, should be OK (not > tolerance)
        assert _classify_deviation(10.0, 10.0) == DeviationSeverity.OK

    def test_exact_double_tolerance_boundary(self) -> None:
        # At exactly 2x tolerance, should be WARNING (not > 2x)
        assert _classify_deviation(20.0, 10.0) == DeviationSeverity.WARNING


class TestComputeDeviation:
    """Tests for deviation percentage computation."""

    def test_no_deviation(self) -> None:
        assert _compute_deviation(10.0, 10.0) == 0.0

    def test_positive_deviation(self) -> None:
        result = _compute_deviation(11.0, 10.0)
        assert abs(result - 10.0) < 0.01

    def test_negative_deviation(self) -> None:
        result = _compute_deviation(9.0, 10.0)
        assert abs(result - (-10.0)) < 0.01

    def test_baseline_zero(self) -> None:
        assert _compute_deviation(5.0, 0.0) == 100.0

    def test_both_zero(self) -> None:
        assert _compute_deviation(0.0, 0.0) == 0.0


class TestCompareSymbolMetrics:
    """Tests for per-symbol metric comparison."""

    def test_matching_metrics_all_ok(self) -> None:
        baseline = _make_baseline()
        paper_metrics = {
            "win_rate": 61.7,
            "average_r_multiple": 1.24,
            "profit_factor": 1.85,
            "max_drawdown": 8.2,
            "total_trades": 47,
        }
        report = compare_symbol_metrics("SPX500", paper_metrics, baseline)
        assert report.overall_status == DeviationSeverity.OK
        assert len(report.anomalies) == 0

    def test_large_win_rate_deviation_triggers_warning(self) -> None:
        baseline = _make_baseline()
        paper_metrics = {
            "win_rate": 45.0,  # 61.7 baseline -> ~27% deviation
            "average_r_multiple": 1.24,
            "profit_factor": 1.85,
            "max_drawdown": 8.2,
            "total_trades": 47,
        }
        report = compare_symbol_metrics("SPX500", paper_metrics, baseline, tolerance_pct=10.0)
        assert report.overall_status in (DeviationSeverity.WARNING, DeviationSeverity.ERROR)
        assert len(report.anomalies) > 0

    def test_custom_tolerance(self) -> None:
        baseline = _make_baseline()
        paper_metrics = {
            "win_rate": 55.0,
            "average_r_multiple": 1.24,
            "profit_factor": 1.85,
            "max_drawdown": 8.2,
            "total_trades": 47,
        }
        # With 5% tolerance, a ~10.9% deviation on win_rate should warn
        report = compare_symbol_metrics("SPX500", paper_metrics, baseline, tolerance_pct=5.0)
        win_rate_metric = next(m for m in report.metrics if m.metric_name == "win_rate")
        assert win_rate_metric.severity != DeviationSeverity.OK

    def test_all_metrics_reported(self) -> None:
        baseline = _make_baseline()
        paper_metrics = {
            "win_rate": 61.7,
            "average_r_multiple": 1.24,
            "profit_factor": 1.85,
            "max_drawdown": 8.2,
            "total_trades": 47,
        }
        report = compare_symbol_metrics("SPX500", paper_metrics, baseline)
        metric_names = {m.metric_name for m in report.metrics}
        assert "win_rate" in metric_names
        assert "average_r_multiple" in metric_names
        assert "profit_factor" in metric_names
        assert "max_drawdown" in metric_names
        assert "total_trades" in metric_names

    def test_missing_paper_metrics_default_to_zero(self) -> None:
        baseline = _make_baseline()
        paper_metrics: dict = {}  # All missing
        report = compare_symbol_metrics("SPX500", paper_metrics, baseline)
        # Should not raise, all paper values default to 0
        assert len(report.metrics) == 5


class TestGenerateComparisonReport:
    """Tests for full report generation."""

    def test_report_with_run_state(self) -> None:
        run = ValidationRunState(
            config=ValidationRunConfig(symbols=[ValidationSymbolConfig(symbol="SPX500")]),
            status=ValidationRunStatus.COMPLETED,
            signals_generated=10,
            signals_executed=8,
            symbol_metrics={
                "SPX500": {
                    "win_rate": 61.7,
                    "average_r_multiple": 1.24,
                    "profit_factor": 1.85,
                    "max_drawdown": 8.2,
                    "total_trades": 47,
                }
            },
        )
        report = generate_comparison_report(run)
        assert report.run_id == str(run.id)
        assert report.signals_generated == 10
        assert report.signals_executed == 8

    def test_report_with_direct_metrics(self) -> None:
        metrics = {
            "SPX500": {
                "win_rate": 61.7,
                "average_r_multiple": 1.24,
                "profit_factor": 1.85,
                "max_drawdown": 8.2,
                "total_trades": 47,
            }
        }
        report = generate_comparison_report(None, paper_metrics_by_symbol=metrics)
        # Should have compared SPX500 if baseline exists
        assert report.generated_at is not None

    def test_report_no_data(self) -> None:
        report = generate_comparison_report(None)
        assert report.overall_status == DeviationSeverity.OK
        assert len(report.symbol_reports) == 0

    def test_report_unknown_symbol_skipped(self) -> None:
        metrics = {
            "XYZNONEXISTENT": {
                "win_rate": 50.0,
            }
        }
        report = generate_comparison_report(None, paper_metrics_by_symbol=metrics)
        assert len(report.symbol_reports) == 0
        assert any("No baseline found" in s for s in report.summary)


class TestValidationRunConfig:
    """Tests for validation configuration models."""

    def test_default_config(self) -> None:
        config = ValidationRunConfig()
        assert len(config.symbols) == 2
        assert config.duration_days == 14
        assert config.tolerance_pct == Decimal("10.0")

    def test_custom_symbols(self) -> None:
        config = ValidationRunConfig(
            symbols=[
                ValidationSymbolConfig(symbol="AAPL"),
                ValidationSymbolConfig(symbol="EURUSD", timeframe="4h"),
            ]
        )
        assert config.symbols[0].symbol == "AAPL"
        assert config.symbols[1].timeframe == "4h"

    def test_tolerance_bounds(self) -> None:
        # Valid tolerance
        config = ValidationRunConfig(tolerance_pct=Decimal("0"))
        assert config.tolerance_pct == Decimal("0")

        config = ValidationRunConfig(tolerance_pct=Decimal("100"))
        assert config.tolerance_pct == Decimal("100")

    def test_duration_bounds(self) -> None:
        config = ValidationRunConfig(duration_days=1)
        assert config.duration_days == 1

        config = ValidationRunConfig(duration_days=90)
        assert config.duration_days == 90


class TestToleranceChecking:
    """Tests specifically for the +/-10% tolerance requirement."""

    def test_within_10_pct_tolerance(self) -> None:
        baseline = _make_baseline(win_rate="0.60")
        # 60% baseline, 63% paper -> 5% deviation -> OK
        paper = {
            "win_rate": 63.0,
            "average_r_multiple": 1.24,
            "profit_factor": 1.85,
            "max_drawdown": 8.2,
            "total_trades": 47,
        }
        report = compare_symbol_metrics("TEST", paper, baseline, tolerance_pct=10.0)
        assert report.overall_status == DeviationSeverity.OK

    def test_outside_10_pct_triggers_warning(self) -> None:
        baseline = _make_baseline(win_rate="0.60")
        # 60% baseline, 48% paper -> -20% deviation -> WARNING (between 1x and 2x tolerance)
        paper = {
            "win_rate": 48.0,
            "average_r_multiple": 1.24,
            "profit_factor": 1.85,
            "max_drawdown": 8.2,
            "total_trades": 47,
        }
        report = compare_symbol_metrics("TEST", paper, baseline, tolerance_pct=10.0)
        win_rate_metric = next(m for m in report.metrics if m.metric_name == "win_rate")
        assert win_rate_metric.severity == DeviationSeverity.WARNING

    def test_extreme_deviation_triggers_error(self) -> None:
        baseline = _make_baseline(win_rate="0.60")
        # 60% baseline, 30% paper -> -50% deviation -> ERROR (> 2x tolerance)
        paper = {
            "win_rate": 30.0,
            "average_r_multiple": 1.24,
            "profit_factor": 1.85,
            "max_drawdown": 8.2,
            "total_trades": 47,
        }
        report = compare_symbol_metrics("TEST", paper, baseline, tolerance_pct=10.0)
        win_rate_metric = next(m for m in report.metrics if m.metric_name == "win_rate")
        assert win_rate_metric.severity == DeviationSeverity.ERROR


# --- API Endpoint Tests ---


class TestValidationAPIEndpoints:
    """Tests for the validation API endpoints in paper_trading routes."""

    @pytest.mark.asyncio
    async def test_get_validation_status_no_run(self) -> None:
        from src.api.routes.paper_trading import get_validation_status

        result = await get_validation_status(_user_id=uuid4())
        assert result["active"] is False

    @pytest.mark.asyncio
    async def test_start_validation_run_endpoint(self) -> None:
        from src.api.routes.paper_trading import (
            StartValidationRequest,
            _validator,
            start_validation_run,
        )

        # Ensure clean state
        if _validator.current_run and _validator.current_run.status == ValidationRunStatus.RUNNING:
            _validator.stop_run()

        request = StartValidationRequest(
            symbols=["EURUSD", "SPX500"],
            duration_days=14,
            tolerance_pct=10.0,
        )
        result = await start_validation_run(request=request, _user_id=uuid4())
        assert result["success"] is True
        assert result["run_id"] is not None
        assert result["symbols"] == ["EURUSD", "SPX500"]

        # Clean up
        _validator.stop_run()

    @pytest.mark.asyncio
    async def test_start_validation_run_conflict_when_active(self) -> None:
        from fastapi import HTTPException

        from src.api.routes.paper_trading import (
            StartValidationRequest,
            _validator,
            start_validation_run,
        )

        # Ensure clean state then start
        if _validator.current_run and _validator.current_run.status == ValidationRunStatus.RUNNING:
            _validator.stop_run()
        _validator.start_run()

        request = StartValidationRequest()
        with pytest.raises(HTTPException) as exc_info:
            await start_validation_run(request=request, _user_id=uuid4())
        assert exc_info.value.status_code == 409

        # Clean up
        _validator.stop_run()

    @pytest.mark.asyncio
    async def test_stop_validation_run_endpoint(self) -> None:
        from src.api.routes.paper_trading import _validator, stop_validation_run

        # Ensure clean state then start
        if _validator.current_run and _validator.current_run.status == ValidationRunStatus.RUNNING:
            _validator.stop_run()
        _validator.start_run()

        result = await stop_validation_run(_user_id=uuid4())
        assert result["success"] is True
        assert result["signals_generated"] == 0

    @pytest.mark.asyncio
    async def test_stop_validation_run_404_when_no_run(self) -> None:
        from fastapi import HTTPException

        from src.api.routes.paper_trading import _validator, stop_validation_run

        # Ensure no active run
        if _validator.current_run and _validator.current_run.status == ValidationRunStatus.RUNNING:
            _validator.stop_run()
        _validator._current_run = None

        with pytest.raises(HTTPException) as exc_info:
            await stop_validation_run(_user_id=uuid4())
        assert exc_info.value.status_code == 404

    def test_get_validation_report_endpoint(self) -> None:
        from src.api.routes.paper_trading import _validator, get_validation_report

        # Ensure clean state then start and record metrics
        if _validator.current_run and _validator.current_run.status == ValidationRunStatus.RUNNING:
            _validator.stop_run()
        _validator.start_run()
        _validator.record_metrics(
            "SPX500",
            {
                "win_rate": 61.7,
                "average_r_multiple": 1.24,
                "profit_factor": 1.85,
                "max_drawdown": 8.2,
                "total_trades": 47,
            },
        )

        result = get_validation_report(_user_id=uuid4())
        assert "overall_status" in result
        assert "symbol_reports" in result

        # Clean up
        _validator.stop_run()

    def test_get_validation_report_404_when_no_run(self) -> None:
        from fastapi import HTTPException

        from src.api.routes.paper_trading import _validator, get_validation_report

        # Ensure no run
        if _validator.current_run and _validator.current_run.status == ValidationRunStatus.RUNNING:
            _validator.stop_run()
        _validator._current_run = None

        with pytest.raises(HTTPException) as exc_info:
            get_validation_report(_user_id=uuid4())
        assert exc_info.value.status_code == 404


class TestGenerateComparisonReportOverallStatus:
    """Tests for overall_status escalation in generate_comparison_report."""

    def test_report_overall_status_warning_when_symbol_has_warning(self) -> None:
        """Overall status should be WARNING when a symbol report has WARNING severity."""
        from unittest.mock import patch

        # Create a baseline that will produce WARNING deviations
        baseline = _make_baseline(
            symbol="SPX500",
            win_rate="0.60",  # 60% baseline
        )

        # Paper metrics with moderate deviation (will trigger WARNING)
        metrics = {
            "SPX500": {
                "win_rate": 48.0,  # ~20% deviation from 60% => WARNING
                "average_r_multiple": 1.24,
                "profit_factor": 1.85,
                "max_drawdown": 8.2,
                "total_trades": 47,
            }
        }

        with (
            patch(
                "src.trading.paper_trading_comparison.load_all_backtest_baselines",
                return_value=[baseline],
            ),
            patch(
                "src.trading.paper_trading_comparison.load_backtest_baseline",
                return_value=None,
            ),
        ):
            report = generate_comparison_report(None, paper_metrics_by_symbol=metrics)

        assert report.overall_status == DeviationSeverity.WARNING
