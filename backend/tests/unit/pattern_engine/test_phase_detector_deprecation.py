"""
Deprecation tests for phase_detector.py and phase_detector_v2.py facades.

Story 22.7c: Phase Detector Deprecation Cleanup
These tests verify that:
1. Import warnings are raised on module load
2. Class instantiation triggers deprecation warnings
3. Function calls trigger deprecation warnings
4. Warning messages contain migration guidance
5. Facades properly delegate to implementations
"""

import warnings
from unittest.mock import MagicMock, patch

import pytest


class TestPhaseDetectorModuleDeprecation:
    """Test deprecation warnings for phase_detector module."""

    def test_import_raises_deprecation_warning(self) -> None:
        """AC3: Importing phase_detector raises DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Force reimport by removing from cache
            import sys

            # Remove cached modules to force fresh import
            for mod in list(sys.modules.keys()):
                if "phase_detector" in mod and "_impl" not in mod:
                    del sys.modules[mod]

            # Import should trigger warning
            import src.pattern_engine.phase_detector  # noqa: F401

            # Find the module import warning
            module_warnings = [
                x
                for x in w
                if issubclass(x.category, DeprecationWarning)
                and "phase_detector" in str(x.message)
                and "deprecated" in str(x.message).lower()
            ]
            assert len(module_warnings) >= 1, "Module import should raise DeprecationWarning"

    def test_warning_message_contains_migration_guidance(self) -> None:
        """AC4: Warning message includes migration path."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import sys

            for mod in list(sys.modules.keys()):
                if "phase_detector" in mod and "_impl" not in mod:
                    del sys.modules[mod]

            import src.pattern_engine.phase_detector  # noqa: F401

            # Check any deprecation warning contains migration guidance
            for warning in w:
                if issubclass(warning.category, DeprecationWarning):
                    msg = str(warning.message)
                    if "phase_detection" in msg:
                        # Found migration guidance
                        assert True
                        return

            # If we get here, no warning had migration guidance
            pytest.fail("No deprecation warning contained migration guidance to phase_detection")

    def test_warning_message_contains_removal_version(self) -> None:
        """AC4: Warning message includes removal version."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import sys

            for mod in list(sys.modules.keys()):
                if "phase_detector" in mod and "_impl" not in mod:
                    del sys.modules[mod]

            import src.pattern_engine.phase_detector  # noqa: F401

            # Check any deprecation warning contains version info
            for warning in w:
                if issubclass(warning.category, DeprecationWarning):
                    msg = str(warning.message)
                    if "v0.3.0" in msg:
                        assert True
                        return

            pytest.fail("No deprecation warning contained removal version v0.3.0")


class TestPhaseDetectorFunctionDeprecation:
    """Test deprecation warnings for phase_detector functions."""

    def test_detect_selling_climax_raises_deprecation_warning(self) -> None:
        """Function call triggers DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.pattern_engine.phase_detector import detect_selling_climax

            # Mock the bars and volume_analysis to avoid actual execution
            with patch(
                "src.pattern_engine._phase_detector_impl.detect_selling_climax"
            ) as mock_impl:
                mock_impl.return_value = None
                detect_selling_climax([], [])

            # Check for function-level deprecation warning
            func_warnings = [
                x
                for x in w
                if issubclass(x.category, DeprecationWarning)
                and "detect_selling_climax" in str(x.message)
            ]
            assert len(func_warnings) >= 1, "Function call should raise DeprecationWarning"

    def test_detect_automatic_rally_raises_deprecation_warning(self) -> None:
        """Function call triggers DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.pattern_engine.phase_detector import detect_automatic_rally

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

    def test_calculate_phase_confidence_raises_deprecation_warning(self) -> None:
        """Function call triggers DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.pattern_engine.phase_detector import calculate_phase_confidence

            with patch(
                "src.pattern_engine._phase_detector_impl.calculate_phase_confidence"
            ) as mock_impl:
                mock_impl.return_value = 80
                calculate_phase_confidence(MagicMock(), MagicMock())

            func_warnings = [
                x
                for x in w
                if issubclass(x.category, DeprecationWarning)
                and "calculate_phase_confidence" in str(x.message)
            ]
            assert len(func_warnings) >= 1


