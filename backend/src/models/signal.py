"""
Trade Signal Output Models (Story 8.8)

Purpose:
--------
Provides Pydantic models for complete trade signal output (FR22) with all required
fields for trade execution, audit trail, and backwards compatibility.

Data Models:
------------
- TargetLevels: Exit target levels (primary Jump + secondary + trailing stop)
- ConfidenceComponents: Confidence breakdown by validator (pattern/phase/volume)
- TradeSignal: Complete trade signal with all FR22 fields + FOREX SUPPORT
- RejectedSignal: Signal rejected during validation with failure details

Features:
---------
- Fixed-point arithmetic: Decimal type for all price/risk fields (NFR20)
- UTC timestamps: Enforced on all datetime fields
- Asset class support: STOCK, FOREX, CRYPTO with appropriate validators
- Serialization: JSON (with Decimal preservation), MessagePack, Pretty Print
- Schema versioning: Backwards compatibility with version field
- Validation: Entry/Stop/Target relationships, R-multiple calculation

Integration:
------------
- Story 8.2: ValidationChain for audit trail (FR25)
- Story 8.3: VolumeAnalysis for volume_confidence
- Story 8.4: PhaseClassification for phase_confidence
- Story 8.5: LevelValidator for entry/stop/target
- Story 8.6: RiskValidator for position sizing and risk metrics
- Story 8.7: StrategyValidator for final approval

Author: Story 8.8
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

import msgpack
from pydantic import BaseModel, Field, field_validator, model_validator

from src.models.validation import ValidationChain


class TargetLevels(BaseModel):
    """
    Target levels for trade exits.

    Contains primary target (Jump level), optional secondary targets,
    and trailing stop configuration.

    Fields:
    -------
    - primary_target: Jump level (main target)
    - secondary_targets: Intermediate targets between entry and Jump
    - trailing_stop_activation: Price level to activate trailing stop
    - trailing_stop_offset: Distance from price for trailing stop

    Example:
    --------
    >>> levels = TargetLevels(
    ...     primary_target=Decimal("156.00"),
    ...     secondary_targets=[Decimal("152.00"), Decimal("154.00")],
    ...     trailing_stop_activation=Decimal("154.00"),
    ...     trailing_stop_offset=Decimal("1.00")
    ... )
    """

    primary_target: Decimal = Field(..., description="Jump level (main target)")
    secondary_targets: list[Decimal] = Field(
        default_factory=list, description="Intermediate targets"
    )
    trailing_stop_activation: Decimal | None = Field(
        None, description="Price to activate trailing stop"
    )
    trailing_stop_offset: Decimal | None = Field(
        None, description="Trailing stop distance from price"
    )

    model_config = {"json_encoders": {Decimal: str}}


class ConfidenceComponents(BaseModel):
    """
    Breakdown of confidence score by validator.

    Provides transparency into how overall confidence is calculated
    from individual validator confidence scores.

    Fields:
    -------
    - pattern_confidence: Pattern detection confidence (0-100)
    - phase_confidence: Phase identification confidence (0-100)
    - volume_confidence: Volume profile confidence (0-100)
    - overall_confidence: Weighted average (70-95)

    Validation:
    -----------
    overall_confidence must match weighted average:
    - pattern: 50%
    - phase: 30%
    - volume: 20%

    Example:
    --------
    >>> components = ConfidenceComponents(
    ...     pattern_confidence=88,
    ...     phase_confidence=82,
    ...     volume_confidence=80,
    ...     overall_confidence=85
    ... )
    """

    pattern_confidence: int = Field(..., ge=0, le=100, description="Pattern detection confidence")
    phase_confidence: int = Field(..., ge=0, le=100, description="Phase identification confidence")
    volume_confidence: int = Field(..., ge=0, le=100, description="Volume profile confidence")
    overall_confidence: int = Field(..., ge=70, le=95, description="Weighted average confidence")

    @field_validator("overall_confidence")
    @classmethod
    def validate_overall(cls, v: int, info) -> int:
        """Ensure overall confidence computed from components."""
        values = info.data
        if (
            "pattern_confidence" in values
            and "phase_confidence" in values
            and "volume_confidence" in values
        ):
            # Weighted average: pattern 50%, phase 30%, volume 20%
            expected = int(
                values["pattern_confidence"] * 0.5
                + values["phase_confidence"] * 0.3
                + values["volume_confidence"] * 0.2
            )
            if abs(v - expected) > 2:  # Allow small rounding difference
                raise ValueError(
                    f"Overall confidence {v} doesn't match components (expected ~{expected})"
                )
        return v


class TradeSignal(BaseModel):
    """
    Complete trade signal output (FR22).

    Contains all information needed for trade execution and audit trail.
    Immutable once created to preserve audit integrity.

    Core FR22 Fields:
    -----------------
    - symbol: Ticker or currency pair (e.g., "AAPL", "EUR/USD")
    - pattern_type: SPRING, SOS, LPS, UTAD
    - phase: Wyckoff phase (C, D, etc.)
    - entry_price: Entry price for trade (8 decimal precision)
    - stop_loss: Stop loss price
    - target_levels: Exit targets (primary + secondary)
    - position_size: Number of shares/lots (Decimal for forex)
    - risk_amount: Dollar amount at risk
    - r_multiple: Risk/reward ratio
    - confidence_score: Overall signal confidence (70-95)
    - campaign_id: Campaign identifier
    - timestamp: Signal generation timestamp (UTC)

    Additional Fields:
    ------------------
    - validation_chain: Complete validation audit trail (FR25)
    - rejection_reasons: Why signal rejected (if applicable)
    - pattern_data: Pattern-specific metadata
    - volume_analysis: Volume metrics

    FOREX Support (AC: 11-14):
    ---------------------------
    - asset_class: STOCK, FOREX, CRYPTO
    - position_size_unit: SHARES, LOTS, CONTRACTS
    - leverage: Leverage ratio (1.0-500.0 for forex)
    - margin_requirement: Margin required to hold position
    - notional_value: Total position exposure

    Example:
    --------
    >>> signal = TradeSignal(
    ...     symbol="AAPL",
    ...     asset_class="STOCK",
    ...     pattern_type="SPRING",
    ...     phase="C",
    ...     timeframe="1h",
    ...     entry_price=Decimal("150.00"),
    ...     stop_loss=Decimal("148.00"),
    ...     target_levels=TargetLevels(primary_target=Decimal("156.00")),
    ...     position_size=Decimal("100"),
    ...     position_size_unit="SHARES",
    ...     risk_amount=Decimal("200.00"),
    ...     r_multiple=Decimal("3.0"),
    ...     confidence_score=85,
    ...     confidence_components=ConfidenceComponents(...),
    ...     validation_chain=ValidationChain(...),
    ...     timestamp=datetime.now(UTC)
    ... )
    """

    # Core identification (FR22)
    id: UUID = Field(default_factory=uuid4, description="Unique signal identifier")
    asset_class: Literal["STOCK", "FOREX", "CRYPTO"] = Field(
        default="STOCK", description="Asset class (AC: 11)"
    )
    symbol: str = Field(..., max_length=20, description="Ticker symbol", examples=["AAPL"])
    pattern_type: Literal["SPRING", "SOS", "LPS", "UTAD"] = Field(
        ..., description="Wyckoff pattern type"
    )
    phase: str = Field(..., max_length=1, description="Wyckoff phase (C, D, etc.)", examples=["C"])
    timeframe: str = Field(..., description="Bar interval", examples=["1h"])

    # Entry details (FR22)
    entry_price: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Entry price for trade",
        examples=["150.25"],
    )
    stop_loss: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Stop loss price",
        examples=["148.00"],
    )

    # Target levels (AC: 3)
    target_levels: TargetLevels = Field(..., description="Exit targets (primary + secondary)")

    # Position sizing & risk (FR22) - FOREX SUPPORT (AC: 12, 13, 14)
    position_size: Decimal = Field(
        ..., ge=Decimal("0.01"), description="Number of shares/lots", examples=["100"]
    )
    position_size_unit: Literal["SHARES", "LOTS", "CONTRACTS"] = Field(
        default="SHARES", description="Position size unit (AC: 12)"
    )
    leverage: Decimal | None = Field(
        None,
        ge=Decimal("1.0"),
        le=Decimal("500.0"),
        description="Leverage ratio (forex/crypto only) (AC: 13)",
    )
    margin_requirement: Decimal | None = Field(
        None, description="Margin required to hold position (AC: 13)"
    )
    notional_value: Decimal = Field(..., description="Total position exposure (AC: 14)")
    risk_amount: Decimal = Field(
        ...,
        description="Dollar amount at risk (account currency)",
        examples=["225.00"],
    )
    r_multiple: Decimal = Field(
        ..., ge=Decimal("0.0"), description="Risk/reward ratio", examples=["3.0"]
    )

    # Confidence (AC: 4)
    confidence_score: int = Field(
        ..., ge=70, le=95, description="Overall signal confidence", examples=[85]
    )
    confidence_components: ConfidenceComponents = Field(
        ..., description="Confidence breakdown by validator"
    )

    # Campaign tracking (FR22, FR23)
    campaign_id: str | None = Field(
        None, description="Campaign this signal belongs to", examples=["AAPL-2024-03-13-C"]
    )

    # Validation audit trail (FR25, AC: 2)
    validation_chain: ValidationChain = Field(
        ..., description="Complete validation results from all stages"
    )

    # Status tracking
    status: Literal[
        "PENDING", "APPROVED", "REJECTED", "FILLED", "STOPPED", "TARGET_HIT", "EXPIRED"
    ] = Field(default="PENDING", description="Current signal status")
    rejection_reasons: list[str] = Field(
        default_factory=list, description="Reasons for rejection if status=REJECTED"
    )

    # Additional context (AC: 2)
    pattern_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Pattern-specific metadata (bar timestamps, detection details)",
    )
    volume_analysis: dict[str, Any] = Field(
        default_factory=dict, description="Volume metrics for pattern bar"
    )

    # Timestamps (FR22, FR25)
    timestamp: datetime = Field(..., description="Signal generation timestamp (UTC)")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Record creation timestamp"
    )

    # Schema versioning (AC: 10)
    schema_version: int = Field(
        default=1, description="TradeSignal schema version for backwards compatibility"
    )

    @property
    def direction(self) -> Literal["LONG", "SHORT"]:
        """Derive trade direction from pattern_type.

        SPRING, SOS, LPS are accumulation (LONG) patterns.
        UTAD is a distribution (SHORT) pattern.
        """
        if self.pattern_type == "UTAD":
            return "SHORT"
        return "LONG"

    @field_validator("timestamp", "created_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str) -> datetime:
        """Enforce UTC timezone on all timestamps (NFR risk mitigation)."""
        # Handle string timestamps (from JSON deserialization)
        if isinstance(v, str):
            from datetime import datetime as dt

            parsed = dt.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

        # Handle datetime objects
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @field_validator("stop_loss")
    @classmethod
    def validate_stop_vs_entry(cls, v: Decimal, info) -> Decimal:
        """Ensure stop loss is on the correct side of entry for the direction.

        LONG (SPRING/SOS/LPS): stop must be below entry.
        SHORT (UTAD): stop must be above entry.
        """
        values = info.data
        if "entry_price" not in values or "pattern_type" not in values:
            return v
        entry = values["entry_price"]
        is_short = values["pattern_type"] == "UTAD"
        if is_short:
            if v <= entry:
                raise ValueError(f"Stop loss {v} must be above entry price {entry} for SHORT/UTAD")
        else:
            if v >= entry:
                raise ValueError(f"Stop loss {v} must be below entry price {entry}")
        return v

    @model_validator(mode="after")
    def validate_targets_vs_entry(self) -> "TradeSignal":
        """Ensure primary target is on the correct side of entry for the direction.

        LONG: target must be above entry.
        SHORT (UTAD): target must be below entry.
        """
        target = self.target_levels.primary_target
        entry = self.entry_price
        if self.direction == "SHORT":
            if target >= entry:
                raise ValueError(
                    f"Primary target {target} must be below entry {entry} for SHORT/UTAD"
                )
        else:
            if target <= entry:
                raise ValueError(f"Primary target {target} must be above entry {entry}")
        return self

    @model_validator(mode="after")
    def validate_r_multiple_calculation(self) -> "TradeSignal":
        """Verify R-multiple matches calculated value.

        LONG:  R = (target - entry) / (entry - stop)
        SHORT: R = (entry - target) / (stop - entry)
        Both formulas yield the same result: abs(target - entry) / abs(entry - stop).
        """
        entry = self.entry_price
        stop = self.stop_loss
        target = self.target_levels.primary_target
        risk = abs(entry - stop)
        if risk == 0:
            raise ValueError("Entry and stop loss cannot be the same price")
        expected_r = abs(target - entry) / risk
        if abs(self.r_multiple - expected_r) > Decimal("0.1"):  # Allow small rounding
            raise ValueError(f"R-multiple {self.r_multiple} doesn't match calculation {expected_r}")
        return self

    @model_validator(mode="after")
    def validate_asset_class_rules(self) -> "TradeSignal":
        """Validate asset-class-specific rules (AC: 11, 12, 13)."""
        # Validate position size unit matches asset class
        if self.asset_class == "STOCK" and self.position_size_unit != "SHARES":
            raise ValueError(f"STOCK must use SHARES, got {self.position_size_unit}")
        elif self.asset_class == "FOREX" and self.position_size_unit != "LOTS":
            raise ValueError(f"FOREX must use LOTS, got {self.position_size_unit}")

        # Validate leverage rules
        if self.asset_class == "STOCK":
            if self.leverage is not None and self.leverage > Decimal("2.0"):
                raise ValueError(f"STOCK leverage must be None or 1.0-2.0, got {self.leverage}")
        elif self.asset_class == "FOREX":
            if self.leverage is None:
                raise ValueError("FOREX requires leverage to be set")
            if not (Decimal("1.0") <= self.leverage <= Decimal("500.0")):
                raise ValueError(f"FOREX leverage must be 1.0-500.0, got {self.leverage}")

        # Validate margin requirement for leveraged positions
        if self.leverage and self.leverage > Decimal("1.0"):
            if self.margin_requirement is None:
                raise ValueError("margin_requirement must be set when leverage > 1.0")

        # Validate position size ranges
        if self.asset_class == "STOCK":
            if self.position_size < Decimal("1.0"):
                raise ValueError(
                    f"STOCK position_size should be >= 1.0 (whole shares), got {self.position_size}"
                )
        elif self.asset_class == "FOREX":
            if not (Decimal("0.01") <= self.position_size <= Decimal("100.0")):
                raise ValueError(
                    f"FOREX position_size must be 0.01-100.0 lots, got {self.position_size}"
                )

        return self

    model_config = {
        "json_encoders": {Decimal: str, datetime: lambda v: v.isoformat()},
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "asset_class": "STOCK",
                    "symbol": "AAPL",
                    "pattern_type": "SPRING",
                    "phase": "C",
                    "timeframe": "1h",
                    "entry_price": "150.00",
                    "stop_loss": "148.00",
                    "target_levels": {
                        "primary_target": "156.00",
                        "secondary_targets": ["152.00", "154.00"],
                        "trailing_stop_activation": "154.00",
                        "trailing_stop_offset": "1.00",
                    },
                    "position_size": "100",
                    "position_size_unit": "SHARES",
                    "leverage": None,
                    "margin_requirement": None,
                    "notional_value": "15000.00",
                    "risk_amount": "200.00",
                    "r_multiple": "3.0",
                    "confidence_score": 85,
                    "confidence_components": {
                        "pattern_confidence": 88,
                        "phase_confidence": 82,
                        "volume_confidence": 80,
                        "overall_confidence": 85,
                    },
                    "campaign_id": "AAPL-2024-03-13-C",
                    "status": "APPROVED",
                    "timestamp": "2024-03-13T14:30:00Z",
                    "schema_version": 1,
                }
            ]
        },
    }

    def to_pretty_string(self) -> str:
        """
        Format signal for human-readable CLI display (AC: 6).

        Returns:
            Multi-line formatted string with all key signal details

        Example:
        --------
        >>> print(signal.to_pretty_string())
        ============================================================
        TRADE SIGNAL: SPRING on AAPL
        ============================================================
        Signal ID:       550e8400-e29b-41d4-a716-446655440000
        Status:          APPROVED
        ...
        """
        lines = [
            "=" * 60,
            f"TRADE SIGNAL: {self.pattern_type} on {self.symbol}",
            "=" * 60,
            f"Signal ID:       {self.id}",
            f"Status:          {self.status}",
            f"Asset Class:     {self.asset_class}",
            f"Timeframe:       {self.timeframe}",
            f"Phase:           {self.phase}",
            f"Confidence:      {self.confidence_score}% (Pattern: {self.confidence_components.pattern_confidence}%, Phase: {self.confidence_components.phase_confidence}%, Volume: {self.confidence_components.volume_confidence}%)",
            "",
            f"ENTRY DETAILS ({self.direction}):",
            f"  Entry Price:   ${self.entry_price:.2f}",
            f"  Stop Loss:     ${self.stop_loss:.2f}",
            f"  Risk/Share:    ${abs(self.entry_price - self.stop_loss):.2f}",
            "",
            "TARGETS:",
            f"  Primary:       ${self.target_levels.primary_target:.2f} (Jump level)",
        ]

        if self.target_levels.secondary_targets:
            for i, target in enumerate(self.target_levels.secondary_targets, 1):
                lines.append(f"  Secondary {i}:   ${target:.2f}")

        lines.extend(
            [
                "",
                "POSITION SIZING:",
                f"  Position:      {self.position_size} {self.position_size_unit}",
            ]
        )

        if self.leverage:
            lines.append(f"  Leverage:      {self.leverage}:1")
        if self.margin_requirement:
            lines.append(f"  Margin Req:    ${self.margin_requirement:.2f}")

        lines.extend(
            [
                f"  Notional Value: ${self.notional_value:.2f}",
                f"  Risk Amount:   ${self.risk_amount:.2f}",
                f"  R-Multiple:    {self.r_multiple:.2f}R",
                f"  Potential Gain: ${abs(self.target_levels.primary_target - self.entry_price) * self.position_size:.2f}",
            ]
        )

        if self.campaign_id:
            lines.append(f"\nCampaign:        {self.campaign_id}")

        # Get validation status value (handle enum or string)
        overall_status = (
            self.validation_chain.overall_status.value
            if hasattr(self.validation_chain.overall_status, "value")
            else str(self.validation_chain.overall_status)
        )
        lines.extend(["", f"VALIDATION: {overall_status}"])

        for result in self.validation_chain.validation_results:
            result_status = (
                result.status.value if hasattr(result.status, "value") else str(result.status)
            )
            status_symbol = "✓" if result_status == "PASS" else "✗"
            lines.append(f"  {status_symbol} {result.stage}: {result_status}")

        if self.rejection_reasons:
            lines.extend(["", "REJECTION REASONS:"])
            for reason in self.rejection_reasons:
                lines.append(f"  - {reason}")

        lines.extend(
            [
                "",
                f"Generated:       {self.timestamp.isoformat()}",
                "=" * 60,
            ]
        )

        return "\n".join(lines)

    def to_msgpack(self) -> bytes:
        """
        Serialize to MessagePack binary format (AC: 5).

        Useful for high-performance API communication or caching.

        Returns:
            MessagePack binary data

        Example:
        --------
        >>> data = signal.to_msgpack()
        >>> restored = TradeSignal.from_msgpack(data)
        """
        data = self.model_dump()
        # Convert Decimal to string for msgpack compatibility
        data = self._convert_decimals_to_str(data)
        return msgpack.packb(data, use_bin_type=True)

    @classmethod
    def from_msgpack(cls, data: bytes) -> "TradeSignal":
        """
        Deserialize from MessagePack binary format.

        Parameters:
        -----------
        data : bytes
            MessagePack binary data

        Returns:
        --------
        TradeSignal
            Restored TradeSignal instance
        """
        unpacked = msgpack.unpackb(data, raw=False)
        return cls(**unpacked)

    @staticmethod
    def _convert_decimals_to_str(data: Any) -> Any:
        """Recursively convert Decimal/UUID/datetime to str for serialization."""
        if isinstance(data, Decimal):
            return str(data)
        elif isinstance(data, UUID):
            return str(data)
        elif isinstance(data, datetime):
            return data.isoformat()
        elif isinstance(data, dict):
            return {k: TradeSignal._convert_decimals_to_str(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [TradeSignal._convert_decimals_to_str(item) for item in data]
        else:
            return data


class RejectedSignal(BaseModel):
    """
    Rejected signal with failure details (AC: 2).

    Created when pattern fails validation at any stage.
    Provides audit trail for why signals were rejected.

    Fields:
    -------
    - id: Unique rejection identifier
    - pattern_id: Pattern that failed validation
    - symbol: Trading symbol
    - pattern_type: SPRING, SOS, LPS, UTAD
    - rejection_stage: Which validator failed (Volume, Phase, Levels, Risk, Strategy)
    - rejection_reason: Detailed failure explanation
    - validation_chain: Partial validation results
    - timestamp: Rejection timestamp (UTC)
    - schema_version: Schema version for backwards compatibility

    Example:
    --------
    >>> rejected = RejectedSignal(
    ...     pattern_id=UUID("..."),
    ...     symbol="AAPL",
    ...     pattern_type="SPRING",
    ...     rejection_stage="Risk",
    ...     rejection_reason="Portfolio heat would exceed 10% limit",
    ...     validation_chain=ValidationChain(...)
    ... )
    """

    id: UUID = Field(default_factory=uuid4, description="Unique rejection identifier")
    pattern_id: UUID = Field(..., description="Pattern that failed validation")
    symbol: str = Field(..., max_length=20, description="Trading symbol")
    pattern_type: str = Field(..., description="SPRING, SOS, LPS, UTAD")
    rejection_stage: str = Field(
        ...,
        description="Which validator failed (Volume, Phase, Levels, Risk, Strategy)",
    )
    rejection_reason: str = Field(..., description="Detailed failure explanation")
    validation_chain: ValidationChain = Field(..., description="Partial validation results")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Rejection timestamp"
    )
    schema_version: int = Field(default=1, description="Schema version for backwards compatibility")

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str) -> datetime:
        """Enforce UTC timezone."""
        # Handle string timestamps (from JSON deserialization)
        if isinstance(v, str):
            from datetime import datetime as dt

            parsed = dt.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

        # Handle datetime objects
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    model_config = {"json_encoders": {Decimal: str, datetime: lambda v: v.isoformat()}}
