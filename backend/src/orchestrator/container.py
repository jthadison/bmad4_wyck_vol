"""
Dependency Injection Container for Orchestrator.

Provides lazy-loaded access to all detector modules from previous epics.
Supports production, test, and mock modes for flexible testing.

Story 8.1: Master Orchestrator Architecture (AC: 4)
"""

from typing import Any, Literal

import structlog

from src.orchestrator.config import OrchestratorConfig

logger = structlog.get_logger(__name__)


class OrchestratorContainer:
    """
    Dependency injection container for orchestrator components.

    Provides lazy-loaded access to all detectors and analyzers from previous
    epics. Supports three modes:
    - production: Real detector implementations
    - test: Real implementations with test-friendly configuration
    - mock: Mock implementations for unit testing

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

        # Lazy-loaded detector instances
        self._volume_analyzer: Any = None
        self._range_detector: Any = None
        self._phase_detector: Any = None
        self._spring_detector: Any = None
        self._sos_detector: Any = None
        self._lps_detector: Any = None
        self._risk_manager: Any = None
        self._trading_range_detector: Any = None
        self._pivot_detector: Any = None
        self._range_quality_scorer: Any = None
        self._level_calculator: Any = None
        self._zone_mapper: Any = None

        # Mock implementations for testing
        self._mocks: dict[str, Any] = {}

        # Health tracking
        self._loaded_detectors: list[str] = []
        self._failed_detectors: list[str] = []

        logger.info(
            "orchestrator_container_initialized",
            mode=self._mode,
        )

    @property
    def mode(self) -> str:
        """Get current detector mode."""
        return self._mode

    # Volume Analysis (Epic 2)

    @property
    def volume_analyzer(self) -> Any:
        """
        Get VolumeAnalyzer instance (Stories 2.1-2.4).

        Returns:
            VolumeAnalyzer for volume ratio, spread ratio, close position,
            and effort/result classification.
        """
        if self._mode == "mock" and "volume_analyzer" in self._mocks:
            return self._mocks["volume_analyzer"]

        if self._volume_analyzer is None:
            try:
                from src.pattern_engine.volume_analyzer import VolumeAnalyzer

                self._volume_analyzer = VolumeAnalyzer()
                self._loaded_detectors.append("volume_analyzer")
                logger.debug("detector_loaded", detector="volume_analyzer")
            except ImportError as e:
                self._failed_detectors.append("volume_analyzer")
                logger.error(
                    "detector_load_failed",
                    detector="volume_analyzer",
                    error=str(e),
                )
                raise

        return self._volume_analyzer

    # Range Detection (Epic 3)

    @property
    def pivot_detector(self) -> Any:
        """
        Get PivotDetector instance (Story 3.1).

        Returns:
            PivotDetector for identifying pivot highs and lows.
        """
        if self._mode == "mock" and "pivot_detector" in self._mocks:
            return self._mocks["pivot_detector"]

        if self._pivot_detector is None:
            try:
                from src.pattern_engine.pivot_detector import PivotDetector

                self._pivot_detector = PivotDetector()
                self._loaded_detectors.append("pivot_detector")
                logger.debug("detector_loaded", detector="pivot_detector")
            except ImportError as e:
                self._failed_detectors.append("pivot_detector")
                logger.error(
                    "detector_load_failed",
                    detector="pivot_detector",
                    error=str(e),
                )
                raise

        return self._pivot_detector

    @property
    def trading_range_detector(self) -> Any:
        """
        Get TradingRangeDetector instance (Story 3.2).

        Returns:
            TradingRangeDetector for range clustering and detection.
        """
        if self._mode == "mock" and "trading_range_detector" in self._mocks:
            return self._mocks["trading_range_detector"]

        if self._trading_range_detector is None:
            try:
                from src.pattern_engine.trading_range_detector import TradingRangeDetector

                self._trading_range_detector = TradingRangeDetector()
                self._loaded_detectors.append("trading_range_detector")
                logger.debug("detector_loaded", detector="trading_range_detector")
            except ImportError as e:
                self._failed_detectors.append("trading_range_detector")
                logger.error(
                    "detector_load_failed",
                    detector="trading_range_detector",
                    error=str(e),
                )
                raise

        return self._trading_range_detector

    @property
    def range_quality_scorer(self) -> Any:
        """
        Get RangeQualityScorer instance (Story 3.3).

        Returns:
            RangeQualityScorer for scoring trading range quality.
        """
        if self._mode == "mock" and "range_quality_scorer" in self._mocks:
            return self._mocks["range_quality_scorer"]

        if self._range_quality_scorer is None:
            try:
                from src.pattern_engine.range_quality import RangeQualityScorer

                self._range_quality_scorer = RangeQualityScorer()
                self._loaded_detectors.append("range_quality_scorer")
                logger.debug("detector_loaded", detector="range_quality_scorer")
            except ImportError as e:
                self._failed_detectors.append("range_quality_scorer")
                logger.error(
                    "detector_load_failed",
                    detector="range_quality_scorer",
                    error=str(e),
                )
                raise

        return self._range_quality_scorer

    @property
    def level_calculator(self) -> Any:
        """
        Get LevelCalculator instance (Stories 3.4-3.6).

        Returns:
            LevelCalculator for Creek, Ice, and Jump level calculation.
        """
        if self._mode == "mock" and "level_calculator" in self._mocks:
            return self._mocks["level_calculator"]

        if self._level_calculator is None:
            try:
                from src.pattern_engine.level_calculator import LevelCalculator

                self._level_calculator = LevelCalculator()
                self._loaded_detectors.append("level_calculator")
                logger.debug("detector_loaded", detector="level_calculator")
            except ImportError as e:
                self._failed_detectors.append("level_calculator")
                logger.error(
                    "detector_load_failed",
                    detector="level_calculator",
                    error=str(e),
                )
                raise

        return self._level_calculator

    @property
    def zone_mapper(self) -> Any:
        """
        Get ZoneMapper instance (Story 3.7).

        Returns:
            ZoneMapper for supply/demand zone detection.
        """
        if self._mode == "mock" and "zone_mapper" in self._mocks:
            return self._mocks["zone_mapper"]

        if self._zone_mapper is None:
            try:
                from src.pattern_engine.zone_mapper import ZoneMapper

                self._zone_mapper = ZoneMapper()
                self._loaded_detectors.append("zone_mapper")
                logger.debug("detector_loaded", detector="zone_mapper")
            except ImportError as e:
                self._failed_detectors.append("zone_mapper")
                logger.error(
                    "detector_load_failed",
                    detector="zone_mapper",
                    error=str(e),
                )
                raise

        return self._zone_mapper

    # Pattern Detection (Epics 5-6)

    @property
    def sos_detector(self) -> Any:
        """
        Get SOS Detector Orchestrator instance (Stories 6.1-6.5).

        Returns:
            SOSDetectorOrchestrator for Sign of Strength detection.
        """
        if self._mode == "mock" and "sos_detector" in self._mocks:
            return self._mocks["sos_detector"]

        if self._sos_detector is None:
            try:
                from src.pattern_engine.detectors.sos_detector_orchestrator import (
                    SOSDetectorOrchestrator,
                )

                self._sos_detector = SOSDetectorOrchestrator()
                self._loaded_detectors.append("sos_detector")
                logger.debug("detector_loaded", detector="sos_detector")
            except ImportError as e:
                self._failed_detectors.append("sos_detector")
                logger.error(
                    "detector_load_failed",
                    detector="sos_detector",
                    error=str(e),
                )
                raise

        return self._sos_detector

    @property
    def lps_detector(self) -> Any:
        """
        Get LPS Detector Orchestrator instance (Stories 6.6-6.7).

        Returns:
            LPSDetectorOrchestrator for Last Point of Support detection.
        """
        if self._mode == "mock" and "lps_detector" in self._mocks:
            return self._mocks["lps_detector"]

        if self._lps_detector is None:
            try:
                from src.pattern_engine.detectors.lps_detector_orchestrator import (
                    LPSDetectorOrchestrator,
                )

                self._lps_detector = LPSDetectorOrchestrator()
                self._loaded_detectors.append("lps_detector")
                logger.debug("detector_loaded", detector="lps_detector")
            except ImportError as e:
                self._failed_detectors.append("lps_detector")
                logger.error(
                    "detector_load_failed",
                    detector="lps_detector",
                    error=str(e),
                )
                raise

        return self._lps_detector

    # Risk Management (Epic 7)

    @property
    def risk_manager(self) -> Any:
        """
        Get RiskManager instance (Story 7.8).

        Returns:
            RiskManager for unified risk validation and position sizing.
        """
        if self._mode == "mock" and "risk_manager" in self._mocks:
            return self._mocks["risk_manager"]

        if self._risk_manager is None:
            try:
                from src.risk_management.risk_manager import RiskManager

                self._risk_manager = RiskManager()
                self._loaded_detectors.append("risk_manager")
                logger.debug("detector_loaded", detector="risk_manager")
            except ImportError as e:
                self._failed_detectors.append("risk_manager")
                logger.error(
                    "detector_load_failed",
                    detector="risk_manager",
                    error=str(e),
                )
                raise

        return self._risk_manager

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

    def health_check(self) -> dict[str, Any]:
        """
        Perform health check on all detectors.

        Returns:
            Dictionary with:
            - status: "healthy", "degraded", or "unhealthy"
            - loaded: List of successfully loaded detectors
            - failed: List of failed detectors
            - mode: Current detector mode
        """
        # Try to load all detectors
        detectors = [
            ("volume_analyzer", lambda: self.volume_analyzer),
            ("pivot_detector", lambda: self.pivot_detector),
            ("trading_range_detector", lambda: self.trading_range_detector),
            ("range_quality_scorer", lambda: self.range_quality_scorer),
            ("level_calculator", lambda: self.level_calculator),
            ("zone_mapper", lambda: self.zone_mapper),
            ("sos_detector", lambda: self.sos_detector),
            ("lps_detector", lambda: self.lps_detector),
            ("risk_manager", lambda: self.risk_manager),
        ]

        for name, loader in detectors:
            if name not in self._loaded_detectors and name not in self._failed_detectors:
                try:
                    loader()
                except Exception:
                    pass  # Error already logged

        # Determine status
        total = len(detectors)
        loaded = len(self._loaded_detectors)
        failed = len(self._failed_detectors)

        if failed == 0:
            status = "healthy"
        elif failed < total / 2:
            status = "degraded"
        else:
            status = "unhealthy"

        return {
            "status": status,
            "loaded": self._loaded_detectors.copy(),
            "failed": self._failed_detectors.copy(),
            "mode": self._mode,
            "loaded_count": loaded,
            "failed_count": failed,
        }


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
