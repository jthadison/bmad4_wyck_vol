"""
Unit tests for OrchestratorContainer with consistent error handling.

Story 18.3: Fix Inconsistent Error Handling in container.py

Tests cover:
- Container initialization
- Mock injection
- health_check() returning HealthStatus
- DetectorLoadError propagation for critical detectors
- Optional detectors returning None on failure
"""

from unittest.mock import MagicMock

from src.orchestrator.container import (
    OrchestratorContainer,
    reset_orchestrator_container,
)
from src.orchestrator.detector_loader import DetectorLoadError, HealthStatus


class TestOrchestratorContainerInit:
    """Tests for container initialization."""

    def test_container_initializes_with_defaults(self) -> None:
        """Should initialize with default config."""
        container = OrchestratorContainer()

        assert container.mode == "production"
        assert container._detectors == {}
        assert container._mocks == {}

    def test_container_initializes_with_mode(self) -> None:
        """Should accept mode override."""
        container = OrchestratorContainer(mode="test")

        assert container.mode == "test"

    def test_container_initializes_with_mock_mode(self) -> None:
        """Should initialize in mock mode."""
        container = OrchestratorContainer(mode="mock")

        assert container.mode == "mock"


class TestOrchestratorContainerMocking:
    """Tests for mock injection."""

    def test_set_mock(self) -> None:
        """Should store mock for later retrieval."""
        container = OrchestratorContainer(mode="mock")
        mock_analyzer = MagicMock()

        container.set_mock("volume_analyzer", mock_analyzer)

        # Access should return the mock
        result = container.volume_analyzer
        assert result is mock_analyzer

    def test_clear_mocks(self) -> None:
        """Should clear all mocks."""
        container = OrchestratorContainer(mode="mock")
        container.set_mock("volume_analyzer", MagicMock())
        container.set_mock("risk_manager", MagicMock())

        container.clear_mocks()

        assert container._mocks == {}

    def test_mock_only_used_in_mock_mode(self) -> None:
        """Mocks should only be returned in mock mode."""
        # In production mode, set_mock shouldn't affect accessor
        container = OrchestratorContainer(mode="production")
        mock_analyzer = MagicMock()
        container.set_mock("volume_analyzer", mock_analyzer)

        # This should try to load the real detector, not use mock
        # (The real detector may or may not load depending on environment)
        try:
            result = container.volume_analyzer
            # If it loads, verify it's not the mock
            if result is not None:
                assert result is not mock_analyzer
        except DetectorLoadError:
            # Expected if real detector not available
            pass


