#!/usr/bin/env python3
"""
Unit tests for run_regression_test.py CLI script (Story 12.7 Task 9).

Tests CLI argument parsing, output formatting, and execution flow.
"""

import argparse
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.run_regression_test import (
    parse_arguments,
    print_degraded_metrics,
    print_header,
    print_metrics,
    print_status,
    run_regression_test,
)
from src.models.backtest import (
    BacktestConfig,
    BacktestMetrics,
    MetricComparison,
    RegressionBaseline,
    RegressionComparison,
    RegressionTestConfig,
    RegressionTestResult,
)


def create_mock_config() -> RegressionTestConfig:
    """Create a mock RegressionTestConfig for testing."""
    return RegressionTestConfig(
        symbols=["AAPL", "MSFT"],
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        backtest_config=BacktestConfig(
            symbol="AAPL",
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=Decimal("100000"),
            risk_per_trade=Decimal("0.02"),
            max_position_size=Decimal("0.10"),
            commission_rate=Decimal("0.001"),
            slippage_bps=Decimal("5.0"),
        ),
        regression_thresholds={
            "win_rate": Decimal("5.0"),
            "average_r_multiple": Decimal("10.0"),
            "profit_factor": Decimal("15.0"),
        },
    )


class TestArgumentParsing:
    """Test command-line argument parsing."""

    def test_parse_default_arguments(self):
        """Test default argument values."""
        with patch("sys.argv", ["run_regression_test.py"]):
            args = parse_arguments()

        assert args.symbols == "AAPL,MSFT,GOOGL,TSLA,NVDA,META,AMZN,SPY,QQQ,DIA"
        assert args.start_date == "2020-01-01"
        assert args.end_date is None
        assert args.establish_baseline is False
        assert args.alert is False
        assert args.output is None
        assert args.no_color is False

    def test_parse_custom_symbols(self):
        """Test parsing custom symbols."""
        with patch("sys.argv", ["run_regression_test.py", "--symbols", "AAPL,MSFT"]):
            args = parse_arguments()

        assert args.symbols == "AAPL,MSFT"

    def test_parse_date_range(self):
        """Test parsing custom date range."""
        with patch(
            "sys.argv",
            [
                "run_regression_test.py",
                "--start-date",
                "2021-01-01",
                "--end-date",
                "2023-12-31",
            ],
        ):
            args = parse_arguments()

        assert args.start_date == "2021-01-01"
        assert args.end_date == "2023-12-31"

    def test_parse_establish_baseline_flag(self):
        """Test --establish-baseline flag."""
        with patch("sys.argv", ["run_regression_test.py", "--establish-baseline"]):
            args = parse_arguments()

        assert args.establish_baseline is True

    def test_parse_alert_flag(self):
        """Test --alert flag."""
        with patch("sys.argv", ["run_regression_test.py", "--alert"]):
            args = parse_arguments()

        assert args.alert is True

    def test_parse_output_path(self):
        """Test --output argument."""
        with patch("sys.argv", ["run_regression_test.py", "--output", "results.json"]):
            args = parse_arguments()

        assert args.output == "results.json"

    def test_parse_no_color_flag(self):
        """Test --no-color flag."""
        with patch("sys.argv", ["run_regression_test.py", "--no-color"]):
            args = parse_arguments()

        assert args.no_color is True

    def test_parse_combined_flags(self):
        """Test multiple flags together."""
        with patch(
            "sys.argv",
            [
                "run_regression_test.py",
                "--symbols",
                "SPY,QQQ",
                "--establish-baseline",
                "--alert",
                "--output",
                "test.json",
                "--no-color",
            ],
        ):
            args = parse_arguments()

        assert args.symbols == "SPY,QQQ"
        assert args.establish_baseline is True
        assert args.alert is True
        assert args.output == "test.json"
        assert args.no_color is True


