"""
Correlation Matrix Data Models - Portfolio Correlation Visualization (Feature P2-7)

Purpose:
--------
Provides Pydantic models for the correlation matrix API endpoint, representing
the pairwise correlation between active campaign returns.

Key Quant Concepts:
--------------------
- Correlation of RETURNS (not prices) is the correct statistical measure.
  Price series are non-stationary; return series are stationary and suitable
  for Pearson correlation. Formula: r_t = (P_t - P_{t-1}) / P_{t-1}

- Pearson correlation ranges from -1 (perfect inverse) to +1 (perfect co-movement).
  Wyckoff campaigns are often sector-correlated: tech stocks (AAPL, MSFT, GOOGL)
  will show high correlation (0.7+), while tech vs healthcare may be near 0.

- The 6% correlated risk limit means: if two positions together represent >6%
  portfolio risk AND they are correlated (r > 0.6), the second entry is blocked.
  Rachel (Risk Manager agent) enforces this rule.

Thresholds:
-----------
  LOW:      -1.0 to 0.3   (green  - safe to add)
  MODERATE:  0.3 to 0.6   (yellow - caution)
  HIGH:      0.6 to 1.0   (red    - Rachel blocks correlated risk)

Author: Feature P2-7 - Portfolio Correlation Matrix
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BlockedPair(BaseModel):
    """
    A pair of campaigns blocked due to high correlation.

    Rachel (Risk Manager) blocks a second campaign entry when:
    1. Correlation between campaigns exceeds the threshold (default 0.6), AND
    2. Combined position risk exceeds the correlated risk limit (6%)

    Attributes:
    -----------
    campaign_a : str
        Name of the first (existing) campaign
    campaign_b : str
        Name of the second (attempted) campaign that was blocked
    correlation : float
        Pearson correlation coefficient between the two campaigns' returns
    reason : str
        Human-readable explanation of why the entry was blocked
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    campaign_a: str = Field(..., description="First campaign name")
    campaign_b: str = Field(..., description="Second campaign name (the one blocked)")
    correlation: float = Field(..., description="Pearson correlation coefficient", ge=-1.0, le=1.0)
    reason: str = Field(..., description="Human-readable reason for blocking")


class CorrelationMatrixResponse(BaseModel):
    """
    NxN pairwise correlation matrix for active campaigns.

    The matrix is symmetric: matrix[i][j] == matrix[j][i].
    The diagonal is always 1.0 (each campaign is perfectly correlated with itself).

    Example with 3 campaigns:
    --------------------------
    campaigns = ["AAPL-2024-01", "MSFT-2024-01", "JNJ-2024-01"]
    matrix = [
        [1.00, 0.78, 0.12],   # AAPL vs AAPL, MSFT, JNJ
        [0.78, 1.00, 0.21],   # MSFT vs AAPL, MSFT, JNJ
        [0.12, 0.21, 1.00],   # JNJ  vs AAPL, MSFT, JNJ
    ]

    AAPL-MSFT correlation of 0.78 is HIGH (> 0.6), so Rachel blocks
    adding MSFT if AAPL already holds >3% portfolio risk.

    Attributes:
    -----------
    campaigns : list[str]
        Ordered list of campaign names. Row i / column j corresponds to campaigns[i] / campaigns[j].
    matrix : list[list[float]]
        NxN symmetric matrix of Pearson return correlations. Diagonal = 1.0.
    blocked_pairs : list[BlockedPair]
        Campaign pairs where correlation exceeds heat_threshold (Rachel blocks entry).
    heat_threshold : float
        Correlation value above which Rachel blocks new entries (default 0.6).
    last_updated : datetime
        UTC timestamp when this matrix was computed.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    campaigns: list[str] = Field(..., description="Ordered list of campaign names")
    matrix: list[list[float]] = Field(
        ..., description="NxN symmetric Pearson correlation matrix of returns"
    )
    blocked_pairs: list[BlockedPair] = Field(
        ..., description="Campaign pairs blocked due to high correlation"
    )
    heat_threshold: float = Field(
        default=0.6,
        description="Correlation threshold above which Rachel blocks new entries",
        ge=0.0,
        le=1.0,
    )
    last_updated: datetime = Field(..., description="UTC timestamp of matrix computation")
