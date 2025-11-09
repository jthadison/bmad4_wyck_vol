"""
Risk Allocator Module - Pattern-Specific Risk Percentage Management

Purpose:
--------
Provides pattern-specific risk allocation based on structural stop loss
distances. Tighter stops (Spring, UTAD) risk less capital than wider
stops (SOS) to maintain consistent dollar risk per trade.

Risk Allocation Table (AC 1) - Wyckoff-Weighted:
--------------------------------------------------
- Spring: 0.5% (2% stop, ~70% success with Phase A-B)
- ST (Secondary Test): 0.5% (3% stop, ~65% success, validates Spring)
- LPS: 0.7% (3% stop, ~75% success - pullback confirmation)
- SOS: 0.8% (5% stop, ~55% success - false-breakout risk)
- UTAD: 0.5% (2% stop, ~70% success, distribution short)

Rationale (AC 2) - Wyckoff Success Probability + Stop Distance:
----------------------------------------------------------------
Combines structural stop distances WITH historical success rates to
optimize risk-adjusted returns. LPS gets HIGHER allocation than SOS
despite tighter stop because pullback confirmation increases win rate.

Example (100K account):
- Spring: 100K × 0.5% = $500 risk, 2% stop, 70% win = $350 expected value
- ST: 100K × 0.5% = $500 risk, 3% stop, 65% win = $325 expected value
- LPS: 100K × 0.7% = $700 risk, 3% stop, 75% win = $525 expected value (BEST)
- SOS: 100K × 0.8% = $800 risk, 5% stop, 55% win = $440 expected value
- UTAD: 100K × 0.5% = $500 risk, 2% stop, 70% win = $350 expected value

Key Insight: LPS has highest expected value due to confirmation strength.

FR16 Compliance (AC 10):
-------------------------
- Fixed-point arithmetic using Decimal type
- No floating point precision errors
- Exact percentage calculations

FR18 Compliance (AC 5):
-----------------------
- Per-trade maximum: 2.0%
- Validation on load and override
- User overrides constrained within limits

Configuration (AC 3):
---------------------
Loaded from YAML: backend/config/risk_allocation.yaml
Schema validation via Pydantic models

Usage:
------
>>> from backend.src.risk_management.risk_allocator import RiskAllocator
>>> from backend.src.models.risk_allocation import PatternType
>>> from decimal import Decimal
>>>
>>> allocator = RiskAllocator()
>>> spring_risk = allocator.get_pattern_risk_pct(PatternType.SPRING)
>>> print(f"Spring risk: {spring_risk}%")  # Output: 0.5%
>>>
>>> # Override risk for specific pattern
>>> allocator.set_pattern_risk_override(PatternType.SPRING, Decimal("0.7"))
>>> spring_risk_override = allocator.get_pattern_risk_pct(PatternType.SPRING)
>>> print(f"Spring risk (override): {spring_risk_override}%")  # Output: 0.7%

Integration:
------------
- Story 7.2: Position size calculation uses risk percentages
- Story 7.8: RiskManager integrates RiskAllocator
- FR16: Pattern-specific risk allocation
- FR18: Risk limits enforcement

Author: Story 7.1
"""

from decimal import Decimal
from pathlib import Path
from typing import Optional

import structlog
import yaml

from src.config import get_settings
from src.models.risk_allocation import PatternType, RiskAllocationConfig


