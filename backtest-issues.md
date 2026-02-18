Backtesting Subsystem Review Report                                                                                                                                                                                                                                       
                                                                                                                                                                                                                                                                            
  Architecture Summary                                                                                                                                                                                                                                                      
                                                                                                                                                                                                                                                                              The system has three distinct backtesting engines at different maturity levels:                                                                                                                                                                                                                                                                                                                                                                                                                                                                         - Engine A (Preview) - Config comparison engine (Story 11.2) - uses placeholder signal detection                                                                                                                                                                            - Engine B (Unified) - DI-based clean architecture engine (Story 18.9.2) - pluggable detectors/cost models                                                                                                                                                                  - Engine C (Legacy) - Event-driven, most production-complete (Story 12.1) - correct next-bar fills                                                                                                                                                                        

  Supporting modules include: OrderSimulator, PositionManager, SlippageCalculator, BacktestRiskManager (4-limit pipeline), LookAheadBiasDetector, MetricsFacade, and WalkForwardEngine.

  ---
  Critical Issues (3)

  C-1: Preview Engine uses future bars for exit pricing (backtesting/engine/backtest_engine.py:292) - reads 5 bars into the future to determine exit price. Textbook look-ahead bias.

  C-2: Walk-Forward Engine returns hardcoded mock data (backtesting/walk_forward_engine.py:349-372) - _run_backtest_for_window returns identical metrics for every window, making stability scores, significance tests, and degradation detection meaningless.

  C-3: Background tasks receive request-scoped DB sessions (api/routes/backtest/full.py:93-98) - FastAPI closes the session when the HTTP 202 response returns, so background tasks operate on a closed session, potentially losing backtest results.

  Medium Issues (6)

  - M-1: Unified Engine fills at same-bar close instead of next-bar open (overstates performance)
  - M-2: In-memory run tracking (backtest_runs dicts) has no cleanup/TTL - unbounded memory growth
  - M-3: Profit factor semantics vary across engines (None, 0, or 999.99 for zero losses)
  - M-4: Max drawdown scale inconsistency (0-100 vs 0-1 across calculators)
  - M-5: Bias detector flags both price extremes for both LONG and SHORT (should be directional)
  - M-6: BarProcessor uses bar.close for stop/target checks instead of bar.low/bar.high

  Low Issues (6)

  - Sharpe ratio uses population variance (n) instead of sample variance (n-1)
  - Legacy engine sets CAGR = total_return_pct (not annualized)
  - Legacy engine hardcodes sharpe_ratio = 0
  - Risk manager minimum position is forex-specific (1000 units)
  - Synthetic fallback data has deterministic upward trend
  - Risk manager close_position has loose fallback matching

  Positive Findings

  - Legacy Engine (C) has correct next-bar fill semantics - proper PENDING→FILLED lifecycle
  - Risk management pipeline is comprehensive - 5-step validation with Decimal precision
  - Slippage model is realistic - two-tier liquidity + market impact model
  - Sortino ratio correctly uses total N for downside deviation
  - Walk-forward window generation is methodologically sound (non-overlapping validation periods)

  Top Recommendations (Prioritized)

  1. Fix background task session handling (C-3) - small fix, prevents data loss
  2. Remove future bar access from Preview Engine (C-1)
  3. Connect walk-forward engine to real backtest execution (C-2) - most important guard against overfitting
  4. Implement next-bar fills in Unified Engine (M-1)
  5. Standardize metric scales and semantics (M-3, M-4)
  6. Long-term: converge to one engine, adopting Unified's DI architecture with Legacy's correct execution semantics