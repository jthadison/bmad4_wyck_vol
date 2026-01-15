"""
Unit tests for DetectorLoader and DetectorLoadError.

Story 18.3: Fix Inconsistent Error Handling in container.py

Tests cover:
- DetectorLoadError exception with proper attributes
- DetectorLoader.load() for successful and failed loads
- DetectorLoader.load_optional() for optional detectors
- Various error scenarios (ImportError, AttributeError, init failures)
"""

import pytest

from src.orchestrator.detector_loader import (
    DetectorLoader,
    DetectorLoadError,
    HealthStatus,
)


class TestDetectorLoadError:
    """Tests for DetectorLoadError exception class."""

    def test_detector_load_error_with_basic_info(self) -> None:
        """Should store detector name and original error."""
        original = ImportError("Module not found")
        error = DetectorLoadError("TestDetector", original)

        assert error.detector_name == "TestDetector"
        assert error.original_error is original
        assert "TestDetector" in str(error)
        assert "Module not found" in str(error)

    def test_detector_load_error_with_import_path(self) -> None:
        """Should include import path in message when provided."""
        original = ImportError("Module not found")
        error = DetectorLoadError(
            "TestDetector",
            original,
            import_path="src.test.module",
        )

        assert error.import_path == "src.test.module"
        assert "src.test.module" in str(error)

    def test_detector_load_error_inherits_from_exception(self) -> None:
        """Should be catchable as a standard Exception."""
        original = ValueError("Invalid value")
        error = DetectorLoadError("TestDetector", original)

        assert isinstance(error, Exception)

        # Verify it can be caught
        with pytest.raises(Exception):
            raise error


class TestDetectorLoader:
    """Tests for DetectorLoader class."""

    def test_load_successful_module(self) -> None:
        """Should load a valid module and class."""
        loader = DetectorLoader()

        # Load a real class that exists in the codebase
        result = loader.load(
            "OrchestratorConfig",
            "src.orchestrator.config",
            "OrchestratorConfig",
        )

        assert result is not None
        # Verify it's the right class
        assert hasattr(result, "detector_mode")

    def test_load_raises_for_missing_module(self) -> None:
        """Should raise DetectorLoadError for missing module."""
        loader = DetectorLoader()

        with pytest.raises(DetectorLoadError) as exc_info:
            loader.load("TestDetector", "nonexistent.module.path")

        assert exc_info.value.detector_name == "TestDetector"
        assert isinstance(exc_info.value.original_error, ImportError)
        assert "nonexistent.module.path" in str(exc_info.value)

    def test_load_raises_for_missing_class(self) -> None:
        """Should raise DetectorLoadError for missing class in module."""
        loader = DetectorLoader()

        with pytest.raises(DetectorLoadError) as exc_info:
            loader.load(
                "NonexistentClass",
                "src.orchestrator.config",
                "NonexistentClass",
            )

        assert exc_info.value.detector_name == "NonexistentClass"
        assert isinstance(exc_info.value.original_error, AttributeError)

    def test_load_uses_name_as_default_class_name(self) -> None:
        """Should use name as class_name when not specified."""
        loader = DetectorLoader()

        # This should try to load 'OrchestratorConfig' class
        result = loader.load(
            "OrchestratorConfig",
            "src.orchestrator.config",
        )

        assert result is not None

    def test_load_optional_returns_none_on_failure(self) -> None:
        """Should return None instead of raising for optional detectors."""
        loader = DetectorLoader()

        result = loader.load_optional("TestDetector", "nonexistent.module")

        assert result is None

    def test_load_optional_returns_instance_on_success(self) -> None:
        """Should return instance when load succeeds."""
        loader = DetectorLoader()

        result = loader.load_optional(
            "OrchestratorConfig",
            "src.orchestrator.config",
        )

        assert result is not None

    def test_load_preserves_exception_chain(self) -> None:
        """Should preserve the original exception as __cause__."""
        loader = DetectorLoader()

        with pytest.raises(DetectorLoadError) as exc_info:
            loader.load("TestDetector", "nonexistent.module")

        # Verify exception chaining
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, ImportError)


