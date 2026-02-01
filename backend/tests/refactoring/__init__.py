"""
Refactoring Test Suite (Story 22.14)

Purpose:
--------
Dedicated test suite for validating refactoring work before decomposition.
These tests ensure that refactoring stories (22.4, 22.5, 22.6, 22.10) don't
break existing functionality.

Test Modules:
- test_campaign_state_transitions.py: AC1 - Campaign state machine tests
- test_portfolio_heat_tracking.py: AC2 - Portfolio heat calculation tests
- test_validation_caching.py: AC3 - Validation cache tests
- test_phase_detection_baseline.py: AC4 - Phase detection tests
- test_backtest_routes_baseline.py: AC5 - Backtest API tests
- test_campaign_routes_baseline.py: AC5 - Campaign API tests

Coverage Target: >=90% on target files (AC6)
"""
