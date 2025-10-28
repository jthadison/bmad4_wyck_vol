"""
Pandas DataFrame conversion utilities for OHLCV bars.

This module provides utilities to convert between OHLCVBar Pydantic models
and pandas DataFrames for vectorized operations like rolling averages.
"""

from __future__ import annotations

from decimal import Decimal
from typing import List

import pandas as pd

from src.models.ohlcv import OHLCVBar


def bars_to_dataframe(bars: List[OHLCVBar]) -> pd.DataFrame:
    """
    Convert OHLCV bars to pandas DataFrame for vectorized operations.

    Converts list of Pydantic models to DataFrame with timestamp index.
    Decimal columns are converted to float for pandas compatibility.

    Args:
        bars: List of OHLCVBar objects

    Returns:
        DataFrame with:
        - Index: timestamp (datetime)
        - Columns: symbol, timeframe, open, high, low, close, volume,
                   spread, spread_ratio, volume_ratio
        - Price columns: float (converted from Decimal)

    Example:
        ```python
        bars = await repository.get_bars("AAPL", "1d", start, end)
        df = bars_to_dataframe(bars)

        # Calculate 20-bar rolling averages
        df['volume_avg_20'] = df['volume'].rolling(20).mean()
        df['spread_avg_20'] = df['spread'].rolling(20).mean()
        ```
    """
    if not bars:
        return pd.DataFrame()

    # Convert Pydantic models to dicts
    data = [bar.model_dump() for bar in bars]

    # Create DataFrame
    df = pd.DataFrame(data)

    # Set timestamp as index
    df.set_index('timestamp', inplace=True)

    # Convert Decimal columns to float for pandas operations
    decimal_cols = ['open', 'high', 'low', 'close', 'spread', 'spread_ratio', 'volume_ratio']
    for col in decimal_cols:
        if col in df.columns:
            df[col] = df[col].astype(float)

    # Sort by timestamp
    df.sort_index(inplace=True)

    return df


def dataframe_to_bars(df: pd.DataFrame) -> List[OHLCVBar]:
    """
    Convert pandas DataFrame back to list of OHLCVBar models.

    Reverse conversion from DataFrame to Pydantic models.
    Float values are converted back to Decimal for price fields.

    Args:
        df: DataFrame with OHLCV data (timestamp as index)

    Returns:
        List of OHLCVBar objects

    Raises:
        ValueError: If required columns are missing
        ValidationError: If data fails Pydantic validation

    Example:
        ```python
        df = bars_to_dataframe(bars)
        # ... perform pandas operations ...
        updated_bars = dataframe_to_bars(df)
        ```
    """
    if df.empty:
        return []

    # Reset index to include timestamp as column
    df_reset = df.reset_index()

    # Convert float back to Decimal for price fields
    decimal_cols = ['open', 'high', 'low', 'close', 'spread', 'spread_ratio', 'volume_ratio']
    for col in decimal_cols:
        if col in df_reset.columns:
            df_reset[col] = df_reset[col].apply(lambda x: Decimal(str(x)))

    # Convert each row to OHLCVBar
    bars = []
    for _, row in df_reset.iterrows():
        bar_dict = row.to_dict()
        bars.append(OHLCVBar(**bar_dict))

    return bars