def get_volume_risk_multiplier(volume_ratio: Decimal) -> Decimal:
    """
    Calculate volume-adjusted risk multiplier based on Wyckoff VSA principles.

    Purpose:
    --------
    Scales base risk allocation by volume quality to reflect Wyckoff principle:
    "Effort (volume) must validate Result (price movement)". Higher volume
    indicates stronger professional participation, justifying fuller risk allocation.

    Volume Tiers (Wyckoff Interpretation):
    --------------------------------------
    - ≥2.5x: Climactic volume (full institutional commitment) → 1.00x
    - ≥2.3x: Very strong volume (heavy participation) → 0.95x
    - ≥2.0x: Ideal professional volume (confirmed activity) → 0.90x
    - ≥1.7x: Acceptable institutional volume (standard) → 0.85x
    - ≥1.5x: Borderline volume (minimal participation) → 0.75x

    Integration:
    ------------
    - Aligns with Story 6.5 AC 2 non-linear volume scoring (consistency)
    - FR12 (Story 6.2) pre-filters <1.5x volume (validation before risk calc)
    - Applied AFTER base pattern risk percentage lookup (Story 7.1 AC 1)

    Example:
    --------
    >>> # LPS pattern with 2.3x volume (very strong)
    >>> base_risk = Decimal("0.7")  # LPS base allocation
    >>> volume_ratio = Decimal("2.3")
    >>> multiplier = get_volume_risk_multiplier(volume_ratio)  # 0.95
    >>> final_risk = base_risk * multiplier  # 0.665%

    Parameters:
    -----------
    volume_ratio : Decimal
        Volume expansion ratio (breakout_volume / avg_volume)
        Must be ≥1.5x (FR12 pre-validation)

    Returns:
    --------
    Decimal
        Risk multiplier (0.75 to 1.00)

    Raises:
    -------
    ValueError
        If volume_ratio <1.5x (indicates FR12 validation failure)

    Author: Story 7.1 AC 11 (Wyckoff team review enhancement)
    """
    logger = structlog.get_logger(__name__)

    # Volume tier thresholds (non-linear Wyckoff scaling)
    if volume_ratio >= Decimal("2.5"):
        multiplier = Decimal("1.00")  # Climactic
        tier = "climactic"
    elif volume_ratio >= Decimal("2.3"):
        multiplier = Decimal("0.95")  # Very strong
        tier = "very_strong"
    elif volume_ratio >= Decimal("2.0"):
        multiplier = Decimal("0.90")  # Ideal professional (inflection point)
        tier = "ideal_professional"
    elif volume_ratio >= Decimal("1.7"):
        multiplier = Decimal("0.85")  # Acceptable institutional
        tier = "acceptable"
    elif volume_ratio >= Decimal("1.5"):
        multiplier = Decimal("0.75")  # Borderline
        tier = "borderline"
    else:
        # Should never reach here (FR12 rejects <1.5x in Story 6.2)
        raise ValueError(
            f"Volume ratio {volume_ratio}x < 1.5x threshold. "
            f"This indicates FR12 validation failure (Story 6.2). "
            f"Risk calculation should not proceed on rejected patterns."
        )

    logger.debug(
        "volume_risk_multiplier_calculated",
        volume_ratio=float(volume_ratio),
        multiplier=float(multiplier),
        tier=tier,
        message=f"Volume tier '{tier}' ({volume_ratio}x) → {multiplier}x multiplier",
    )

    return multiplier


