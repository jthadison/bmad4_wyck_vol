"""
Pattern Statistics Models (Story 10.7)

Purpose:
--------
Pydantic models for historical pattern performance statistics.
Provides educational context showing win rates of rejected vs valid patterns.

Data Models:
------------
- PatternStatistics: Historical performance data for pattern types

Integration:
------------
- Story 10.7: Educational Rejection Detail View
- GET /api/v1/patterns/statistics endpoint

Author: Story 10.7
"""

from decimal import Decimal

from pydantic import BaseModel, Field


class PatternStatistics(BaseModel):
    """
    Historical pattern performance statistics for educational context.

    Compares win rates between patterns that violated specific rules
    vs patterns that followed the rules correctly.

    Fields:
    -------
    - pattern_type: SPRING, UTAD, SOS, LPS, SC, AR, ST
    - rejection_category: Category of rejection (volume_high, volume_low, test_not_confirmed, etc.)
    - invalid_win_rate: Win rate for patterns violating this rule (0-100)
    - valid_win_rate: Win rate for valid patterns (0-100)
    - sample_size_invalid: Number of invalid patterns analyzed
    - sample_size_valid: Number of valid patterns analyzed
    - sufficient_data: True if sample_size >= 20
    - message: Human-readable comparison message

    Example:
    --------
    >>> stats = PatternStatistics(
    ...     pattern_type="SPRING",
    ...     rejection_category="volume_high",
    ...     invalid_win_rate=Decimal("23.5"),
    ...     valid_win_rate=Decimal("68.2"),
    ...     sample_size_invalid=147,
    ...     sample_size_valid=523,
    ...     sufficient_data=True,
    ...     message="Springs with volume >0.7x: 23% win rate vs 68% for valid springs"
    ... )
    """

    pattern_type: str = Field(..., description="SPRING, UTAD, SOS, LPS, SC, AR, ST")
    rejection_category: str | None = Field(
        None, description="Category of rejection (volume_high, test_not_confirmed, etc.)"
    )
    invalid_win_rate: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        decimal_places=2,
        description="Win rate for patterns violating this rule",
    )
    valid_win_rate: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        decimal_places=2,
        description="Win rate for valid patterns",
    )
    sample_size_invalid: int = Field(..., ge=0, description="Number of invalid patterns analyzed")
    sample_size_valid: int = Field(..., ge=0, description="Number of valid patterns analyzed")
    sufficient_data: bool = Field(..., description="True if sample_size >= 20")
    message: str = Field(..., description="Human-readable comparison message")

    model_config = {
        "json_encoders": {Decimal: str},
        "json_schema_extra": {
            "examples": [
                {
                    "pattern_type": "SPRING",
                    "rejection_category": "volume_high",
                    "invalid_win_rate": "23.5",
                    "valid_win_rate": "68.2",
                    "sample_size_invalid": 147,
                    "sample_size_valid": 523,
                    "sufficient_data": True,
                    "message": "Springs with volume >0.7x: 23% win rate vs 68% for valid springs",
                }
            ]
        },
    }
