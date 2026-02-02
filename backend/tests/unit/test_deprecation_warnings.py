"""
Tests for deprecation warnings across refactored modules.

Story 22.13: Add Deprecation Warnings for Legacy APIs

Ensures all legacy APIs emit proper deprecation warnings with:
- Correct format: "{old_name} is deprecated. Use {new_import} instead. Will be removed in {version}."
- Warnings visible in logs but don't fail tests
- Removal version included (v0.3.0)
- Migration guidance (what to use instead)

Note: Module-level deprecation warnings are emitted at import time. Since pytest
imports modules during collection, we verify warnings via module reload.
"""

import importlib
import warnings
from pathlib import Path

import pytest

# List of deprecated modules for parametrized tests
DEPRECATED_PHASE_MODULES = [
    "src.pattern_engine.phase_detector",
    "src.pattern_engine.phase_detector_v2",
]

# Facade line count limit: Facades should be thin wrappers (~50-100 lines typically).
# 200 lines allows for docstrings, type re-exports, and deprecation boilerplate.
MAX_FACADE_LINES = 200


class TestDeprecationWarningFormat:
    """Tests that all deprecation messages follow standard format."""

    @pytest.mark.parametrize("module_name", DEPRECATED_PHASE_MODULES)
    def test_warning_includes_removal_version(self, module_name: str) -> None:
        """AC4: All deprecation warnings must include removal version."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            try:
                module = importlib.import_module(module_name)
                importlib.reload(module)
            except ImportError:
                pytest.skip(f"Module {module_name} not yet implemented")

            for warning in w:
                if issubclass(warning.category, DeprecationWarning):
                    msg = str(warning.message)
                    assert (
                        "v0.3.0" in msg or "removed" in msg.lower()
                    ), f"Warning missing removal version: {msg}"

    @pytest.mark.parametrize("module_name", DEPRECATED_PHASE_MODULES)
    def test_warning_includes_alternative(self, module_name: str) -> None:
        """AC1: All deprecation warnings must include what to use instead."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            try:
                module = importlib.import_module(module_name)
                importlib.reload(module)
            except ImportError:
                pytest.skip(f"Module {module_name} not yet implemented")

            for warning in w:
                if issubclass(warning.category, DeprecationWarning):
                    msg = str(warning.message)
                    assert (
                        "Use" in msg or "use" in msg or "instead" in msg.lower()
                    ), f"Warning missing alternative: {msg}"


class TestPhaseDetectorDeprecation:
    """Tests for phase_detector.py deprecation (AC3)."""

    def test_module_import_warns_on_reload(self) -> None:
        """AC2/AC3: Reloading phase_detector raises DeprecationWarning visible in logs."""
        # Import to ensure module is in sys.modules
        import src.pattern_engine.phase_detector as phase_detector

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # Reload triggers the module-level warning again
            importlib.reload(phase_detector)

            deprecation_warnings = [
                x
                for x in w
                if issubclass(x.category, DeprecationWarning) and "phase_detector" in str(x.message)
            ]
            assert len(deprecation_warnings) >= 1, "No warnings captured on module reload"
            assert "deprecated" in str(deprecation_warnings[0].message).lower()
            assert "phase_detection" in str(deprecation_warnings[0].message)
            assert "v0.3.0" in str(deprecation_warnings[0].message)

    def test_warning_message_format(self) -> None:
        """AC1: Warning follows standard format."""
        import src.pattern_engine.phase_detector as phase_detector

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            importlib.reload(phase_detector)

            # Find the module deprecation warning
            module_warning = None
            for warning in w:
                if issubclass(warning.category, DeprecationWarning):
                    if "phase_detector" in str(warning.message):
                        module_warning = warning
                        break

            assert module_warning is not None, "No module deprecation warning found"
            msg = str(module_warning.message)

            # Verify format: mentions old, new, and version
            assert "deprecated" in msg.lower(), "Should say 'deprecated'"
            assert "phase_detection" in msg, "Should mention new module"
            assert "v0.3.0" in msg, "Should mention removal version"

    def test_function_deprecation_detect_selling_climax(self) -> None:
        """AC3: Function call triggers DeprecationWarning."""
        from unittest.mock import patch

        from src.pattern_engine.phase_detector import detect_selling_climax

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            with patch(
                "src.pattern_engine._phase_detector_impl.detect_selling_climax"
            ) as mock_impl:
                mock_impl.return_value = None
                detect_selling_climax([], [])

            func_warnings = [
                x
                for x in w
                if issubclass(x.category, DeprecationWarning)
                and "detect_selling_climax" in str(x.message)
            ]
            assert len(func_warnings) >= 1, "Function call should raise DeprecationWarning"

    def test_function_deprecation_detect_automatic_rally(self) -> None:
        """AC3: Function call triggers DeprecationWarning."""
        from unittest.mock import MagicMock, patch

        from src.pattern_engine.phase_detector import detect_automatic_rally

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            with patch(
                "src.pattern_engine._phase_detector_impl.detect_automatic_rally"
            ) as mock_impl:
                mock_impl.return_value = None
                detect_automatic_rally([], MagicMock(), [])

            func_warnings = [
                x
                for x in w
                if issubclass(x.category, DeprecationWarning)
                and "detect_automatic_rally" in str(x.message)
            ]
            assert len(func_warnings) >= 1