class RiskAllocator:
    """
    Risk allocation service for pattern-specific position sizing.

    Purpose:
    --------
    Provides risk percentage lookup for each pattern type based on
    structural stop distances. Loads configuration from YAML and
    validates user overrides against FR18 limits.

    Usage:
    ------
    >>> allocator = RiskAllocator()
    >>> risk_pct = allocator.get_pattern_risk_pct(PatternType.SPRING)
    >>> print(f"Spring risk: {risk_pct}%")  # Output: 0.5%

    Author: Story 7.1
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize RiskAllocator with configuration file.

        Parameters:
        -----------
        config_path : Optional[str]
            Path to risk_allocation.yaml (defaults to backend/config/risk_allocation.yaml)

        Raises:
        -------
        FileNotFoundError
            If configuration file not found
        ValueError
            If configuration validation fails
        """
        self.logger = structlog.get_logger(__name__)

        if config_path is None:
            settings = get_settings()
            config_path = settings.risk_allocation_config_path

        self.config_path = Path(config_path)
        self.config = self._load_config()

        # AC 6: User overrides (optional)
        self._overrides: dict[PatternType, Decimal] = {}

        self.logger.info(
            "risk_allocator_initialized",
            config_version=self.config.version,
            per_trade_maximum=float(self.config.per_trade_maximum),
            patterns=list(self.config.pattern_risk_percentages.keys()),
            message="RiskAllocator initialized with configuration",
        )

    def _load_config(self) -> RiskAllocationConfig:
        """
        Load and validate risk allocation configuration from YAML.

        AC 3: Configuration loaded from YAML
        AC 5: Validation enforced during load
        AC 10: Decimal type for fixed-point arithmetic

        Returns:
        --------
        RiskAllocationConfig
            Validated configuration object

        Raises:
        -------
        FileNotFoundError
            If config file not found
        ValueError
            If configuration validation fails
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Risk allocation config not found: {self.config_path}")

        with open(self.config_path) as f:
            raw_config = yaml.safe_load(f)

        # Convert float percentages to Decimal for fixed-point arithmetic (AC 10)
        if "risk_allocation" in raw_config:
            config_data = raw_config["risk_allocation"]

            # Convert pattern_risk_percentages to Decimal
            if "pattern_risk_percentages" in config_data:
                config_data["pattern_risk_percentages"] = {
                    PatternType(k): Decimal(str(v))
                    for k, v in config_data["pattern_risk_percentages"].items()
                }

            # Convert per_trade_maximum to Decimal
            if "per_trade_maximum" in config_data:
                config_data["per_trade_maximum"] = Decimal(str(config_data["per_trade_maximum"]))

            # Convert override_constraints to Decimal
            if "override_constraints" in config_data:
                config_data["override_constraints"] = {
                    k: Decimal(str(v)) for k, v in config_data["override_constraints"].items()
                }

            # Pydantic validation (AC 5)
            return RiskAllocationConfig(**config_data)
        else:
            raise ValueError("Invalid config structure: missing 'risk_allocation' key")

    def get_pattern_risk_pct(self, pattern_type: PatternType, use_override: bool = True) -> Decimal:
        """
        Get risk percentage for a pattern type.

        AC 4: Primary function for risk percentage lookup
        AC 6: Support user overrides
        AC 9: Log when non-default risk used
        AC 10: Return Decimal for fixed-point arithmetic

        Parameters:
        -----------
        pattern_type : PatternType
            Pattern type (SPRING, UTAD, LPS, SOS)
        use_override : bool
            Whether to use user override if set (default True)

        Returns:
        --------
        Decimal
            Risk percentage (e.g., Decimal("0.5") for 0.5%)

        Example:
        --------
        >>> allocator = RiskAllocator()
        >>> spring_risk = allocator.get_pattern_risk_pct(PatternType.SPRING)
        >>> print(spring_risk)  # Decimal("0.5")

        Author: Story 7.1
        """
        # Check for user override (AC 6)
        if use_override and pattern_type in self._overrides:
            override_risk = self._overrides[pattern_type]

            # AC 9: Log when non-default risk used
            self.logger.info(
                "non_default_risk_used",
                pattern_type=pattern_type.value,
                default_risk=float(self.config.pattern_risk_percentages[pattern_type]),
                override_risk=float(override_risk),
                message=f"Using overridden risk for {pattern_type.value}: {override_risk}%",
            )

            return override_risk

        # Return default risk from configuration (AC 1)
        default_risk = self.config.pattern_risk_percentages[pattern_type]

        self.logger.debug(
            "default_risk_used",
            pattern_type=pattern_type.value,
            risk_pct=float(default_risk),
            message=f"Using default risk for {pattern_type.value}: {default_risk}%",
        )

        return default_risk

    def set_pattern_risk_override(self, pattern_type: PatternType, risk_pct: Decimal) -> None:
        """
        Set user override for pattern risk percentage.

        AC 6: Allow user to adjust pattern risk within limits
        AC 5: Validate override ≤ 2.0% (per-trade maximum)
        AC 10: Use Decimal for fixed-point arithmetic

        Parameters:
        -----------
        pattern_type : PatternType
            Pattern type to override
        risk_pct : Decimal
            Override risk percentage (must be within constraints)

        Raises:
        -------
        ValueError
            If override violates constraints (FR18 limits)

        Example:
        --------
        >>> allocator = RiskAllocator()
        >>> allocator.set_pattern_risk_override(PatternType.SPRING, Decimal("0.7"))

        Author: Story 7.1
        """
        if not self.config.override_allowed:
            raise ValueError("Risk overrides are disabled in configuration")

        # AC 5: Validate override within constraints
        min_risk = self.config.override_constraints["minimum_risk_pct"]
        max_risk = self.config.override_constraints["maximum_risk_pct"]

        if risk_pct < min_risk:
            raise ValueError(f"Override risk {risk_pct}% < minimum {min_risk}%")

        if risk_pct > max_risk:
            raise ValueError(f"Override risk {risk_pct}% > maximum {max_risk}% (FR18 violation)")

        # Set override
        self._overrides[pattern_type] = risk_pct

        self.logger.info(
            "risk_override_set",
            pattern_type=pattern_type.value,
            default_risk=float(self.config.pattern_risk_percentages[pattern_type]),
            override_risk=float(risk_pct),
            message=f"Risk override set for {pattern_type.value}: {risk_pct}%",
        )

    def clear_pattern_risk_override(self, pattern_type: PatternType) -> None:
        """
        Clear user override for pattern risk percentage.

        AC 6: Allow removal of overrides

        Parameters:
        -----------
        pattern_type : PatternType
            Pattern type to clear override for

        Author: Story 7.1
        """
        if pattern_type in self._overrides:
            del self._overrides[pattern_type]

            self.logger.info(
                "risk_override_cleared",
                pattern_type=pattern_type.value,
                message=f"Risk override cleared for {pattern_type.value}",
            )

    def get_all_risk_percentages(self) -> dict[PatternType, Decimal]:
        """
        Get all pattern risk percentages (with overrides applied).

        Returns:
        --------
        Dict[PatternType, Decimal]
            Risk percentage for each pattern type

        Author: Story 7.1
        """
        result = {}
        for pattern_type in PatternType:
            result[pattern_type] = self.get_pattern_risk_pct(pattern_type)
        return result

    def get_adjusted_pattern_risk(
        self,
        pattern_type: PatternType,
        volume_ratio: Decimal,
        use_override: bool = True,
    ) -> Decimal:
        """
        Get pattern risk percentage with volume adjustment applied.

        AC 11: Volume-adjusted risk scaling

        Parameters:
        -----------
        pattern_type : PatternType
            Pattern type (SPRING, LPS, SOS, etc.)
        volume_ratio : Decimal
            Volume expansion ratio for the pattern
        use_override : bool
            Whether to use user overrides (default True)

        Returns:
        --------
        Decimal
            Adjusted risk percentage (base_risk × volume_multiplier)

        Example:
        --------
        >>> allocator = RiskAllocator()
        >>> # LPS with 2.4x volume
        >>> adjusted_risk = allocator.get_adjusted_pattern_risk(
        >>>     pattern_type=PatternType.LPS,
        >>>     volume_ratio=Decimal("2.4")
        >>> )
        >>> # Base: 0.7%, Multiplier: 0.95, Result: 0.665%

        Author: Story 7.1 AC 11
        """
        # Get base risk percentage (AC 1, AC 4)
        base_risk = self.get_pattern_risk_pct(pattern_type, use_override)

        # Calculate volume multiplier (AC 11)
        volume_multiplier = get_volume_risk_multiplier(volume_ratio)

        # Apply volume adjustment
        adjusted_risk = base_risk * volume_multiplier

        self.logger.debug(
            "volume_adjusted_risk_calculated",
            pattern_type=pattern_type.value,
            base_risk_pct=float(base_risk),
            volume_ratio=float(volume_ratio),
            volume_multiplier=float(volume_multiplier),
            adjusted_risk_pct=float(adjusted_risk),
            message=f"Volume-adjusted risk: {base_risk}% × {volume_multiplier} = {adjusted_risk}%",
        )

        return adjusted_risk
