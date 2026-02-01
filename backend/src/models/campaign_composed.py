"""
Composed Campaign Model - Story 22.10

Purpose:
--------
Provides a Campaign model using composition of focused sub-models for improved
Single Responsibility Principle compliance. Maintains full backward compatibility
with the original monolithic Campaign dataclass through property accessors.

This module enables gradual migration: existing code continues to work unchanged,
while new code can use the cleaner composed structure.

Classes:
--------
- ComposedCampaign: Campaign model using composition of sub-models

Usage:
------
# Old style (still works - backward compatible)
campaign = ComposedCampaign(
    campaign_id="abc123",
    symbol="AAPL",
    support_level=Decimal("145.00"),
    resistance_level=Decimal("160.00")
)

# New style (cleaner, uses sub-models)
campaign = ComposedCampaign.create(
    symbol="AAPL",
    support_level=Decimal("145.00"),
    resistance_level=Decimal("160.00")
)

# Access via sub-models
campaign.risk.support_level  # New way
campaign.support_level       # Old way (still works via property)

Author: Story 22.10 - Decompose Campaign Dataclass
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

from src.models.campaign_core import CampaignCore, CampaignState
from src.models.campaign_performance import (
    CampaignPerformanceMetrics,
    ExitReason,
)
from src.models.campaign_risk import CampaignRiskMetadata
from src.models.campaign_volume import (
    CampaignVolumeProfile,
    EffortVsResult,
    VolumeProfile,
)

# Validation cache configuration (Story 15.4)
VALIDATION_CACHE_MAX_ENTRIES = 100


@dataclass
class ComposedCampaign:
    """
    Campaign model using composition of focused sub-models.

    This model composes four focused sub-models:
    - core: CampaignCore - Identity and state
    - risk: CampaignRiskMetadata - Risk-related metadata
    - performance: CampaignPerformanceMetrics - Performance tracking
    - volume: CampaignVolumeProfile - Volume analysis

    All original Campaign fields are accessible via property accessors for
    full backward compatibility. New code should prefer accessing data through
    the sub-models for cleaner separation of concerns.

    Attributes:
        core: CampaignCore model for identity/state
        risk: CampaignRiskMetadata model for risk data
        performance: CampaignPerformanceMetrics model for P&L tracking
        volume: CampaignVolumeProfile model for volume analysis

        # Additional tracking not in sub-models
        phase_history: List of (timestamp, phase) tuples
        phase_transition_count: Number of phase transitions

        # Phase duration tracking (Story 13.6.3)
        phase_c_start_bar: Bar index when Phase C started
        phase_d_start_bar: Bar index when Phase D started
        phase_e_start_bar: Bar index when Phase E started

        # Correlation tracking (Story 16.1b)
        correlation_group: Correlation group identifier
        sector: Sector for equities

    Example:
        >>> from decimal import Decimal
        >>> campaign = ComposedCampaign.create(
        ...     symbol="AAPL",
        ...     support_level=Decimal("145.00"),
        ...     resistance_level=Decimal("160.00")
        ... )
        >>> campaign.core.symbol
        'AAPL'
        >>> campaign.risk.support_level
        Decimal('145.00')
        >>> campaign.symbol  # Backward compatible
        'AAPL'
    """

    # Composed sub-models
    core: CampaignCore = field(default_factory=CampaignCore)
    risk: CampaignRiskMetadata = field(default_factory=CampaignRiskMetadata)
    performance: CampaignPerformanceMetrics = field(default_factory=CampaignPerformanceMetrics)
    volume: CampaignVolumeProfile = field(default_factory=CampaignVolumeProfile)

    # Phase history tracking (not in sub-models, campaign-level concern)
    # Phase is stored as string for flexibility (e.g., "A", "B", "C", "D", "E")
    phase_history: list[tuple[datetime, str]] = field(default_factory=list)
    phase_transition_count: int = 0

    # Phase duration tracking (Story 13.6.3)
    phase_c_start_bar: Optional[int] = None
    phase_d_start_bar: Optional[int] = None
    phase_e_start_bar: Optional[int] = None

    # Correlation tracking (Story 16.1b)
    correlation_group: Optional[str] = None
    sector: Optional[str] = None

    # Validation cache (Story 15.4)
    _validation_cache: dict[str, dict[str, Any]] = field(
        default_factory=dict, repr=False, compare=False
    )
    _cache_ttl_seconds: int = 300

    # =========================================================================
    # Factory Methods
    # =========================================================================

    @classmethod
    def create(
        cls,
        symbol: str,
        support_level: Optional[Decimal] = None,
        resistance_level: Optional[Decimal] = None,
        *,
        campaign_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        timeframe: str = "1d",
        asset_class: str = "stock",
        risk_per_share: Optional[Decimal] = None,
        **kwargs: Any,
    ) -> "ComposedCampaign":
        """
        Factory method for creating campaigns with cleaner API.

        This method provides a convenient way to create campaigns without
        manually constructing all sub-models.

        Args:
            symbol: Trading symbol (required)
            support_level: Support level price
            resistance_level: Resistance level price
            campaign_id: Optional ID (auto-generated if not provided)
            start_time: Optional start time (defaults to now)
            timeframe: Chart timeframe (default "1d")
            asset_class: Asset class type (default "stock")
            risk_per_share: Risk per share amount
            **kwargs: Additional keyword arguments

        Returns:
            New ComposedCampaign instance

        Example:
            >>> campaign = ComposedCampaign.create(
            ...     symbol="AAPL",
            ...     support_level=Decimal("145.00"),
            ...     resistance_level=Decimal("160.00"),
            ...     timeframe="4h"
            ... )
        """
        # Create core model
        core = CampaignCore(
            campaign_id=campaign_id or str(uuid4()),
            symbol=symbol,
            start_time=start_time or datetime.now(UTC),
            timeframe=timeframe,
            asset_class=asset_class,
        )

        # Create risk model
        risk = CampaignRiskMetadata(
            support_level=support_level,
            resistance_level=resistance_level,
            risk_per_share=risk_per_share,
        )

        # Calculate range width if both levels provided
        if support_level and resistance_level:
            risk.range_width_pct = risk.calculate_range_width()

        # Create performance and volume models with defaults
        performance = CampaignPerformanceMetrics()
        volume = CampaignVolumeProfile()

        return cls(
            core=core,
            risk=risk,
            performance=performance,
            volume=volume,
            sector=kwargs.get("sector"),
            correlation_group=kwargs.get("correlation_group"),
        )

    # =========================================================================
    # Backward Compatibility Properties - Core
    # =========================================================================

    @property
    def campaign_id(self) -> str:
        """Campaign ID (backward compatible)."""
        return self.core.campaign_id

    @campaign_id.setter
    def campaign_id(self, value: str) -> None:
        self.core.campaign_id = value

    @property
    def symbol(self) -> str:
        """Symbol (backward compatible)."""
        return self.core.symbol

    @symbol.setter
    def symbol(self, value: str) -> None:
        self.core.symbol = value

    @property
    def start_time(self) -> datetime:
        """Start time (backward compatible)."""
        return self.core.start_time

    @start_time.setter
    def start_time(self, value: datetime) -> None:
        self.core.start_time = value

    @property
    def state(self) -> CampaignState:
        """Campaign state (backward compatible)."""
        return self.core.state

    @state.setter
    def state(self, value: CampaignState) -> None:
        self.core.state = value

    @property
    def current_phase(self) -> Optional[str]:
        """Current phase (backward compatible)."""
        return self.core.current_phase

    @current_phase.setter
    def current_phase(self, value: Optional[str]) -> None:
        self.core.current_phase = value

    @property
    def patterns(self) -> list[Any]:
        """Patterns list (backward compatible)."""
        return self.core.patterns

    @patterns.setter
    def patterns(self, value: list[Any]) -> None:
        self.core.patterns = value

    @property
    def failure_reason(self) -> Optional[str]:
        """Failure reason (backward compatible)."""
        return self.core.failure_reason

    @failure_reason.setter
    def failure_reason(self, value: Optional[str]) -> None:
        self.core.failure_reason = value

    @property
    def timeframe(self) -> str:
        """Timeframe (backward compatible)."""
        return self.core.timeframe

    @timeframe.setter
    def timeframe(self, value: str) -> None:
        self.core.timeframe = value

    # =========================================================================
    # Backward Compatibility Properties - Risk
    # =========================================================================

    @property
    def support_level(self) -> Optional[Decimal]:
        """Support level (backward compatible)."""
        return self.risk.support_level

    @support_level.setter
    def support_level(self, value: Optional[Decimal]) -> None:
        self.risk.support_level = value

    @property
    def resistance_level(self) -> Optional[Decimal]:
        """Resistance level (backward compatible)."""
        return self.risk.resistance_level

    @resistance_level.setter
    def resistance_level(self, value: Optional[Decimal]) -> None:
        self.risk.resistance_level = value

    @property
    def risk_per_share(self) -> Optional[Decimal]:
        """Risk per share (backward compatible)."""
        return self.risk.risk_per_share

    @risk_per_share.setter
    def risk_per_share(self, value: Optional[Decimal]) -> None:
        self.risk.risk_per_share = value

    @property
    def strength_score(self) -> float:
        """Strength score (backward compatible)."""
        return self.risk.strength_score

    @strength_score.setter
    def strength_score(self, value: float) -> None:
        self.risk.strength_score = value

    @property
    def range_width_pct(self) -> Optional[Decimal]:
        """Range width percentage (backward compatible)."""
        return self.risk.range_width_pct

    @range_width_pct.setter
    def range_width_pct(self, value: Optional[Decimal]) -> None:
        self.risk.range_width_pct = value

    @property
    def position_size(self) -> Decimal:
        """Position size (backward compatible)."""
        return self.risk.position_size

    @position_size.setter
    def position_size(self, value: Decimal) -> None:
        self.risk.position_size = value

    @property
    def dollar_risk(self) -> Decimal:
        """Dollar risk (backward compatible)."""
        return self.risk.dollar_risk

    @dollar_risk.setter
    def dollar_risk(self, value: Decimal) -> None:
        self.risk.dollar_risk = value

    @property
    def jump_level(self) -> Optional[Decimal]:
        """Jump level (backward compatible)."""
        return self.risk.jump_level

    @jump_level.setter
    def jump_level(self, value: Optional[Decimal]) -> None:
        self.risk.jump_level = value

    @property
    def original_ice_level(self) -> Optional[Decimal]:
        """Original ice level (backward compatible)."""
        return self.risk.original_ice_level

    @original_ice_level.setter
    def original_ice_level(self, value: Optional[Decimal]) -> None:
        self.risk.original_ice_level = value

    @property
    def original_jump_level(self) -> Optional[Decimal]:
        """Original jump level (backward compatible)."""
        return self.risk.original_jump_level

    @original_jump_level.setter
    def original_jump_level(self, value: Optional[Decimal]) -> None:
        self.risk.original_jump_level = value

    @property
    def ice_expansion_count(self) -> int:
        """Ice expansion count (backward compatible)."""
        return self.risk.ice_expansion_count

    @ice_expansion_count.setter
    def ice_expansion_count(self, value: int) -> None:
        self.risk.ice_expansion_count = value

    @property
    def last_ice_update_bar(self) -> Optional[int]:
        """Last ice update bar (backward compatible)."""
        return self.risk.last_ice_update_bar

    @last_ice_update_bar.setter
    def last_ice_update_bar(self, value: Optional[int]) -> None:
        self.risk.last_ice_update_bar = value

    @property
    def entry_atr(self) -> Optional[Decimal]:
        """Entry ATR (backward compatible)."""
        return self.risk.entry_atr

    @entry_atr.setter
    def entry_atr(self, value: Optional[Decimal]) -> None:
        self.risk.entry_atr = value

    @property
    def max_atr_seen(self) -> Optional[Decimal]:
        """Max ATR seen (backward compatible)."""
        return self.risk.max_atr_seen

    @max_atr_seen.setter
    def max_atr_seen(self, value: Optional[Decimal]) -> None:
        self.risk.max_atr_seen = value

    # =========================================================================
    # Backward Compatibility Properties - Performance
    # =========================================================================

    @property
    def r_multiple(self) -> Optional[Decimal]:
        """R-multiple (backward compatible)."""
        return self.performance.r_multiple

    @r_multiple.setter
    def r_multiple(self, value: Optional[Decimal]) -> None:
        self.performance.r_multiple = value

    @property
    def points_gained(self) -> Optional[Decimal]:
        """Points gained (backward compatible)."""
        return self.performance.points_gained

    @points_gained.setter
    def points_gained(self, value: Optional[Decimal]) -> None:
        self.performance.points_gained = value

    @property
    def exit_price(self) -> Optional[Decimal]:
        """Exit price (backward compatible)."""
        return self.performance.exit_price

    @exit_price.setter
    def exit_price(self, value: Optional[Decimal]) -> None:
        self.performance.exit_price = value

    @property
    def exit_timestamp(self) -> Optional[datetime]:
        """Exit timestamp (backward compatible)."""
        return self.performance.exit_timestamp

    @exit_timestamp.setter
    def exit_timestamp(self, value: Optional[datetime]) -> None:
        self.performance.exit_timestamp = value

    @property
    def exit_reason(self) -> ExitReason:
        """Exit reason (backward compatible)."""
        return self.performance.exit_reason

    @exit_reason.setter
    def exit_reason(self, value: ExitReason) -> None:
        self.performance.exit_reason = value

    @property
    def duration_bars(self) -> int:
        """Duration in bars (backward compatible)."""
        return self.performance.duration_bars

    @duration_bars.setter
    def duration_bars(self, value: int) -> None:
        self.performance.duration_bars = value

    @property
    def phase_e_progress_percent(self) -> Decimal:
        """Phase E progress percent (backward compatible)."""
        return self.performance.phase_e_progress_percent

    @phase_e_progress_percent.setter
    def phase_e_progress_percent(self, value: Decimal) -> None:
        self.performance.phase_e_progress_percent = value

    # =========================================================================
    # Backward Compatibility Properties - Volume
    # =========================================================================

    @property
    def volume_profile(self) -> VolumeProfile:
        """Volume profile (backward compatible)."""
        return self.volume.volume_profile

    @volume_profile.setter
    def volume_profile(self, value: VolumeProfile) -> None:
        self.volume.volume_profile = value

    @property
    def volume_trend_quality(self) -> float:
        """Volume trend quality (backward compatible)."""
        return self.volume.volume_trend_quality

    @volume_trend_quality.setter
    def volume_trend_quality(self, value: float) -> None:
        self.volume.volume_trend_quality = value

    @property
    def effort_vs_result(self) -> EffortVsResult:
        """Effort vs result (backward compatible)."""
        return self.volume.effort_vs_result

    @effort_vs_result.setter
    def effort_vs_result(self, value: EffortVsResult) -> None:
        self.volume.effort_vs_result = value

    @property
    def climax_detected(self) -> bool:
        """Climax detected (backward compatible)."""
        return self.volume.climax_detected

    @climax_detected.setter
    def climax_detected(self, value: bool) -> None:
        self.volume.climax_detected = value

    @property
    def absorption_quality(self) -> float:
        """Absorption quality (backward compatible)."""
        return self.volume.absorption_quality

    @absorption_quality.setter
    def absorption_quality(self, value: float) -> None:
        self.volume.absorption_quality = value

    @property
    def volume_history(self) -> list[Decimal]:
        """Volume history (backward compatible)."""
        return self.volume.volume_history

    @volume_history.setter
    def volume_history(self, value: list[Decimal]) -> None:
        self.volume.volume_history = value

    # =========================================================================
    # Methods (Backward Compatible)
    # =========================================================================

    def calculate_performance_metrics(self, exit_price: Decimal) -> None:
        """
        Calculate R-multiple, points gained, and duration (Story 15.1a).

        Delegates to performance sub-model after getting entry price from patterns.

        Args:
            exit_price: Campaign exit price
        """
        if not self.patterns:
            return

        # Entry from first pattern bar close
        entry_price = self.patterns[0].bar.close

        self.performance.finalize(
            exit_price=exit_price,
            entry_price=entry_price,
            risk_per_share=self.risk.risk_per_share,
            exit_reason=self.performance.exit_reason,
            exit_timestamp=datetime.now(UTC),
        )

        # Update duration
        if self.patterns:
            if hasattr(self.patterns[0], "bar_index") and hasattr(self.patterns[-1], "bar_index"):
                first_bar = self.patterns[0].bar_index
                last_bar = self.patterns[-1].bar_index
                self.performance.duration_bars = last_bar - first_bar + 1
            else:
                self.performance.duration_bars = len(self.patterns)

    def _get_pattern_sequence_hash(self) -> str:
        """Generate hash of pattern sequence for cache key."""
        pattern_parts = []
        for p in self.patterns:
            if isinstance(p.bar, dict):
                timestamp_str = p.bar["timestamp"]
            else:
                timestamp_str = p.bar.timestamp.isoformat()
            pattern_parts.append(f"{type(p).__name__}:{timestamp_str}")

        pattern_signature = "|".join(pattern_parts)
        return str(hash(pattern_signature))

    def get_cached_validation(self) -> Optional[bool]:
        """Get cached validation result if available and not expired."""
        cache_key = self._get_pattern_sequence_hash()

        if cache_key not in self._validation_cache:
            return None

        cache_entry = self._validation_cache[cache_key]
        cached_at = cache_entry["timestamp"]

        if datetime.now(UTC) - cached_at > timedelta(seconds=self._cache_ttl_seconds):
            del self._validation_cache[cache_key]
            return None

        return cache_entry["result"]

    def set_cached_validation(self, result: bool) -> None:
        """Cache validation result with LRU eviction."""
        cache_key = self._get_pattern_sequence_hash()

        self._validation_cache[cache_key] = {
            "result": result,
            "timestamp": datetime.now(UTC),
        }

        if len(self._validation_cache) > VALIDATION_CACHE_MAX_ENTRIES:
            oldest_key = min(
                self._validation_cache.keys(),
                key=lambda k: self._validation_cache[k]["timestamp"],
            )
            del self._validation_cache[oldest_key]

    def invalidate_validation_cache(self) -> None:
        """Clear validation cache."""
        self._validation_cache.clear()

    def is_terminal(self) -> bool:
        """Check if campaign is in a terminal state."""
        return self.core.is_terminal()

    def is_actionable(self) -> bool:
        """Check if campaign is actionable (ACTIVE state)."""
        return self.core.is_actionable()


# Export the composed model with the same name for easy migration
Campaign = ComposedCampaign
