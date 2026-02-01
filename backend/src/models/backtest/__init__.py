"""
Backtest models package.

This package organizes backtest-related models into focused modules.

Usage:
    from models.backtest import BacktestConfig, BacktestResult

Or import from specific modules:
    from models.backtest.config import BacktestConfig
    from models.backtest.results import BacktestResult
"""

from .accuracy import AccuracyMetrics, LabeledPattern
from .config import (
    BacktestConfig,
    BacktestPreviewRequest,
    CommissionConfig,
    SlippageConfig,
)
from .costs import (
    BacktestCostSummary,
    CommissionBreakdown,
    SlippageBreakdown,
    TransactionCostReport,
)
from .metrics import (
    BacktestMetrics,
    CampaignPerformance,
    DrawdownPeriod,
    MonthlyReturn,
    PatternPerformance,
    RiskMetrics,
)
from .regression import (
    MetricComparison,
    RegressionBaseline,
    RegressionComparison,
    RegressionTestConfig,
    RegressionTestResult,
)
from .results import (
    BacktestComparison,
    BacktestCompletedMessage,
    BacktestOrder,
    BacktestPosition,
    BacktestPreviewResponse,
    BacktestProgressUpdate,
    BacktestResult,
    BacktestTrade,
    EquityCurvePoint,
)
from .walk_forward import (
    ValidationWindow,
    WalkForwardChartData,
    WalkForwardConfig,
    WalkForwardResult,
)

__all__ = [
    # Config
    "BacktestConfig",
    "BacktestPreviewRequest",
    "CommissionConfig",
    "SlippageConfig",
    # Costs
    "BacktestCostSummary",
    "CommissionBreakdown",
    "SlippageBreakdown",
    "TransactionCostReport",
    # Metrics
    "AccuracyMetrics",
    "BacktestMetrics",
    "CampaignPerformance",
    "DrawdownPeriod",
    "LabeledPattern",
    "MonthlyReturn",
    "PatternPerformance",
    "RiskMetrics",
    # Results
    "BacktestComparison",
    "BacktestCompletedMessage",
    "BacktestOrder",
    "BacktestPosition",
    "BacktestPreviewResponse",
    "BacktestProgressUpdate",
    "BacktestResult",
    "BacktestTrade",
    "EquityCurvePoint",
    # Walk-forward
    "ValidationWindow",
    "WalkForwardChartData",
    "WalkForwardConfig",
    "WalkForwardResult",
    # Regression
    "MetricComparison",
    "RegressionBaseline",
    "RegressionComparison",
    "RegressionTestConfig",
    "RegressionTestResult",
]