class TestHealthStatus:
    """Tests for HealthStatus dataclass."""

    def test_health_status_healthy(self) -> None:
        """Should report healthy when no failures."""
        status = HealthStatus(
            healthy=True,
            detectors_loaded=5,
            detectors_failed=0,
            failures=[],
            details={"detector1": True, "detector2": True},
        )

        assert status.healthy is True
        assert status.status == "healthy"
        assert status.detectors_loaded == 5
        assert status.detectors_failed == 0
        assert len(status.failures) == 0

    def test_health_status_degraded(self) -> None:
        """Should report degraded when some failures."""
        status = HealthStatus(
            healthy=False,
            detectors_loaded=3,
            detectors_failed=2,
            failures=["detector3: failed", "detector4: failed"],
            details={"detector1": True, "detector2": True, "detector3": False},
        )

        assert status.healthy is False
        assert status.status == "degraded"
        assert len(status.failures) == 2

    def test_health_status_unhealthy(self) -> None:
        """Should report unhealthy when all failures."""
        status = HealthStatus(
            healthy=False,
            detectors_loaded=0,
            detectors_failed=5,
            failures=["detector1: failed"],
            details={"detector1": False},
        )

        assert status.healthy is False
        assert status.status == "unhealthy"

    def test_health_status_default_lists(self) -> None:
        """Should default to empty lists for failures and details."""
        status = HealthStatus(
            healthy=True,
            detectors_loaded=0,
            detectors_failed=0,
        )

        assert status.failures == []
        assert status.details == {}


class TestDetectorLoaderErrorScenarios:
    """Tests for various error scenarios in DetectorLoader."""

    def test_load_with_init_that_raises(self) -> None:
        """Should wrap initialization errors in DetectorLoadError."""
        loader = DetectorLoader()

        # Try to load something that will fail on init
        # Use a module we know exists but might fail to initialize
        with pytest.raises(DetectorLoadError) as exc_info:
            # This class doesn't exist, so it will raise AttributeError
            loader.load(
                "BrokenClass",
                "src.orchestrator.config",
                "BrokenClass",
            )

        assert exc_info.value.detector_name == "BrokenClass"

    def test_load_with_init_runtime_error(self, monkeypatch) -> None:
        """Should wrap runtime initialization errors in DetectorLoadError."""
        import importlib

        # Mock importlib to return a module with a class that raises on init
        class BrokenClass:
            def __init__(self):
                raise RuntimeError("Initialization failed")

        mock_module = type("MockModule", (), {"BrokenClass": BrokenClass})()

        original_import = importlib.import_module

        def patched_import(name):
            if name == "test.broken.module":
                return mock_module
            return original_import(name)

        monkeypatch.setattr(importlib, "import_module", patched_import)

        loader = DetectorLoader()

        with pytest.raises(DetectorLoadError) as exc_info:
            loader.load("BrokenClass", "test.broken.module", "BrokenClass")

        assert exc_info.value.detector_name == "BrokenClass"
        assert isinstance(exc_info.value.original_error, RuntimeError)
        assert "Initialization failed" in str(exc_info.value.original_error)

    def test_multiple_loads_are_independent(self) -> None:
        """Should not cache failures between load calls."""
        loader = DetectorLoader()

        # First call fails
        result1 = loader.load_optional("Bad", "nonexistent.module")
        assert result1 is None

        # Second call with valid module should succeed
        result2 = loader.load_optional(
            "OrchestratorConfig",
            "src.orchestrator.config",
        )
        assert result2 is not None

    def test_load_error_message_formatting(self) -> None:
        """Should format error messages consistently."""
        original = ImportError("No module named 'foo'")

        # Without import path
        error1 = DetectorLoadError("TestDetector", original)
        assert "TestDetector" in str(error1)
        assert "foo" in str(error1)

        # With import path
        error2 = DetectorLoadError("TestDetector", original, "src.foo.bar")
        assert "TestDetector" in str(error2)
        assert "src.foo.bar" in str(error2)
        assert "foo" in str(error2)
