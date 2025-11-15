"""
Abstract base class for asset-class-specific confidence scoring.

This module provides the ConfidenceScorer abstract base class that defines the
interface for all asset-class-specific confidence scoring implementations.

Wyckoff Principle: Adapt Methodology to Market Conditions
-----------------------------------------------------------
The Wyckoff methodology's core principles remain constant across all markets:
- Supply and Demand dynamics (First Law: Price/Volume)
- Phases of accumulation and distribution
- Composite Operator behavior patterns

However, the CONFIRMATION METHODS must adapt based on asset-class characteristics,
particularly volume data reliability.

Volume Reliability by Asset Class
----------------------------------
Different asset classes provide different quality of volume data:

| Asset Class | Volume Type              | Reliability  | Wyckoff Analysis Impact    |
|-------------|--------------------------|--------------|----------------------------|
| Stocks      | Real shares traded       | HIGH         | Full volume analysis       |
| Forex       | Tick volume (price chgs) | LOW          | Price structure primary    |
| Futures     | Real contracts traded    | HIGH         | Full volume analysis       |
| Crypto      | Real coins/tokens traded | MEDIUM-HIGH  | Volume analysis w/ caveats |

Volume Reliability Impact on Confidence Scoring
------------------------------------------------
- HIGH reliability (stocks, futures):
  * Volume weight: 35-40 points (primary confirmation)
  * Max confidence: 100
  * Volume confirms institutional participation
  * Example: 2.0x volume = institutional accumulation confirmed

- MEDIUM reliability (crypto):
  * Volume weight: 20-30 points (secondary confirmation)
  * Max confidence: 90-95
  * Volume analysis applicable with exchange volume caveats
  * Example: 2.0x volume = likely institutional, verify exchange

- LOW reliability (forex):
  * Volume weight: 5-10 points (pattern consistency only)
  * Max confidence: 85
  * Price structure becomes primary confirmation
  * Example: 2.0x tick volume = increased activity (NOT institutional proof)

Wyckoff Team Insight (Richard Wyckoff Analyst)
-----------------------------------------------
"This abstract base class embodies Wyckoff's principle: 'Adapt methodology to
market conditions.' The PRINCIPLES remain (supply/demand, phases, accumulation),
but CONFIRMATION methods must adapt. Stock volume confirms institutional activity.
Forex tick volume cannot. The interface acknowledges this reality."

Examples by Asset Class
------------------------

Stock Example (HIGH volume reliability):
    >>> scorer = StockConfidenceScorer()
    >>> confidence = scorer.calculate_spring_confidence(
    ...     spring=spring,  # 2.5x volume climactic spring
    ...     creek=creek_level,
    ...     previous_tests=[test1, test2]
    ... )
    >>> # Volume weight: 40 points (2.5x volume = maximum score)
    >>> # Total confidence: 95 (volume fully confirms pattern)

Forex Example (LOW volume reliability):
    >>> scorer = ForexConfidenceScorer()
    >>> confidence = scorer.calculate_spring_confidence(
    ...     spring=spring,  # 2.5x tick volume spring
    ...     creek=creek_level,
    ...     previous_tests=[test1, test2]
    ... )
    >>> # Volume weight: 7 points (tick volume = pattern consistency only)
    >>> # Total confidence: 78 (capped at 85, volume discount applied)
    >>> # Price structure (penetration/recovery) becomes primary confirmation

Implementation Checklist
-------------------------
When implementing a concrete ConfidenceScorer:

1. Set asset_class property ("stock", "forex", "futures", "crypto")
2. Set volume_reliability ("HIGH", "MEDIUM", "LOW")
3. Set max_confidence (100 for HIGH, 90-95 for MEDIUM, 85 for LOW)
4. Implement calculate_spring_confidence() with volume weighting
5. Implement calculate_sos_confidence() with volume weighting
6. Apply confidence cap in final score calculation
7. Document volume weight rationale in docstrings

Author: Story 0.1 - Asset-Class Base Interfaces
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.models.creek_level import CreekLevel
from src.models.lps import LPS
from src.models.phase_classification import PhaseClassification
from src.models.sos_breakout import SOSBreakout
from src.models.spring import Spring
from src.models.spring_confidence import SpringConfidence
from src.models.test import Test
from src.models.trading_range import TradingRange

# Valid enumeration values for validation
VALID_ASSET_CLASSES = ["stock", "forex", "futures", "crypto"]
VALID_RELIABILITY = ["HIGH", "MEDIUM", "LOW"]


class ConfidenceScorer(ABC):
    """
    Abstract base class for asset-class-specific confidence scoring.

    This base class defines the interface that all asset-class-specific
    confidence scorers must implement. It ensures consistent scoring
    behavior while allowing adaptation to volume data quality differences.

    Wyckoff Methodology Adaptation
    -------------------------------
    The Wyckoff methodology applies universally, but volume confirmation
    methods must adapt to data quality:

    - Stock volume = institutional participation (direct evidence)
    - Forex tick volume = activity level (indirect evidence)

    Confidence scoring must reflect this difference to prevent false
    signals when using forex tick volume data.

    Attributes:
        asset_class: Asset class identifier ("stock", "forex", "futures", "crypto")
        volume_reliability: Volume data quality ("HIGH", "MEDIUM", "LOW")
        max_confidence: Maximum achievable confidence score (1-100)

    Abstract Methods:
        calculate_spring_confidence: Score spring pattern with asset-class awareness
        calculate_sos_confidence: Score SOS/LPS pattern with asset-class awareness

    Validation:
        - asset_class must be one of: "stock", "forex", "futures", "crypto"
        - volume_reliability must be one of: "HIGH", "MEDIUM", "LOW"
        - max_confidence must be 1-100 (typically 85-100)

    Usage:
        This is an abstract base class and cannot be instantiated directly.
        Create concrete implementations like StockConfidenceScorer or
        ForexConfidenceScorer that implement all abstract methods.

    Example:
        >>> # INCORRECT - Cannot instantiate abstract class
        >>> scorer = ConfidenceScorer(
        ...     asset_class="stock",
        ...     volume_reliability="HIGH",
        ...     max_confidence=100
        ... )
        TypeError: Can't instantiate abstract class ConfidenceScorer

        >>> # CORRECT - Use concrete implementation
        >>> from src.pattern_engine.scorers.stock_scorer import StockConfidenceScorer
        >>> scorer = StockConfidenceScorer()
        >>> confidence = scorer.calculate_spring_confidence(spring, creek)
        95

    See Also:
        - StockConfidenceScorer: Implementation for stock markets (HIGH reliability)
        - ForexConfidenceScorer: Implementation for forex markets (LOW reliability)
        - Story 0.2: Stock scorer refactor
        - Story 0.3: Forex scorer implementation
    """

    def __init__(
        self,
        asset_class: str,
        volume_reliability: str,
        max_confidence: int,
    ) -> None:
        """
        Initialize the confidence scorer with asset-class properties.

        Args:
            asset_class: Asset class identifier
                Must be one of: "stock", "forex", "futures", "crypto"
            volume_reliability: Volume data quality level
                Must be one of: "HIGH", "MEDIUM", "LOW"
            max_confidence: Maximum achievable confidence score
                Must be 1-100 (typically 85 for LOW, 90-95 for MEDIUM, 100 for HIGH)

        Raises:
            ValueError: If asset_class is not in VALID_ASSET_CLASSES
            ValueError: If volume_reliability is not in VALID_RELIABILITY
            ValueError: If max_confidence is not in range 1-100

        Example:
            >>> # In concrete implementation
            >>> class StockConfidenceScorer(ConfidenceScorer):
            ...     def __init__(self):
            ...         super().__init__(
            ...             asset_class="stock",
            ...             volume_reliability="HIGH",
            ...             max_confidence=100
            ...         )
        """
        # Validate asset_class
        if asset_class not in VALID_ASSET_CLASSES:
            raise ValueError(
                f"Invalid asset_class: {asset_class}. " f"Must be one of: {VALID_ASSET_CLASSES}"
            )

        # Validate volume_reliability
        if volume_reliability not in VALID_RELIABILITY:
            raise ValueError(
                f"Invalid volume_reliability: {volume_reliability}. "
                f"Must be one of: {VALID_RELIABILITY}"
            )

        # Validate max_confidence range
        if not 1 <= max_confidence <= 100:
            raise ValueError(
                f"Invalid max_confidence: {max_confidence}. " f"Must be between 1 and 100"
            )

        # Set properties after validation
        self.asset_class = asset_class
        self.volume_reliability = volume_reliability
        self.max_confidence = max_confidence

    @abstractmethod
    def calculate_spring_confidence(
        self,
        spring: Spring,
        creek: CreekLevel,
        previous_tests: list[Test] | None = None,
    ) -> SpringConfidence:
        """
        Calculate confidence score for a spring pattern.

        This method must be implemented by concrete subclasses to provide
        asset-class-specific spring confidence scoring.

        Volume Weighting by Asset Class:
            - Stock (HIGH reliability): 40 points for volume component
            - Forex (LOW reliability): 5-10 points for volume component
            - Futures (HIGH reliability): 40 points for volume component
            - Crypto (MEDIUM reliability): 20-30 points for volume component

        Args:
            spring: Spring pattern to score
            creek: Creek level that spring penetrated below
            previous_tests: Optional list of prior test confirmations

        Returns:
            SpringConfidence with total_score, component_scores, and quality_tier

        Example (Stock Implementation):
            >>> # High-volume spring in stock market
            >>> confidence = scorer.calculate_spring_confidence(
            ...     spring=Spring(volume_ratio=Decimal("0.3"), ...),
            ...     creek=creek_level,
            ...     previous_tests=[test1]
            ... )
            >>> confidence.total_score  # 95 (volume heavily weighted)
            95
            >>> confidence.component_scores["volume"]  # 40 points
            40

        Example (Forex Implementation):
            >>> # High tick-volume spring in forex market
            >>> confidence = scorer.calculate_spring_confidence(
            ...     spring=Spring(volume_ratio=Decimal("0.3"), ...),
            ...     creek=creek_level,
            ...     previous_tests=[test1]
            ... )
            >>> confidence.total_score  # 78 (volume lightly weighted, capped at 85)
            78
            >>> confidence.component_scores["volume"]  # 7 points
            7

        See Also:
            - Story 5.4: Spring confidence scoring (stock implementation)
            - Story 0.2: Stock scorer refactor
            - Story 0.3: Forex scorer implementation
        """
        pass

    @abstractmethod
    def calculate_sos_confidence(
        self,
        sos: SOSBreakout,
        lps: Optional[LPS],
        range_: TradingRange,
        phase: PhaseClassification,
    ) -> int:
        """
        Calculate confidence score for SOS/LPS pattern.

        This method must be implemented by concrete subclasses to provide
        asset-class-specific SOS confidence scoring.

        Volume Weighting by Asset Class:
            - Stock (HIGH reliability): 35 points for volume component
            - Forex (LOW reliability): 5-10 points for volume component
            - Futures (HIGH reliability): 35 points for volume component
            - Crypto (MEDIUM reliability): 20-25 points for volume component

        Args:
            sos: SOS breakout pattern to score
            lps: Optional LPS pullback entry (None for SOS direct entry)
            range_: Trading range being broken out of
            phase: Current Wyckoff phase classification

        Returns:
            int: Confidence score (0-100, or 0-max_confidence for asset class)

        Example (Stock Implementation):
            >>> # High-volume SOS breakout in stock market
            >>> confidence = scorer.calculate_sos_confidence(
            ...     sos=SOSBreakout(volume_ratio=Decimal("2.0"), ...),
            ...     lps=None,
            ...     range_=trading_range,
            ...     phase=phase_d
            ... )
            >>> confidence  # 92 (volume heavily weighted)
            92

        Example (Forex Implementation):
            >>> # High tick-volume SOS breakout in forex market
            >>> confidence = scorer.calculate_sos_confidence(
            ...     sos=SOSBreakout(volume_ratio=Decimal("2.0"), ...),
            ...     lps=None,
            ...     range_=trading_range,
            ...     phase=phase_d
            ... )
            >>> confidence  # 75 (volume lightly weighted, capped at 85)
            75

        See Also:
            - Story 6.5: SOS/LPS confidence scoring (stock implementation)
            - Story 0.2: Stock scorer refactor
            - Story 0.3: Forex scorer implementation
        """
        pass

    def __repr__(self) -> str:
        """
        String representation of the confidence scorer.

        Returns:
            str: Human-readable representation with asset class info

        Example:
            >>> scorer = StockConfidenceScorer()
            >>> repr(scorer)
            'StockConfidenceScorer(asset_class=stock, reliability=HIGH, max_confidence=100)'
        """
        return (
            f"{self.__class__.__name__}("
            f"asset_class={self.asset_class}, "
            f"reliability={self.volume_reliability}, "
            f"max_confidence={self.max_confidence})"
        )