class TestPhaseDetectorV2Deprecation:
    """Tests for phase_detector_v2.py deprecation (AC3)."""

    def test_module_import_warns_on_reload(self) -> None:
        """AC2/AC3: Reloading phase_detector_v2 raises DeprecationWarning."""
        from src.pattern_engine import phase_detector_v2

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            importlib.reload(phase_detector_v2)

            deprecation_warnings = [
                x
                for x in w
                if issubclass(x.category, DeprecationWarning)
                and "phase_detector_v2" in str(x.message)
            ]
            assert len(deprecation_warnings) >= 1
            assert "v0.3.0" in str(deprecation_warnings[0].message)

    def test_class_instantiation_warns(self) -> None:
        """AC3: PhaseDetector class instantiation triggers warning."""
        from unittest.mock import MagicMock, patch

        from src.pattern_engine.phase_detector_v2 import PhaseDetector

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            with patch("src.pattern_engine._phase_detector_v2_impl.PhaseDetector") as mock_impl:
                mock_impl.return_value = MagicMock()
                PhaseDetector()

            warning_msgs = [str(warning.message) for warning in w]
            assert any("PhaseDetector" in msg for msg in warning_msgs)

    def test_get_current_phase_warns(self) -> None:
        """AC3: get_current_phase function triggers warning."""
        from unittest.mock import MagicMock, patch

        from src.pattern_engine.phase_detector_v2 import get_current_phase

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            with patch("src.pattern_engine._phase_detector_v2_impl.get_current_phase") as mock_impl:
                mock_impl.return_value = None
                get_current_phase(MagicMock())

            func_warnings = [
                x
                for x in w
                if issubclass(x.category, DeprecationWarning)
                and "get_current_phase" in str(x.message)
            ]
            assert len(func_warnings) >= 1


class TestBacktestModelsPackage:
    """Tests for models/backtest/ package documentation (AC3 - if applicable)."""

    def test_backtest_package_has_usage_documentation(self) -> None:
        """Backtest package __init__.py documents correct import pattern."""
        from src.models import backtest

        # Package should have docstring with usage guidance
        assert backtest.__doc__ is not None
        assert "backtest" in backtest.__doc__.lower() or "Usage" in backtest.__doc__


class TestDeprecationTimeline:
    """Tests for consistent deprecation timeline (AC4)."""

    def test_all_deprecation_warnings_use_v030(self) -> None:
        """AC4: All deprecation warnings should use v0.3.0 removal timeline."""
        from src.pattern_engine import phase_detector, phase_detector_v2

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # Reload both modules to capture their warnings
            importlib.reload(phase_detector)
            importlib.reload(phase_detector_v2)

            # Verify all deprecation warnings mention v0.3.0
            deprecation_warnings = [
                x
                for x in w
                if issubclass(x.category, DeprecationWarning)
                and ("phase_detector" in str(x.message))
            ]

            assert (
                len(deprecation_warnings) >= 2
            ), "Should have deprecation warnings from both modules"

            for warning in deprecation_warnings:
                msg = str(warning.message)
                assert "v0.3.0" in msg, f"Warning missing v0.3.0: {msg}"


class TestFacadeTypesReExport:
    """Tests that facades properly re-export types from new packages."""

    def test_phase_detector_reexports_types(self) -> None:
        """Facades re-export types from phase_detection package."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            from src.pattern_engine.phase_detection import (
                DetectionConfig as NewDetectionConfig,
            )
            from src.pattern_engine.phase_detection import EventType as NewEventType
            from src.pattern_engine.phase_detection import PhaseEvent as NewPhaseEvent
            from src.pattern_engine.phase_detection import PhaseResult as NewPhaseResult
            from src.pattern_engine.phase_detection import PhaseType as NewPhaseType
            from src.pattern_engine.phase_detector import (
                DetectionConfig,
                EventType,
                PhaseEvent,
                PhaseResult,
                PhaseType,
            )

            assert PhaseType is NewPhaseType
            assert EventType is NewEventType
            assert PhaseEvent is NewPhaseEvent
            assert PhaseResult is NewPhaseResult
            assert DetectionConfig is NewDetectionConfig

    def test_phase_detector_v2_reexports_types(self) -> None:
        """phase_detector_v2 re-exports types from phase_detection package."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            from src.pattern_engine.phase_detection import (
                DetectionConfig as NewDetectionConfig,
            )
            from src.pattern_engine.phase_detection import EventType as NewEventType
            from src.pattern_engine.phase_detector_v2 import (
                DetectionConfig,
                EventType,
            )

            assert EventType is NewEventType
            assert DetectionConfig is NewDetectionConfig