class TestOutputFormatting:
    """Test output formatting functions."""

    def test_print_header_with_color(self, capsys):
        """Test header printing with color enabled."""
        print_header("Test Header", use_color=True)
        captured = capsys.readouterr()

        assert "Test Header" in captured.out
        assert "=" in captured.out

    def test_print_header_without_color(self, capsys):
        """Test header printing with color disabled."""
        print_header("Test Header", use_color=False)
        captured = capsys.readouterr()

        assert "Test Header" in captured.out
        assert "=" in captured.out
        # Should not contain ANSI codes
        assert "\033[" not in captured.out

    def test_print_status_pass_with_color(self, capsys):
        """Test PASS status printing with color."""
        print_status("PASS", use_color=True)
        captured = capsys.readouterr()

        assert "PASS" in captured.out
        assert "✓" in captured.out

    def test_print_status_fail_with_color(self, capsys):
        """Test FAIL status printing with color."""
        print_status("FAIL", use_color=True)
        captured = capsys.readouterr()

        assert "FAIL" in captured.out
        assert "✗" in captured.out

    def test_print_status_baseline_not_set_with_color(self, capsys):
        """Test BASELINE_NOT_SET status printing with color."""
        print_status("BASELINE_NOT_SET", use_color=True)
        captured = capsys.readouterr()

        assert "BASELINE_NOT_SET" in captured.out
        assert "⚠" in captured.out

    def test_print_status_without_color(self, capsys):
        """Test status printing without color."""
        print_status("PASS", use_color=False)
        captured = capsys.readouterr()

        assert "PASS" in captured.out
        assert "\033[" not in captured.out

    def test_print_metrics(self, capsys):
        """Test metrics printing."""
        metrics = {
            "total_trades": 150,
            "win_rate": Decimal("0.6333"),
            "average_r_multiple": Decimal("1.85"),
            "profit_factor": Decimal("2.45"),
            "max_drawdown": Decimal("0.12"),
            "sharpe_ratio": Decimal("1.75"),
        }

        print_metrics(metrics, use_color=True)
        captured = capsys.readouterr()

        assert "Total Trades:" in captured.out
        assert "150" in captured.out
        assert "63.33%" in captured.out  # win_rate formatted
        assert "1.85" in captured.out
        assert "2.45" in captured.out
        assert "12.00%" in captured.out  # max_drawdown formatted
        assert "1.75" in captured.out

    def test_print_degraded_metrics_with_data(self, capsys):
        """Test degraded metrics printing with data."""
        degraded = ["win_rate", "profit_factor"]
        comparisons = {
            "win_rate": {
                "baseline_value": Decimal("0.65"),
                "current_value": Decimal("0.60"),
                "percent_change": Decimal("-7.69"),
                "threshold": Decimal("5.0"),
            },
            "profit_factor": {
                "baseline_value": Decimal("2.5"),
                "current_value": Decimal("2.0"),
                "percent_change": Decimal("-20.0"),
                "threshold": Decimal("15.0"),
            },
        }

        print_degraded_metrics(degraded, comparisons, use_color=True)
        captured = capsys.readouterr()

        assert "Degraded Metrics:" in captured.out
        assert "win_rate" in captured.out
        assert "profit_factor" in captured.out
        assert "0.6500" in captured.out  # baseline
        assert "0.6000" in captured.out  # current
        assert "-7.69%" in captured.out
        assert "5.00%" in captured.out  # threshold

    def test_print_degraded_metrics_empty(self, capsys):
        """Test degraded metrics printing with no degradations."""
        print_degraded_metrics([], {}, use_color=True)
        captured = capsys.readouterr()

        assert "No metrics degraded" in captured.out


