"""
Wyckoff event detection classes.

This module contains detector classes for identifying specific Wyckoff
events within price/volume data.

TODO (Story 22.7b): Migrate implementation from phase_detector_v2.py
"""

from abc import ABC, abstractmethod

import pandas as pd

from .types import DetectionConfig, PhaseEvent


class BaseEventDetector(ABC):
    """
    Base class for all event detectors.

    Provides common interface and configuration for Wyckoff event detection.
    Subclasses implement specific detection logic for each event type.

    Attributes:
        config: Detection configuration parameters
    """

    def __init__(self, config: DetectionConfig) -> None:
        """
        Initialize the event detector.

        Args:
            config: Detection configuration parameters
        """
        self.config = config

    @abstractmethod
    def detect(self, ohlcv: pd.DataFrame) -> list[PhaseEvent]:
        """
        Detect events in OHLCV data.

        Args:
            ohlcv: DataFrame with columns [timestamp, open, high, low, close, volume]

        Returns:
            List of detected PhaseEvent objects
        """
        pass

    def _validate_dataframe(self, ohlcv: pd.DataFrame) -> bool:
        """
        Validate that DataFrame has required columns.

        Args:
            ohlcv: DataFrame to validate

        Returns:
            True if valid, False otherwise
        """
        required_columns = {"timestamp", "open", "high", "low", "close", "volume"}
        return required_columns.issubset(set(ohlcv.columns))


class SellingClimaxDetector(BaseEventDetector):
    """
    Detects Selling Climax (SC) events.

    SC is characterized by:
    - Ultra-high volume (>2x average)
    - Wide spread down bar
    - Closes near low
    - Follows downtrend

    TODO (Story 22.7b): Migrate from phase_detector_v2.py
    """

    def detect(self, ohlcv: pd.DataFrame) -> list[PhaseEvent]:
        """
        Detect Selling Climax events in OHLCV data.

        Args:
            ohlcv: DataFrame with OHLCV data

        Returns:
            List of detected SC events

        Raises:
            ValueError: If DataFrame is missing required columns
            NotImplementedError: Implementation pending Story 22.7b
        """
        if not self._validate_dataframe(ohlcv):
            raise ValueError("Invalid DataFrame: missing required columns")
        raise NotImplementedError("Implementation pending Story 22.7b")


class AutomaticRallyDetector(BaseEventDetector):
    """
    Detects Automatic Rally (AR) events.

    AR is characterized by:
    - Follows SC within a few bars
    - Rally on declining volume
    - Establishes initial resistance

    TODO (Story 22.7b): Migrate from phase_detector_v2.py
    """

    def detect(self, ohlcv: pd.DataFrame) -> list[PhaseEvent]:
        """
        Detect Automatic Rally events in OHLCV data.

        Args:
            ohlcv: DataFrame with OHLCV data

        Returns:
            List of detected AR events

        Raises:
            ValueError: If DataFrame is missing required columns
            NotImplementedError: Implementation pending Story 22.7b
        """
        if not self._validate_dataframe(ohlcv):
            raise ValueError("Invalid DataFrame: missing required columns")
        raise NotImplementedError("Implementation pending Story 22.7b")


class SecondaryTestDetector(BaseEventDetector):
    """
    Detects Secondary Test (ST) events.

    ST is characterized by:
    - Tests SC low area
    - Lower volume than SC
    - May or may not reach SC low
    - Confirms support zone

    TODO (Story 22.7b): Migrate from phase_detector_v2.py
    """

    def detect(self, ohlcv: pd.DataFrame) -> list[PhaseEvent]:
        """
        Detect Secondary Test events in OHLCV data.

        Args:
            ohlcv: DataFrame with OHLCV data

        Returns:
            List of detected ST events

        Raises:
            ValueError: If DataFrame is missing required columns
            NotImplementedError: Implementation pending Story 22.7b
        """
        if not self._validate_dataframe(ohlcv):
            raise ValueError("Invalid DataFrame: missing required columns")
        raise NotImplementedError("Implementation pending Story 22.7b")


class SpringDetector(BaseEventDetector):
    """
    Detects Spring events (shakeout below support).

    Spring is characterized by:
    - Price breaks below support (Creek)
    - Low volume on the break (<0.7x average)
    - Quick recovery back above support
    - Occurs in Phase C

    Note: This is a reference interface. Full implementation requires
    integration with level detection (Creek/Ice) from other modules.

    TODO (Story 22.7b): Migrate from phase_detector_v2.py
    """

    def detect(self, ohlcv: pd.DataFrame) -> list[PhaseEvent]:
        """
        Detect Spring events in OHLCV data.

        Args:
            ohlcv: DataFrame with OHLCV data

        Returns:
            List of detected Spring events

        Raises:
            ValueError: If DataFrame is missing required columns
            NotImplementedError: Implementation pending Story 22.7b
        """
        if not self._validate_dataframe(ohlcv):
            raise ValueError("Invalid DataFrame: missing required columns")
        raise NotImplementedError("Implementation pending Story 22.7b")


class SignOfStrengthDetector(BaseEventDetector):
    """
    Detects Sign of Strength (SOS) events.

    SOS is characterized by:
    - Decisive break above resistance (Ice)
    - High volume on breakout (>1.5x average)
    - Wide spread up bar
    - Occurs in Phase D

    TODO (Story 22.7b): Migrate from phase_detector_v2.py
    """

    def detect(self, ohlcv: pd.DataFrame) -> list[PhaseEvent]:
        """
        Detect Sign of Strength events in OHLCV data.

        Args:
            ohlcv: DataFrame with OHLCV data

        Returns:
            List of detected SOS events

        Raises:
            ValueError: If DataFrame is missing required columns
            NotImplementedError: Implementation pending Story 22.7b
        """
        if not self._validate_dataframe(ohlcv):
            raise ValueError("Invalid DataFrame: missing required columns")
        raise NotImplementedError("Implementation pending Story 22.7b")


class LastPointOfSupportDetector(BaseEventDetector):
    """
    Detects Last Point of Support (LPS) events.

    LPS is characterized by:
    - Pullback after SOS
    - Tests broken resistance as new support
    - Lower volume than SOS
    - Occurs in Phase D/E

    TODO (Story 22.7b): Migrate from phase_detector_v2.py
    """

    def detect(self, ohlcv: pd.DataFrame) -> list[PhaseEvent]:
        """
        Detect Last Point of Support events in OHLCV data.

        Args:
            ohlcv: DataFrame with OHLCV data

        Returns:
            List of detected LPS events

        Raises:
            ValueError: If DataFrame is missing required columns
            NotImplementedError: Implementation pending Story 22.7b
        """
        if not self._validate_dataframe(ohlcv):
            raise ValueError("Invalid DataFrame: missing required columns")
        raise NotImplementedError("Implementation pending Story 22.7b")
