"""
Unified Breakout Signal Generator for SOS and LPS entries.

Purpose:
--------
Consolidates the duplicate signal generation logic for SOS (Sign of Strength)
direct entries and LPS (Last Point of Support) pullback entries into a single
parameterized class.

This refactoring:
- Reduces ~391 lines of duplicate code to ~180 lines
- Ensures bug fixes apply to both signal types
- Makes code easier to maintain and test

Story: 18.4 - Merge Duplicate LPS/SOS Signal Generators

Usage:
------
>>> from src.signal_generator.breakout_signal_generator import BreakoutSignalGenerator
>>>
>>> generator = BreakoutSignalGenerator()
>>>
>>> # Generate LPS signal (preferred - tighter stop)
>>> lps_signal = generator.generate_signal(
>>>     entry_type="LPS",
>>>     sos=sos_breakout,
>>>     trading_range=range,
>>>     confidence=85,
>>>     lps=lps_pattern,  # Required for LPS
>>>     campaign_id=spring_campaign_id,
>>> )
>>>
>>> # Generate SOS direct signal (if no LPS forms)
>>> sos_signal = generator.generate_signal(
>>>     entry_type="SOS",
>>>     sos=sos_breakout,
>>>     trading_range=range,
>>>     confidence=80,
>>> )
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, Optional
from uuid import UUID

import structlog

from src.models.sos_signal import SOSSignal

# Import ForexPositionSize to resolve forward reference in SOSSignal
# This must happen at runtime (not under TYPE_CHECKING) for Pydantic
from src.risk_management.forex_position_sizer import ForexPositionSize  # noqa: F401

# Rebuild SOSSignal model to resolve the ForexPositionSize forward reference
SOSSignal.model_rebuild()

if TYPE_CHECKING:
    from src.models.lps import LPS
    from src.models.sos_breakout import SOSBreakout
    from src.models.trading_range import TradingRange

logger = structlog.get_logger(__name__)

# Constants for entry/stop calculations (FR17, FR19)
MIN_R_MULTIPLE = Decimal("2.0")  # FR19: Minimum R for all signals
LPS_ENTRY_BUFFER_PCT = Decimal("0.01")  # 1% above Ice for LPS entry slippage
LPS_STOP_DISTANCE_PCT = Decimal("0.03")  # 3% below Ice (tighter stop)
SOS_STOP_DISTANCE_PCT = Decimal("0.05")  # 5% below Ice (wider stop)


class BreakoutSignalGenerator:
    """
    Unified generator for SOS and LPS breakout signals.

    Consolidates duplicate logic from generate_lps_signal() and
    generate_sos_direct_signal() into a single parameterized class.

    Entry Types:
    -----------
    - LPS: Pullback to Ice after SOS breakout (tighter 3% stop, better R-multiple)
    - SOS: Direct entry on SOS breakout (wider 5% stop, used when no LPS forms)
    """

    def generate_signal(
        self,
        entry_type: Literal["LPS", "SOS"],
        sos: SOSBreakout,
        trading_range: TradingRange,
        confidence: int,
        lps: Optional[LPS] = None,
        campaign_id: Optional[UUID] = None,
    ) -> Optional[SOSSignal]:
        """
        Generate breakout signal for LPS or SOS entry.

        Args:
            entry_type: "LPS" for pullback entry or "SOS" for direct breakout entry
            sos: The SOS breakout pattern
            trading_range: Trading range with Ice and Jump levels
            confidence: Pattern confidence score (0-100)
            lps: LPS pattern (required if entry_type is "LPS")
            campaign_id: Optional campaign linkage (Spring→SOS progression)

        Returns:
            SOSSignal if valid, None if validation fails

        Raises:
            ValueError: If Ice or Jump level missing, or LPS required but not provided
        """
        # Validate entry type and required parameters
        if entry_type == "LPS" and lps is None:
            raise ValueError("LPS pattern required for LPS entry type")

        # Check tradeable status
        pattern_to_check = lps if entry_type == "LPS" else sos
        if not self._check_tradeable(entry_type, pattern_to_check, confidence):
            return None

        # Validate Ice and Jump levels exist
        self._validate_levels(entry_type, trading_range)
        ice_level = trading_range.ice.price
        jump_level = trading_range.jump.price

        # Calculate entry, stop, and target
        entry_price = self._calculate_entry(entry_type, ice_level, sos)
        stop_loss = self._calculate_stop(entry_type, ice_level)
        target = jump_level

        self._log_level_calculations(entry_type, ice_level, entry_price, stop_loss, target)

        # Calculate and validate R-multiple
        r_multiple = self._calculate_r_multiple(entry_type, entry_price, stop_loss, target)
        if r_multiple is None:
            return None

        if not self._validate_r_multiple(entry_type, r_multiple):
            return None

        # Build pattern data
        pattern_data = self._build_pattern_data(entry_type, sos, lps)

        # Create signal
        signal = self._create_signal(
            entry_type=entry_type,
            sos=sos,
            lps=lps,
            trading_range=trading_range,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target,
            confidence=confidence,
            r_multiple=r_multiple,
            pattern_data=pattern_data,
            ice_level=ice_level,
            jump_level=jump_level,
            campaign_id=campaign_id,
        )

        self._log_signal_generated(entry_type, signal, campaign_id)
        return signal

    def _check_tradeable(
        self,
        entry_type: str,
        pattern: LPS | SOSBreakout,
        confidence: int,
    ) -> bool:
        """Check if pattern is tradeable based on session filters."""
        if not pattern.is_tradeable or pattern.rejected_by_session_filter:
            log_event = f"{entry_type.lower()}_signal_rejected_not_tradeable"
            logger.warning(
                log_event,
                confidence=confidence,
                session=pattern.session_quality.value,
                session_penalty=pattern.session_confidence_penalty,
                rejected_by_session_filter=pattern.rejected_by_session_filter,
                message=(
                    "Pattern not tradeable - "
                    f"{'rejected by session filter' if pattern.rejected_by_session_filter else 'low confidence'}"
                ),
            )
            return False
        return True

    def _validate_levels(self, entry_type: str, trading_range: TradingRange) -> None:
        """Validate Ice and Jump levels exist."""
        if trading_range.ice is None or trading_range.ice.price is None:
            log_event = f"{entry_type.lower()}_signal_ice_missing"
            logger.error(
                log_event,
                trading_range_id=str(trading_range.id),
                message=f"Ice level required for {entry_type} signal generation",
            )
            raise ValueError(f"Ice level required for {entry_type} signal generation")

        if trading_range.jump is None or trading_range.jump.price is None:
            log_event = f"{entry_type.lower()}_signal_jump_missing"
            logger.error(
                log_event,
                trading_range_id=str(trading_range.id),
                message=f"Jump level required for {entry_type} signal generation",
            )
            raise ValueError(f"Jump level required for {entry_type} signal generation")

    def _calculate_entry(
        self,
        entry_type: str,
        ice_level: Decimal,
        sos: SOSBreakout,
    ) -> Decimal:
        """Calculate entry price based on entry type."""
        if entry_type == "LPS":
            # LPS entry: Ice + 1% buffer for slippage
            return ice_level * (Decimal("1") + LPS_ENTRY_BUFFER_PCT)
        else:
            # SOS direct entry: breakout price
            return sos.breakout_price

    def _calculate_stop(self, entry_type: str, ice_level: Decimal) -> Decimal:
        """Calculate stop loss based on entry type."""
        if entry_type == "LPS":
            # LPS: 3% below Ice (tighter stop)
            return ice_level * (Decimal("1") - LPS_STOP_DISTANCE_PCT)
        else:
            # SOS: 5% below Ice (wider stop for no pullback confirmation)
            return ice_level * (Decimal("1") - SOS_STOP_DISTANCE_PCT)

    def _log_level_calculations(
        self,
        entry_type: str,
        ice_level: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        target: Decimal,
    ) -> None:
        """Log the calculated levels."""
        prefix = entry_type.lower()
        stop_pct = LPS_STOP_DISTANCE_PCT if entry_type == "LPS" else SOS_STOP_DISTANCE_PCT

        if entry_type == "LPS":
            logger.debug(
                f"{prefix}_entry_calculated",
                ice_level=float(ice_level),
                entry_price=float(entry_price),
                buffer_pct=float(LPS_ENTRY_BUFFER_PCT * 100),
                message=f"LPS entry set at Ice + {LPS_ENTRY_BUFFER_PCT*100}% for entry slippage",
            )
        else:
            logger.debug(
                f"{prefix}_direct_entry_calculated",
                breakout_price=float(entry_price),
                entry_price=float(entry_price),
                message="SOS direct entry at breakout price (close of SOS bar)",
            )

        logger.debug(
            f"{prefix}_stop_calculated",
            ice_level=float(ice_level),
            stop_loss=float(stop_loss),
            stop_distance_pct=float(stop_pct * 100),
            message=f"{entry_type} stop {stop_pct*100}% below Ice (FR17 - structural stop)",
        )

        if entry_type == "LPS":
            logger.debug(
                f"{prefix}_target_calculated",
                jump_level=float(target),
                target=float(target),
                message="LPS target set to Jump level (Wyckoff cause-effect)",
            )

    def _calculate_r_multiple(
        self,
        entry_type: str,
        entry_price: Decimal,
        stop_loss: Decimal,
        target: Decimal,
    ) -> Optional[Decimal]:
        """Calculate R-multiple and validate risk is positive."""
        risk = entry_price - stop_loss
        reward = target - entry_price

        if risk <= 0:
            prefix = entry_type.lower()
            logger.error(
                f"{prefix}_invalid_risk",
                entry=float(entry_price),
                stop=float(stop_loss),
                message=f"Invalid {entry_type}: stop >= entry (risk <= 0)",
            )
            return None

        r_multiple = (reward / risk).quantize(Decimal("0.0001"))

        logger.info(
            f"{entry_type.lower()}_r_multiple_calculated",
            entry=float(entry_price),
            stop=float(stop_loss),
            target=float(target),
            risk=float(risk),
            reward=float(reward),
            r_multiple=float(r_multiple),
            message=f"{entry_type} R-multiple: {r_multiple:.2f}R",
        )

        return r_multiple

    def _validate_r_multiple(self, entry_type: str, r_multiple: Decimal) -> bool:
        """Validate R-multiple meets minimum requirement."""
        if r_multiple < MIN_R_MULTIPLE:
            prefix = entry_type.lower()
            logger.warning(
                f"{prefix}_insufficient_r_multiple",
                r_multiple=float(r_multiple),
                minimum_required=float(MIN_R_MULTIPLE),
                message=f"{entry_type} signal rejected: R-multiple {r_multiple:.2f}R < 2.0R minimum (FR19)",
            )
            return False
        return True

    def _build_pattern_data(
        self,
        entry_type: str,
        sos: SOSBreakout,
        lps: Optional[LPS],
    ) -> dict:
        """Build pattern data dictionary for signal metadata."""
        sos_data = {
            "bar_timestamp": sos.bar.timestamp.isoformat(),
            "breakout_price": str(sos.breakout_price),
            "breakout_pct": str(sos.breakout_pct),
            "volume_ratio": str(sos.volume_ratio),
            "spread_ratio": str(sos.spread_ratio),
            "close_position": str(sos.close_position),
        }

        if entry_type == "LPS":
            return {
                "sos": sos_data,
                "lps": {
                    "bar_timestamp": lps.bar.timestamp.isoformat(),
                    "pullback_low": str(lps.pullback_low),
                    "distance_from_ice": str(lps.distance_from_ice),
                    "volume_ratio": str(lps.volume_ratio),
                    "held_support": lps.held_support,
                    "bounce_confirmed": lps.bounce_confirmed,
                    "bars_after_sos": lps.bars_after_sos,
                },
                "entry_type": "LPS_ENTRY",
                "entry_rationale": "Pullback to Ice (old resistance, now support) after SOS breakout",
            }
        else:
            return {
                "sos": sos_data,
                "entry_type": "SOS_DIRECT_ENTRY",
                "entry_rationale": "Direct entry on SOS breakout (no LPS pullback within 10 bars)",
            }

    def _get_r_multiple_status(self, r_multiple: Decimal) -> tuple[str, Optional[str]]:
        """
        Determine R-multiple status and warning message.

        Story 7.6 thresholds:
        - IDEAL: >= 3.0R (no warning)
        - ACCEPTABLE: >= 2.0R and < 3.0R (warning)
        - REJECTED: < 2.0R (should be filtered before this)

        Returns:
            Tuple of (status, warning_message)
        """
        if r_multiple >= Decimal("3.0"):
            return "IDEAL", None
        elif r_multiple >= MIN_R_MULTIPLE:
            return "ACCEPTABLE", f"R-multiple {r_multiple:.2f}R below ideal threshold of 3.0R"
        else:
            # This shouldn't happen as we filter earlier, but handle defensively
            return "REJECTED", f"R-multiple {r_multiple:.2f}R below minimum threshold of 2.0R"

    def _create_signal(
        self,
        entry_type: str,
        sos: SOSBreakout,
        lps: Optional[LPS],
        trading_range: TradingRange,
        entry_price: Decimal,
        stop_loss: Decimal,
        target: Decimal,
        confidence: int,
        r_multiple: Decimal,
        pattern_data: dict,
        ice_level: Decimal,
        jump_level: Decimal,
        campaign_id: Optional[UUID],
    ) -> SOSSignal:
        """Create the SOSSignal instance."""
        # Calculate R-multiple status (Story 7.6)
        r_multiple_status, r_multiple_warning = self._get_r_multiple_status(r_multiple)

        if entry_type == "LPS":
            return SOSSignal(
                symbol=lps.bar.symbol,
                entry_type="LPS_ENTRY",
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target,
                confidence=confidence,
                r_multiple=r_multiple,
                r_multiple_status=r_multiple_status,
                r_multiple_warning=r_multiple_warning,
                pattern_data=pattern_data,
                sos_bar_timestamp=sos.bar.timestamp,
                lps_bar_timestamp=lps.bar.timestamp,
                sos_volume_ratio=sos.volume_ratio,
                lps_volume_ratio=lps.volume_ratio,
                phase="D",
                campaign_id=campaign_id,
                trading_range_id=trading_range.id,
                ice_level=ice_level,
                jump_level=jump_level,
                generated_at=datetime.now(UTC),
                expires_at=None,
            )
        else:
            return SOSSignal(
                symbol=sos.bar.symbol,
                entry_type="SOS_DIRECT_ENTRY",
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target,
                confidence=confidence,
                r_multiple=r_multiple,
                r_multiple_status=r_multiple_status,
                r_multiple_warning=r_multiple_warning,
                pattern_data=pattern_data,
                sos_bar_timestamp=sos.bar.timestamp,
                lps_bar_timestamp=None,
                sos_volume_ratio=sos.volume_ratio,
                lps_volume_ratio=None,
                phase="D",
                campaign_id=campaign_id,
                trading_range_id=trading_range.id,
                ice_level=ice_level,
                jump_level=jump_level,
                generated_at=datetime.now(UTC),
                expires_at=None,
            )

    def _log_signal_generated(
        self,
        entry_type: str,
        signal: SOSSignal,
        campaign_id: Optional[UUID],
    ) -> None:
        """Log successful signal generation."""
        log_event = f"{entry_type.lower()}_signal_generated"
        logger.info(
            log_event,
            symbol=signal.symbol,
            entry_type=signal.entry_type,
            entry=float(signal.entry_price),
            stop=float(signal.stop_loss),
            target=float(signal.target),
            r_multiple=float(signal.r_multiple),
            confidence=signal.confidence,
            campaign_id=str(campaign_id) if campaign_id else None,
            message=f"{entry_type} signal generated: {signal.r_multiple:.2f}R, confidence {signal.confidence}%",
        )
