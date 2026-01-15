"""
Dependency Injection Container for Orchestrator.

Provides lazy-loaded access to all detector modules from previous epics.
Supports production, test, and mock modes for flexible testing.

Story 8.1: Master Orchestrator Architecture (AC: 4)
Story 18.3: Fix Inconsistent Error Handling - Uses DetectorLoader for consistent error handling
"""

from typing import Any, Literal

import structlog

from src.orchestrator.config import OrchestratorConfig
from src.orchestrator.detector_loader import DetectorLoader, DetectorLoadError, HealthStatus

logger = structlog.get_logger(__name__)


class OrchestratorContainer:
    """
    Dependency injection container for orchestrator components.

    Provides lazy-loaded access to all detectors and analyzers from previous
    epics. Supports three modes:
    - production: Real detector implementations
    - test: Real implementations with test-friendly configuration
    - mock: Mock implementations for unit testing

    All detectors are loaded via DetectorLoader for consistent error handling.
    Critical detectors raise DetectorLoadError on failure.
    Optional detectors return None on failure.

    Detectors loaded:
    - Volume analyzers (Stories 2.1-2.4)
    - Range detectors (Stories 3.1-3.7)
    - Phase detectors (Stories 4.1-4.7)
    - Pattern detectors (Stories 5.1-5.6, 6.1-6.7)
    - Risk manager (Story 7.8)

    Example:
        >>> container = OrchestratorContainer(mode="production")
        >>> volume_analyzer = container.volume_analyzer
        >>> risk_manager = container.risk_manager
    """

    def __init__(
        self,
        config: OrchestratorConfig | None = None,
        mode: Literal["production", "test", "mock"] | None = None,
    ) -> None:
        """
        Initialize container with configuration.

        Args:
            config: Optional orchestrator configuration
            mode: Detector mode (overrides config if provided)
        """
        self._config = config or OrchestratorConfig()
        self._mode = mode or self._config.detector_mode
        self._loader = DetectorLoader()

        # Lazy-loaded detector instances
        self._detectors: dict[str, Any] = {}

        # Mock implementations for testing
        self._mocks: dict[str, Any] = {}

        # Health tracking
        self._loaded_detectors: list[str] = []
        self._failed_detectors: list[str] = []
        self._load_errors: list[DetectorLoadError] = []

        logger.info(
            "orchestrator_container_initialized",
            mode=self._mode,
        )

    @property
    def mode(self) -> str:
        """Get current detector mode."""
        return self._mode

    def _load_detector(
        self,
        name: str,
        import_path: str,
        class_name: str,
        critical: bool,
    ) -> Any | None:
        """
        Load a detector using the centralized DetectorLoader.

        Args:
            name: Detector name for tracking and mocking
            import_path: Module path to import
            class_name: Class to instantiate
            critical: If True, raises on failure; if False, returns None

        Returns:
            Detector instance, or None for non-critical failures

        Raises:
            DetectorLoadError: If critical detector fails to load
        """
        # Check for mock first
        if self._mode == "mock" and name in self._mocks:
            return self._mocks[name]

        # Return cached instance if already loaded
        if name in self._detectors:
            return self._detectors[name]

        # Skip if already failed
        if name in self._failed_detectors:
            return None

        try:
            if critical:
                instance = self._loader.load(name, import_path, class_name)
            else:
                instance = self._loader.load_optional(name, import_path, class_name)

            if instance is not None:
                self._detectors[name] = instance
                self._loaded_detectors.append(name)
            else:
                self._failed_detectors.append(name)

            return instance

        except DetectorLoadError as e:
            self._failed_detectors.append(name)
            self._load_errors.append(e)
            raise

    # Volume Analysis (Epic 2)

    @property
    def volume_analyzer(self) -> Any:
        """
        Get VolumeAnalyzer instance (Stories 2.1-2.4).

        Returns:
            VolumeAnalyzer for volume ratio, spread ratio, close position,
            and effort/result classification.

        Raises:
            DetectorLoadError: If volume analyzer fails to load (critical detector)
        """
        return self._load_detector(
            "volume_analyzer",
            "src.pattern_engine.volume_analyzer",
            "VolumeAnalyzer",
            critical=True,
        )

    # Range Detection (Epic 3)

    @property
    def pivot_detector(self) -> Any | None:
        """
        Get PivotDetector instance (Story 3.1).

        Returns:
            PivotDetector for identifying pivot highs and lows,
            or None if not available.
        """
        return self._load_detector(
            "pivot_detector",
            "src.pattern_engine.pivot_detector",
            "PivotDetector",
            critical=False,
        )

    @property
    def trading_range_detector(self) -> Any:
        """
        Get TradingRangeDetector instance (Story 3.2).

        Returns:
            TradingRangeDetector for range clustering and detection.

        Raises:
            DetectorLoadError: If trading range detector fails to load (critical detector)
        """
        return self._load_detector(
            "trading_range_detector",
            "src.pattern_engine.trading_range_detector",
            "TradingRangeDetector",
            critical=True,
        )

    @property
    def range_quality_scorer(self) -> Any | None:
        """
        Get RangeQualityScorer instance (Story 3.3).

        Returns:
            RangeQualityScorer for scoring trading range quality,
            or None if not available.
        """
        return self._load_detector(
            "range_quality_scorer",
            "src.pattern_engine.range_quality",
            "RangeQualityScorer",
            critical=False,
        )

    @property
    def level_calculator(self) -> Any | None:
        """
        Get LevelCalculator instance (Stories 3.4-3.6).

        Returns:
            LevelCalculator for Creek, Ice, and Jump level calculation,
            or None if not available.
        """
        return self._load_detector(
            "level_calculator",
            "src.pattern_engine.level_calculator",
            "LevelCalculator",
            critical=False,
        )

    @property
    def zone_mapper(self) -> Any | None:
        """
        Get ZoneMapper instance (Story 3.7).

        Returns:
            ZoneMapper for supply/demand zone detection,
            or None if not available.
        """
        return self._load_detector(
            "zone_mapper",
            "src.pattern_engine.zone_mapper",
            "ZoneMapper",
            critical=False,
        )

    # Pattern Detection (Epics 5-6)

    @property
    def sos_detector(self) -> Any | None:
        """
        Get SOS Detector Orchestrator instance (Stories 6.1-6.5).

        Returns:
            SOSDetectorOrchestrator for Sign of Strength detection,
            or None if not available.
        """
        return self._load_detector(
            "sos_detector",
            "src.pattern_engine.detectors.sos_detector_orchestrator",
            "SOSDetector",
            critical=False,
        )

    @property
    def lps_detector(self) -> Any | None:
        """
        Get LPS Detector Orchestrator instance (Stories 6.6-6.7).

        Returns:
            LPSDetectorOrchestrator for Last Point of Support detection,
            or None if not available.
        """
        return self._load_detector(
            "lps_detector",
            "src.pattern_engine.detectors.lps_detector_orchestrator",
            "LPSDetector",
            critical=False,
        )

    # Risk Management (Epic 7)

    @property
    def risk_manager(self) -> Any:
        """
        Get RiskManager instance (Story 7.8).

        Returns:
            RiskManager for unified risk validation and position sizing.

        Raises:
            DetectorLoadError: If risk manager fails to load (critical detector)
        """
        return self._load_detector(
            "risk_manager",
            "src.risk_management.risk_manager",
            "RiskManager",
            critical=True,
        )

    # Mock injection for testing

    def set_mock(self, name: str, mock_instance: Any) -> None:
        """
        Set a mock implementation for testing.

        Args:
            name: Detector name (e.g., "volume_analyzer", "risk_manager")
            mock_instance: Mock object to use
        """
        self._mocks[name] = mock_instance
        logger.debug("mock_set", detector=name)

    def clear_mocks(self) -> None:
        """Clear all mock implementations."""
        self._mocks.clear()
        logger.debug("mocks_cleared")

    # Health check

    def health_check(self) -> HealthStatus:
        """
        Perform health check on all detectors.

        Returns:
            HealthStatus with detailed results including:
            - healthy: Overall health status
            - detectors_loaded: Count of loaded detectors
            - detectors_failed: Count of failed detectors
            - failures: List of specific failure reasons
            - details: Per-detector health status

        Note:
            This method attempts to load all detectors and checks their health.
            Failures are logged and included in the result, not swallowed.
        """
        details: dict[str, bool] = {}
        failures: list[str] = []

        # Try to load all detectors
        detector_accessors = [
            ("volume_analyzer", lambda: self.volume_analyzer, True),
            ("pivot_detector", lambda: self.pivot_detector, False),
            ("trading_range_detector", lambda: self.trading_range_detector, True),
            ("range_quality_scorer", lambda: self.range_quality_scorer, False),
            ("level_calculator", lambda: self.level_calculator, False),
            ("zone_mapper", lambda: self.zone_mapper, False),
            ("sos_detector", lambda: self.sos_detector, False),
            ("lps_detector", lambda: self.lps_detector, False),
            ("risk_manager", lambda: self.risk_manager, True),
        ]

        for name, accessor, critical in detector_accessors:
            try:
                detector = accessor()

                if detector is None:
                    details[name] = False
                    failures.append(f"{name}: not available (returned None)")
                    logger.warning(
                        "health_check_detector_unavailable",
                        detector=name,
                    )
                elif hasattr(detector, "health_check"):
                    # Call detector's own health check if available
                    try:
                        is_healthy = detector.health_check()
                        details[name] = bool(is_healthy)
                        if not is_healthy:
                            failures.append(f"{name}: health check returned False")
                    except Exception as e:
                        details[name] = False
                        failures.append(f"{name}: health check raised {type(e).__name__}: {e}")
                        logger.error(
                            "health_check_failed",
                            detector=name,
                            error=str(e),
                        )
                else:
                    # Detector loaded successfully, no health_check method
                    details[name] = True

            except DetectorLoadError as e:
                details[name] = False
                failures.append(f"{name}: {e}")
                logger.error(
                    "health_check_load_failed",
                    detector=name,
                    error=str(e),
                )

        loaded_count = sum(1 for v in details.values() if v)
        failed_count = sum(1 for v in details.values() if not v)

        return HealthStatus(
            healthy=failed_count == 0,
            detectors_loaded=loaded_count,
            detectors_failed=failed_count,
            failures=failures,
            details=details,
        )

    def get_load_errors(self) -> list[DetectorLoadError]:
        """
        Get list of detector load errors encountered.

        Returns:
            List of DetectorLoadError exceptions from failed loads
        """
        return self._load_errors.copy()


# Singleton instance
_container_instance: OrchestratorContainer | None = None


def get_orchestrator_container(
    config: OrchestratorConfig | None = None,
) -> OrchestratorContainer:
    """
    Get the singleton container instance.

    Args:
        config: Optional configuration (used only on first call)

    Returns:
        OrchestratorContainer singleton instance
    """
    global _container_instance
    if _container_instance is None:
        _container_instance = OrchestratorContainer(config)
    return _container_instance


def reset_orchestrator_container(
    config: OrchestratorConfig | None = None,
    mode: Literal["production", "test", "mock"] | None = None,
) -> OrchestratorContainer:
    """
    Reset the singleton container (for testing).

    Args:
        config: Optional configuration for new instance
        mode: Optional detector mode

    Returns:
        New OrchestratorContainer instance
    """
    global _container_instance
    _container_instance = OrchestratorContainer(config, mode)
    return _container_instance