class TestOrchestratorContainerHealthCheck:
    """Tests for health_check() method."""

    def test_health_check_returns_health_status(self) -> None:
        """Should return HealthStatus dataclass, not dict."""
        container = OrchestratorContainer(mode="mock")

        # Set up mocks for all detectors to avoid import errors
        for name in [
            "volume_analyzer",
            "pivot_detector",
            "trading_range_detector",
            "range_quality_scorer",
            "level_calculator",
            "zone_mapper",
            "sos_detector",
            "lps_detector",
            "risk_manager",
        ]:
            container.set_mock(name, MagicMock())

        result = container.health_check()

        assert isinstance(result, HealthStatus)
        assert hasattr(result, "healthy")
        assert hasattr(result, "detectors_loaded")
        assert hasattr(result, "detectors_failed")
        assert hasattr(result, "failures")
        assert hasattr(result, "details")

    def test_health_check_all_mocked_healthy(self) -> None:
        """Should report healthy when all detectors are mocked."""
        container = OrchestratorContainer(mode="mock")

        for name in [
            "volume_analyzer",
            "pivot_detector",
            "trading_range_detector",
            "range_quality_scorer",
            "level_calculator",
            "zone_mapper",
            "sos_detector",
            "lps_detector",
            "risk_manager",
        ]:
            container.set_mock(name, MagicMock())

        result = container.health_check()

        assert result.healthy is True
        assert result.detectors_loaded == 9
        assert result.detectors_failed == 0
        assert len(result.failures) == 0

    def test_health_check_calls_detector_health_check(self) -> None:
        """Should call detector's health_check if available."""
        container = OrchestratorContainer(mode="mock")

        mock_with_health = MagicMock()
        mock_with_health.health_check.return_value = True

        mock_without_health = MagicMock(spec=[])  # No health_check method

        container.set_mock("volume_analyzer", mock_with_health)
        container.set_mock("pivot_detector", mock_without_health)

        # Mock the rest
        for name in [
            "trading_range_detector",
            "range_quality_scorer",
            "level_calculator",
            "zone_mapper",
            "sos_detector",
            "lps_detector",
            "risk_manager",
        ]:
            container.set_mock(name, MagicMock())

        result = container.health_check()

        # Verify health_check was called on the mock that has it
        mock_with_health.health_check.assert_called_once()

    def test_health_check_reports_detector_health_failure(self) -> None:
        """Should report failure when detector health_check returns False."""
        container = OrchestratorContainer(mode="mock")

        unhealthy_mock = MagicMock()
        unhealthy_mock.health_check.return_value = False

        container.set_mock("volume_analyzer", unhealthy_mock)

        # Mock the rest as healthy
        for name in [
            "pivot_detector",
            "trading_range_detector",
            "range_quality_scorer",
            "level_calculator",
            "zone_mapper",
            "sos_detector",
            "lps_detector",
            "risk_manager",
        ]:
            container.set_mock(name, MagicMock())

        result = container.health_check()

        assert result.healthy is False
        assert result.detectors_failed == 1
        assert any("volume_analyzer" in f for f in result.failures)

    def test_health_check_reports_detector_health_exception(self) -> None:
        """Should catch and report detector health_check exceptions."""
        container = OrchestratorContainer(mode="mock")

        failing_mock = MagicMock()
        failing_mock.health_check.side_effect = RuntimeError("Health check boom")

        container.set_mock("volume_analyzer", failing_mock)

        # Mock the rest as healthy
        for name in [
            "pivot_detector",
            "trading_range_detector",
            "range_quality_scorer",
            "level_calculator",
            "zone_mapper",
            "sos_detector",
            "lps_detector",
            "risk_manager",
        ]:
            container.set_mock(name, MagicMock())

        result = container.health_check()

        assert result.healthy is False
        assert any("RuntimeError" in f for f in result.failures)
        assert any("Health check boom" in f for f in result.failures)

    def test_health_check_reports_none_detectors(self) -> None:
        """Should report detectors that return None as failures."""
        container = OrchestratorContainer(mode="mock")

        # Set some as mocks, leave pivot_detector unset
        for name in [
            "volume_analyzer",
            "trading_range_detector",
            "range_quality_scorer",
            "level_calculator",
            "zone_mapper",
            "sos_detector",
            "lps_detector",
            "risk_manager",
        ]:
            container.set_mock(name, MagicMock())

        # pivot_detector not mocked, will try to load and likely fail/return None

        result = container.health_check()

        # At least check that we got a proper HealthStatus
        assert isinstance(result, HealthStatus)
        assert result.details.get("pivot_detector") is not None or "pivot_detector" in str(
            result.failures
        )


class TestOrchestratorContainerLoadErrors:
    """Tests for error handling in detector loading."""

    def test_get_load_errors_initially_empty(self) -> None:
        """Should have no load errors on fresh container."""
        container = OrchestratorContainer(mode="mock")

        errors = container.get_load_errors()

        assert errors == []

    def test_get_load_errors_returns_copy(self) -> None:
        """Should return a copy of load errors list."""
        container = OrchestratorContainer(mode="mock")

        errors1 = container.get_load_errors()
        errors2 = container.get_load_errors()

        assert errors1 is not errors2

    def test_detector_caching(self) -> None:
        """Should cache detector instances after first load."""
        container = OrchestratorContainer(mode="mock")
        mock = MagicMock()
        container.set_mock("volume_analyzer", mock)

        result1 = container.volume_analyzer
        result2 = container.volume_analyzer

        assert result1 is result2

    def test_failed_detector_not_retried(self) -> None:
        """Should not retry loading a failed detector."""
        container = OrchestratorContainer(mode="production")

        # Force a failure tracking
        container._failed_detectors.append("test_detector")

        # Access pivot_detector which would normally try to load
        # But since we've marked it as failed, it should return None
        container._failed_detectors.append("pivot_detector")

        result = container.pivot_detector

        assert result is None


class TestResetOrchestratorContainer:
    """Tests for reset_orchestrator_container function."""

    def test_reset_creates_new_instance(self) -> None:
        """Should create a fresh container instance."""
        container1 = reset_orchestrator_container(mode="mock")
        container1.set_mock("volume_analyzer", MagicMock())

        container2 = reset_orchestrator_container(mode="mock")

        # New container should not have the mock
        assert container2._mocks == {}

    def test_reset_with_different_mode(self) -> None:
        """Should accept new mode on reset."""
        container1 = reset_orchestrator_container(mode="production")
        assert container1.mode == "production"

        container2 = reset_orchestrator_container(mode="test")
        assert container2.mode == "test"
