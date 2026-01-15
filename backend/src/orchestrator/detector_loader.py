"""
Centralized detector loading with consistent error handling.

Story 18.3: Fix Inconsistent Error Handling in container.py

Provides a unified approach to loading detectors with:
- Consistent error handling across all detectors
- Structured logging with full context
- Custom exception with original error preservation
"""

import importlib
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class DetectorLoadError(Exception):
    """
    Raised when a detector fails to load.

    Attributes:
        detector_name: Name of the detector that failed to load
        import_path: Module path that was attempted
        original_error: The underlying exception that caused the failure
    """

    def __init__(
        self,
        detector_name: str,
        original_error: Exception,
        import_path: str | None = None,
    ) -> None:
        self.detector_name = detector_name
        self.original_error = original_error
        self.import_path = import_path

        message = f"Failed to load detector '{detector_name}'"
        if import_path:
            message += f" from '{import_path}'"
        message += f": {original_error}"

        super().__init__(message)


@dataclass
class HealthStatus:
    """
    Health check result with detailed status information.

    Attributes:
        healthy: Overall health status (True if no failures)
        detectors_loaded: Count of successfully loaded detectors
        detectors_failed: Count of failed detectors
        failures: List of failure descriptions
        details: Per-detector health status mapping
    """

    healthy: bool
    detectors_loaded: int
    detectors_failed: int
    failures: list[str] = field(default_factory=list)
    details: dict[str, bool] = field(default_factory=dict)

    @property
    def status(self) -> str:
        """Get status string for backwards compatibility."""
        if self.healthy:
            return "healthy"
        elif self.detectors_failed < self.detectors_loaded:
            return "degraded"
        else:
            return "unhealthy"


class DetectorLoader:
    """
    Centralized detector loading with consistent error handling.

    All detectors are loaded through this class to ensure:
    - Consistent exception types (DetectorLoadError)
    - Structured logging with context
    - Predictable failure behavior
    """

    def load(
        self,
        name: str,
        import_path: str,
        class_name: str | None = None,
    ) -> Any:
        """
        Load a detector with consistent error handling.

        Args:
            name: Friendly name for logging/errors
            import_path: Module path to import (e.g., 'src.pattern_engine.volume_analyzer')
            class_name: Class to get from module (defaults to name if not provided)

        Returns:
            Initialized detector instance

        Raises:
            DetectorLoadError: If import or initialization fails
        """
        class_name = class_name or name

        logger.debug(
            "detector_loading",
            detector=name,
            import_path=import_path,
            class_name=class_name,
        )

        try:
            module = importlib.import_module(import_path)
            detector_class = getattr(module, class_name)
            instance = detector_class()

            logger.debug("detector_loaded", detector=name)
            return instance

        except ImportError as e:
            logger.error(
                "detector_import_failed",
                detector=name,
                import_path=import_path,
                error=str(e),
            )
            raise DetectorLoadError(name, e, import_path) from e

        except AttributeError as e:
            logger.error(
                "detector_class_not_found",
                detector=name,
                import_path=import_path,
                class_name=class_name,
                error=str(e),
            )
            raise DetectorLoadError(name, e, import_path) from e

        except Exception as e:
            logger.error(
                "detector_init_failed",
                detector=name,
                import_path=import_path,
                class_name=class_name,
                error=str(e),
                exc_info=True,
            )
            raise DetectorLoadError(name, e, import_path) from e

    def load_optional(
        self,
        name: str,
        import_path: str,
        class_name: str | None = None,
    ) -> Any | None:
        """
        Load a detector, returning None on failure (for optional detectors).

        Still logs the error for debugging, but doesn't raise.

        Args:
            name: Friendly name for logging/errors
            import_path: Module path to import
            class_name: Class to get from module (defaults to name if not provided)

        Returns:
            Initialized detector instance, or None if loading failed
        """
        try:
            return self.load(name, import_path, class_name)
        except DetectorLoadError:
            return None