class TestPhaseDetectorV2ModuleDeprecation:
    """Test deprecation warnings for phase_detector_v2 module."""

    def test_import_raises_deprecation_warning(self) -> None:
        """AC3: Importing phase_detector_v2 raises DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import sys

            for mod in list(sys.modules.keys()):
                if "phase_detector_v2" in mod and "_impl" not in mod:
                    del sys.modules[mod]

            import src.pattern_engine.phase_detector_v2  # noqa: F401

            module_warnings = [
                x
                for x in w
                if issubclass(x.category, DeprecationWarning)
                and "phase_detector_v2" in str(x.message)
                and "deprecated" in str(x.message).lower()
            ]
            assert len(module_warnings) >= 1, "Module import should raise DeprecationWarning"


class TestPhaseDetectorV2ClassDeprecation:
    """Test deprecation warnings for PhaseDetector class."""

    def test_instantiation_raises_deprecation_warning(self) -> None:
        """AC3: Class instantiation triggers DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.pattern_engine.phase_detector_v2 import PhaseDetector

            with patch("src.pattern_engine._phase_detector_v2_impl.PhaseDetector") as mock_impl:
                mock_impl.return_value = MagicMock()
                PhaseDetector()

            class_warnings = [
                x
                for x in w
                if issubclass(x.category, DeprecationWarning) and "PhaseDetector" in str(x.message)
            ]
            assert len(class_warnings) >= 1, "Class instantiation should raise DeprecationWarning"

    def test_warning_suggests_phase_classifier(self) -> None:
        """AC4: Warning suggests PhaseClassifier as replacement."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.pattern_engine.phase_detector_v2 import PhaseDetector

            with patch("src.pattern_engine._phase_detector_v2_impl.PhaseDetector") as mock_impl:
                mock_impl.return_value = MagicMock()
                PhaseDetector()

            for warning in w:
                if issubclass(warning.category, DeprecationWarning):
                    msg = str(warning.message)
                    if "PhaseClassifier" in msg:
                        assert True
                        return

            pytest.fail("No warning suggested PhaseClassifier replacement")


class TestPhaseDetectorV2FunctionDeprecation:
    """Test deprecation warnings for phase_detector_v2 functions."""

    def test_get_current_phase_raises_deprecation_warning(self) -> None:
        """Function call triggers DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.pattern_engine.phase_detector_v2 import get_current_phase

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

    def test_is_trading_allowed_raises_deprecation_warning(self) -> None:
        """Function call triggers DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.pattern_engine.phase_detector_v2 import is_trading_allowed

            with patch(
                "src.pattern_engine._phase_detector_v2_impl.is_trading_allowed"
            ) as mock_impl:
                mock_impl.return_value = False
                is_trading_allowed(MagicMock())

            func_warnings = [
                x
                for x in w
                if issubclass(x.category, DeprecationWarning)
                and "is_trading_allowed" in str(x.message)
            ]
            assert len(func_warnings) >= 1

    def test_get_phase_description_raises_deprecation_warning(self) -> None:
        """Function call triggers DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.pattern_engine.phase_detector_v2 import get_phase_description

            with patch(
                "src.pattern_engine._phase_detector_v2_impl.get_phase_description"
            ) as mock_impl:
                mock_impl.return_value = "test"
                get_phase_description(MagicMock())

            func_warnings = [
                x
                for x in w
                if issubclass(x.category, DeprecationWarning)
                and "get_phase_description" in str(x.message)
            ]
            assert len(func_warnings) >= 1


class TestFacadeDelegation:
    """Test that facades properly delegate to implementations."""

    def test_phase_detector_delegates_detect_phase(self) -> None:
        """AC1/AC2: Facade delegates to implementation."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # Ignore deprecation for this test
            from src.pattern_engine.phase_detector_v2 import PhaseDetector

            with patch("src.pattern_engine._phase_detector_v2_impl.PhaseDetector") as mock_class:
                mock_instance = MagicMock()
                mock_instance.detect_phase.return_value = MagicMock()
                mock_class.return_value = mock_instance

                detector = PhaseDetector()
                detector.detect_phase(
                    trading_range=MagicMock(),
                    bars=[],
                    volume_analysis=[],
                )

                mock_instance.detect_phase.assert_called_once()

    def test_types_re_exported_from_new_package(self) -> None:
        """AC1/AC2: Types are re-exported from phase_detection package."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            # Check phase_detector re-exports
            # Verify they're the same as the new package exports
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


class TestFacadeLineCount:
    """Test that facades meet line count requirements."""

    def test_phase_detector_facade_under_200_lines(self) -> None:
        """AC5: phase_detector.py facade is compact."""
        import inspect

        from src.pattern_engine import phase_detector

        source_file = inspect.getfile(phase_detector)
        with open(source_file) as f:
            line_count = len(f.readlines())

        # Allow some buffer over 100 for type hints and docstrings
        assert line_count < 200, f"phase_detector.py has {line_count} lines, should be <200"

    def test_phase_detector_v2_facade_under_200_lines(self) -> None:
        """AC5: phase_detector_v2.py facade is compact."""
        import inspect

        from src.pattern_engine import phase_detector_v2

        source_file = inspect.getfile(phase_detector_v2)
        with open(source_file) as f:
            line_count = len(f.readlines())

        assert line_count < 200, f"phase_detector_v2.py has {line_count} lines, should be <200"
