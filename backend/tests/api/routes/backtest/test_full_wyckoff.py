"""
Unit test verifying full.py uses UnifiedBacktestEngine (Critical Backtest Fix).

Ensures the full backtest endpoint references the Wyckoff-based engine
instead of the legacy buy-and-hold BacktestEngine with simple_strategy.

This is a source-level verification test: it reads the actual source code
of full.py and asserts the correct engine/detector imports are present
and the legacy buy-and-hold strategy is absent.

Author: Critical Backtest Fix tests
"""

from pathlib import Path


class TestFullEndpointUsesUnifiedEngine:
    """Verify full.py references the correct Wyckoff engine, not legacy buy-and-hold."""

    def _read_full_source(self) -> str:
        """Read the source of the full.py backtest endpoint module."""
        full_path = Path("src/api/routes/backtest/full.py")
        assert full_path.exists(), f"Expected source file at {full_path}"
        return full_path.read_text(encoding="utf-8")

    def test_no_simple_strategy_present(self) -> None:
        """Legacy buy-and-hold simple_strategy should not be in full.py."""
        source = self._read_full_source()
        assert "simple_strategy" not in source, (
            "Legacy buy-and-hold strategy (simple_strategy) is still present in full.py. "
            "It should be replaced by WyckoffSignalDetector + UnifiedBacktestEngine."
        )

    def test_uses_unified_backtest_engine(self) -> None:
        """full.py should import and use UnifiedBacktestEngine."""
        source = self._read_full_source()
        assert (
            "UnifiedBacktestEngine" in source
        ), "full.py should import UnifiedBacktestEngine, not the legacy BacktestEngine."

    def test_uses_wyckoff_signal_detector(self) -> None:
        """full.py should import and use WyckoffSignalDetector."""
        source = self._read_full_source()
        assert (
            "WyckoffSignalDetector" in source
        ), "full.py should import WyckoffSignalDetector for Wyckoff pattern detection."

    def test_no_legacy_backtest_engine_import(self) -> None:
        """full.py should not import the legacy BacktestEngine directly.

        The legacy BacktestEngine is in src.backtesting.backtest_engine and uses
        a strategy_func callback. The new code should use UnifiedBacktestEngine
        with a SignalDetector protocol instead.
        """
        source = self._read_full_source()
        # Check for the specific legacy import pattern
        has_legacy = (
            "from src.backtesting.backtest_engine import BacktestEngine" in source
            and "UnifiedBacktestEngine" not in source
        )
        assert not has_legacy, (
            "full.py still imports legacy BacktestEngine without UnifiedBacktestEngine. "
            "Should use UnifiedBacktestEngine with WyckoffSignalDetector."
        )