class TestRegressionTestExecution:
    """Test regression test execution flow."""

    @pytest.mark.asyncio
    async def test_run_regression_test_pass(self):
        """Test successful PASS regression test."""
        # Mock arguments
        args = argparse.Namespace(
            symbols="AAPL,MSFT",
            start_date="2020-01-01",
            end_date="2024-12-31",
            establish_baseline=False,
            alert=False,
            output=None,
            no_color=True,
        )

        # Mock result
        mock_result = RegressionTestResult(
            test_id=uuid4(),
            config=create_mock_config(),
            test_run_time=datetime.now(),
            codebase_version="abc123",
            status="PASS",
            aggregate_metrics=BacktestMetrics(
                total_trades=150,
                winning_trades=95,
                losing_trades=55,
                win_rate=Decimal("0.6333"),
                average_r_multiple=Decimal("1.85"),
                profit_factor=Decimal("2.45"),
                max_drawdown=Decimal("0.12"),
                sharpe_ratio=Decimal("1.75"),
                total_return=Decimal("0.35"),
            ),
            per_symbol_results={},
            regression_detected=False,
            degraded_metrics=[],
            execution_time_seconds=45.5,
        )

        # Mock engine
        with patch("scripts.run_regression_test.async_session_maker") as mock_session:
            mock_session.return_value.__aenter__.return_value = AsyncMock()

            with patch("scripts.run_regression_test.RegressionTestEngine") as mock_engine_class:
                mock_engine = AsyncMock()
                mock_engine.run_regression_test.return_value = mock_result
                mock_engine_class.return_value = mock_engine

                exit_code = await run_regression_test(args)

        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_run_regression_test_fail(self):
        """Test FAIL regression test."""
        args = argparse.Namespace(
            symbols="AAPL",
            start_date="2020-01-01",
            end_date=None,
            establish_baseline=False,
            alert=False,
            output=None,
            no_color=True,
        )

        mock_result = RegressionTestResult(
            test_id=uuid4(),
            config=create_mock_config(),
            test_run_time=datetime.now(),
            codebase_version="def456",
            status="FAIL",
            aggregate_metrics=BacktestMetrics(
                total_trades=150,
                winning_trades=85,
                losing_trades=65,
                win_rate=Decimal("0.5667"),
                average_r_multiple=Decimal("1.45"),
                profit_factor=Decimal("1.85"),
                max_drawdown=Decimal("0.18"),
                sharpe_ratio=Decimal("1.25"),
                total_return=Decimal("0.22"),
            ),
            per_symbol_results={},
            regression_detected=True,
            degraded_metrics=["win_rate", "profit_factor"],
            execution_time_seconds=52.3,
            baseline_comparison=RegressionComparison(
                baseline_id=uuid4(),
                test_id=uuid4(),
                baseline_version="abc123",
                current_version="def456",
                metric_comparisons={
                    "win_rate": MetricComparison(
                        metric_name="win_rate",
                        baseline_value=Decimal("0.65"),
                        current_value=Decimal("0.5667"),
                        absolute_change=Decimal("-0.0833"),
                        percent_change=Decimal("-12.82"),
                        threshold=Decimal("5.0"),
                        degraded=True,
                    )
                },
            ),
        )

        with patch("scripts.run_regression_test.async_session_maker") as mock_session:
            mock_session.return_value.__aenter__.return_value = AsyncMock()

            with patch("scripts.run_regression_test.RegressionTestEngine") as mock_engine_class:
                mock_engine = AsyncMock()
                mock_engine.run_regression_test.return_value = mock_result
                mock_engine_class.return_value = mock_engine

                exit_code = await run_regression_test(args)

        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_run_regression_test_baseline_not_set(self):
        """Test BASELINE_NOT_SET status."""
        args = argparse.Namespace(
            symbols="AAPL",
            start_date="2020-01-01",
            end_date=None,
            establish_baseline=False,
            alert=False,
            output=None,
            no_color=True,
        )

        mock_result = RegressionTestResult(
            test_id=uuid4(),
            config=create_mock_config(),
            test_run_time=datetime.now(),
            codebase_version="ghi789",
            status="BASELINE_NOT_SET",
            aggregate_metrics=BacktestMetrics(
                total_trades=150,
                winning_trades=95,
                losing_trades=55,
                win_rate=Decimal("0.6333"),
                average_r_multiple=Decimal("1.85"),
                profit_factor=Decimal("2.45"),
                max_drawdown=Decimal("0.12"),
                sharpe_ratio=Decimal("1.75"),
                total_return=Decimal("0.35"),
            ),
            per_symbol_results={},
            regression_detected=False,
            degraded_metrics=[],
            execution_time_seconds=43.1,
        )

        with patch("scripts.run_regression_test.async_session_maker") as mock_session:
            mock_session.return_value.__aenter__.return_value = AsyncMock()

            with patch("scripts.run_regression_test.RegressionTestEngine") as mock_engine_class:
                mock_engine = AsyncMock()
                mock_engine.run_regression_test.return_value = mock_result
                mock_engine_class.return_value = mock_engine

                exit_code = await run_regression_test(args)

        assert exit_code == 2

    @pytest.mark.asyncio
    async def test_run_regression_test_with_error(self):
        """Test error during test execution."""
        args = argparse.Namespace(
            symbols="AAPL",
            start_date="2020-01-01",
            end_date=None,
            establish_baseline=False,
            alert=False,
            output=None,
            no_color=True,
        )

        with patch("scripts.run_regression_test.async_session_maker") as mock_session:
            mock_session.return_value.__aenter__.return_value = AsyncMock()

            with patch("scripts.run_regression_test.RegressionTestEngine") as mock_engine_class:
                mock_engine = AsyncMock()
                mock_engine.run_regression_test.side_effect = Exception("Test execution failed")
                mock_engine_class.return_value = mock_engine

                exit_code = await run_regression_test(args)

        assert exit_code == 3

    @pytest.mark.asyncio
    async def test_run_regression_test_with_default_end_date(self):
        """Test that end_date defaults to yesterday."""
        args = argparse.Namespace(
            symbols="AAPL",
            start_date="2020-01-01",
            end_date=None,  # Should default to yesterday
            establish_baseline=False,
            alert=False,
            output=None,
            no_color=True,
        )

        mock_result = RegressionTestResult(
            test_id=uuid4(),
            config=create_mock_config(),
            test_run_time=datetime.now(),
            codebase_version="abc123",
            status="PASS",
            aggregate_metrics=BacktestMetrics(
                total_trades=150,
                winning_trades=95,
                losing_trades=55,
                win_rate=Decimal("0.6333"),
                average_r_multiple=Decimal("1.85"),
                profit_factor=Decimal("2.45"),
                max_drawdown=Decimal("0.12"),
                sharpe_ratio=Decimal("1.75"),
                total_return=Decimal("0.35"),
            ),
            per_symbol_results={},
            regression_detected=False,
            degraded_metrics=[],
            execution_time_seconds=45.5,
        )

        with patch("scripts.run_regression_test.async_session_maker") as mock_session:
            mock_session.return_value.__aenter__.return_value = AsyncMock()

            with patch("scripts.run_regression_test.RegressionTestEngine") as mock_engine_class:
                mock_engine = AsyncMock()
                mock_engine.run_regression_test.return_value = mock_result
                mock_engine_class.return_value = mock_engine

                # Capture the config passed to run_regression_test
                await run_regression_test(args)

                # Verify end_date was set to yesterday
                call_args = mock_engine.run_regression_test.call_args[0][0]
                expected_end_date = date.today() - timedelta(days=1)
                assert call_args.end_date == expected_end_date