class TestWarningsVisibleInOutput:
    """Tests that warnings appear in test output (AC2)."""

    def test_warnings_are_deprecation_type(self) -> None:
        """AC2: Warnings use DeprecationWarning category (visible in pytest)."""
        from src.pattern_engine import phase_detector

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            importlib.reload(phase_detector)

            # Verify all are proper DeprecationWarning (not UserWarning, etc.)
            for warning in w:
                if "deprecated" in str(warning.message).lower():
                    assert issubclass(
                        warning.category, DeprecationWarning
                    ), f"Warning should be DeprecationWarning, got {warning.category}"

    @pytest.mark.filterwarnings("default::DeprecationWarning")
    def test_deprecation_warnings_not_errors(self) -> None:
        """AC2: Deprecation warnings don't fail tests (just visible)."""
        from src.pattern_engine import phase_detector, phase_detector_v2

        # Reloading should not raise - warnings should just be logged
        importlib.reload(phase_detector)
        importlib.reload(phase_detector_v2)

        # If we reach here, warnings didn't fail the test
        assert True


class TestBacktestEngineDeprecation:
    """Tests for backtesting engine deprecation warnings."""

    def test_backtest_engine_import_warns_on_reload(self) -> None:
        """AC3: Reloading backtest_engine raises DeprecationWarning."""
        from src.backtesting import backtest_engine

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            importlib.reload(backtest_engine)

            deprecation_warnings = [
                x
                for x in w
                if issubclass(x.category, DeprecationWarning)
                and "backtest_engine" in str(x.message)
            ]
            assert len(deprecation_warnings) >= 1, "backtest_engine reload should warn"

            msg = str(deprecation_warnings[0].message)
            assert "deprecated" in msg.lower()
            assert "v0.3.0" in msg, f"Warning missing v0.3.0: {msg}"

    def test_engine_enhanced_import_warns_on_reload(self) -> None:
        """AC3: Reloading engine_enhanced raises DeprecationWarning."""
        from src.backtesting import engine_enhanced

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            importlib.reload(engine_enhanced)

            deprecation_warnings = [
                x
                for x in w
                if issubclass(x.category, DeprecationWarning)
                and "engine_enhanced" in str(x.message)
            ]
            assert len(deprecation_warnings) >= 1, "engine_enhanced reload should warn"

            msg = str(deprecation_warnings[0].message)
            assert "deprecated" in msg.lower()
            assert "v0.3.0" in msg, f"Warning missing v0.3.0: {msg}"

    def test_backtest_engine_warns_with_alternative(self) -> None:
        """AC1: Warning includes UnifiedBacktestEngine as alternative."""
        from src.backtesting import backtest_engine

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            importlib.reload(backtest_engine)

            for warning in w:
                if issubclass(warning.category, DeprecationWarning):
                    msg = str(warning.message)
                    if "backtest_engine" in msg:
                        assert "UnifiedBacktestEngine" in msg
                        return

            pytest.fail("No warning mentioned UnifiedBacktestEngine")


class TestLegacyFacadeLineCount:
    """Test that facades remain compact."""

    def test_phase_detector_facade_under_limit(self) -> None:
        """Facade should be thin wrapper, not bloated."""
        import inspect

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from src.pattern_engine import phase_detector

            source_file = Path(inspect.getfile(phase_detector))
            line_count = len(source_file.read_text().splitlines())

        assert (
            line_count < MAX_FACADE_LINES
        ), f"phase_detector.py has {line_count} lines, should be <{MAX_FACADE_LINES}"

    def test_phase_detector_v2_facade_under_limit(self) -> None:
        """Facade should be thin wrapper, not bloated."""
        import inspect

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from src.pattern_engine import phase_detector_v2

            source_file = Path(inspect.getfile(phase_detector_v2))
            line_count = len(source_file.read_text().splitlines())

        assert (
            line_count < MAX_FACADE_LINES
        ), f"phase_detector_v2.py has {line_count} lines, should be <{MAX_FACADE_LINES}"
