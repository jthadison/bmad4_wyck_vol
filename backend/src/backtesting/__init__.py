"""
Backtesting Engine Package (Story 11.2)

Purpose:
--------
Provides backtesting functionality for validating proposed configuration
changes against historical data before applying them to live trading.

Modules:
--------
- engine: Core backtest execution engine with preview mode
- metrics: Performance metrics calculation
- event_publisher: Campaign event notification system (Story 15.6)
- intraday_campaign_detector: Campaign detection and tracking

Author: Story 11.2
"""

from src.backtesting.event_publisher import EventFilter, EventPublisher

__all__ = ["EventFilter", "EventPublisher"]