class TestEstablishBaseline:
    """Test baseline establishment functionality."""

    @pytest.mark.asyncio
    async def test_establish_baseline_from_pass(self):
        """Test establishing baseline from PASS test."""
        args = argparse.Namespace(
            symbols="AAPL",
            start_date="2020-01-01",
            end_date=None,
            establish_baseline=True,
            alert=False,
            output=None,
            no_color=True,
        )

        test_id = uuid4()
        mock_result = RegressionTestResult(
            test_id=test_id,
            config=create_mock_config(),
            test_run_time=datetime.now(),
            codebase_version="abc123",
            status="PASS",
            aggregate_metrics=BacktestMetrics(
                total_trades=150,
                winning_trades=95,
                losing_trades=55,
                win_rate=Decimal("0.6333"),
                average_r_multiple=Decimal("1.85"),
                profit_factor=Decimal("2.45"),
                max_drawdown=Decimal("0.12"),
                sharpe_ratio=Decimal("1.75"),
                total_return=Decimal("0.35"),
            ),
            per_symbol_results={},
            regression_detected=False,
            degraded_metrics=[],
            execution_time_seconds=45.5,
        )

        mock_baseline = RegressionBaseline(
            baseline_id=uuid4(),
            test_id=test_id,
            version="abc123",
            established_at=datetime.now(),
            metrics=BacktestMetrics(
                total_trades=150,
                winning_trades=95,
                losing_trades=55,
                win_rate=Decimal("0.6333"),
                average_r_multiple=Decimal("1.85"),
                profit_factor=Decimal("2.45"),
                max_drawdown=Decimal("0.12"),
                sharpe_ratio=Decimal("1.75"),
                total_return=Decimal("0.35"),
            ),
            per_symbol_metrics={},
            is_current=True,
        )

        with patch("scripts.run_regression_test.async_session_maker") as mock_session:
            mock_session.return_value.__aenter__.return_value = AsyncMock()

            with patch("scripts.run_regression_test.RegressionTestEngine") as mock_engine_class:
                mock_engine = AsyncMock()
                mock_engine.run_regression_test.return_value = mock_result
                mock_engine.establish_baseline.return_value = mock_baseline
                mock_engine_class.return_value = mock_engine

                exit_code = await run_regression_test(args)

                # Verify establish_baseline was called with test_id
                mock_engine.establish_baseline.assert_called_once_with(test_id)

        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_establish_baseline_from_baseline_not_set(self):
        """Test establishing baseline from BASELINE_NOT_SET test."""
        args = argparse.Namespace(
            symbols="AAPL",
            start_date="2020-01-01",
            end_date=None,
            establish_baseline=True,
            alert=False,
            output=None,
            no_color=True,
        )

        test_id = uuid4()
        mock_result = RegressionTestResult(
            test_id=test_id,
            config=create_mock_config(),
            test_run_time=datetime.now(),
            codebase_version="abc123",
            status="BASELINE_NOT_SET",
            aggregate_metrics=BacktestMetrics(
                total_trades=150,
                winning_trades=95,
                losing_trades=55,
                win_rate=Decimal("0.6333"),
                average_r_multiple=Decimal("1.85"),
                profit_factor=Decimal("2.45"),
                max_drawdown=Decimal("0.12"),
                sharpe_ratio=Decimal("1.75"),
                total_return=Decimal("0.35"),
            ),
            per_symbol_results={},
            regression_detected=False,
            degraded_metrics=[],
            execution_time_seconds=45.5,
        )

        mock_baseline = RegressionBaseline(
            baseline_id=uuid4(),
            test_id=test_id,
            version="abc123",
            established_at=datetime.now(),
            metrics=BacktestMetrics(
                total_trades=150,
                winning_trades=95,
                losing_trades=55,
                win_rate=Decimal("0.6333"),
                average_r_multiple=Decimal("1.85"),
                profit_factor=Decimal("2.45"),
                max_drawdown=Decimal("0.12"),
                sharpe_ratio=Decimal("1.75"),
                total_return=Decimal("0.35"),
            ),
            per_symbol_metrics={},
            is_current=True,
        )

        with patch("scripts.run_regression_test.async_session_maker") as mock_session:
            mock_session.return_value.__aenter__.return_value = AsyncMock()

            with patch("scripts.run_regression_test.RegressionTestEngine") as mock_engine_class:
                mock_engine = AsyncMock()
                mock_engine.run_regression_test.return_value = mock_result
                mock_engine.establish_baseline.return_value = mock_baseline
                mock_engine_class.return_value = mock_engine

                exit_code = await run_regression_test(args)

                # Verify establish_baseline was called
                mock_engine.establish_baseline.assert_called_once_with(test_id)

        assert exit_code == 2

    @pytest.mark.asyncio
    async def test_cannot_establish_baseline_from_fail(self, capsys):
        """Test that baseline cannot be established from FAIL test."""
        args = argparse.Namespace(
            symbols="AAPL",
            start_date="2020-01-01",
            end_date=None,
            establish_baseline=True,
            alert=False,
            output=None,
            no_color=True,
        )

        mock_result = RegressionTestResult(
            test_id=uuid4(),
            config=create_mock_config(),
            test_run_time=datetime.now(),
            codebase_version="def456",
            status="FAIL",
            aggregate_metrics=BacktestMetrics(
                total_trades=150,
                winning_trades=85,
                losing_trades=65,
                win_rate=Decimal("0.5667"),
                average_r_multiple=Decimal("1.45"),
                profit_factor=Decimal("1.85"),
                max_drawdown=Decimal("0.18"),
                sharpe_ratio=Decimal("1.25"),
                total_return=Decimal("0.22"),
            ),
            per_symbol_results={},
            regression_detected=True,
            degraded_metrics=["win_rate"],
            execution_time_seconds=52.3,
        )

        with patch("scripts.run_regression_test.async_session_maker") as mock_session:
            mock_session.return_value.__aenter__.return_value = AsyncMock()

            with patch("scripts.run_regression_test.RegressionTestEngine") as mock_engine_class:
                mock_engine = AsyncMock()
                mock_engine.run_regression_test.return_value = mock_result
                mock_engine_class.return_value = mock_engine

                exit_code = await run_regression_test(args)

                # Verify establish_baseline was NOT called
                mock_engine.establish_baseline.assert_not_called()

        captured = capsys.readouterr()
        assert "Cannot establish baseline from FAIL test" in captured.out
        assert exit_code == 1
