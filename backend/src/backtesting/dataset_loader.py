"""
Dataset Loader Utility (Story 12.2 Task 9)

Purpose:
--------
Utility functions for loading labeled pattern datasets for accuracy testing.
Provides convenient access to Parquet-formatted labeled patterns with proper
error handling and type conversion.

Usage:
------
    from backtesting.dataset_loader import load_labeled_patterns

    # Load dataset
    df = load_labeled_patterns()

    # Load specific version
    df = load_labeled_patterns(version="v1")

    # Convert to list of LabeledPattern models
    patterns = load_labeled_patterns_as_models()

Author: Story 12.2 Task 9
"""

import json
from pathlib import Path
from typing import Any

import pandas as pd


def load_labeled_patterns(version: str = "v1") -> pd.DataFrame:
    """
    Load labeled pattern dataset for accuracy testing.

    This function loads the Parquet-formatted labeled pattern dataset
    and returns it as a pandas DataFrame for analysis and validation.

    Args:
        version: Dataset version (default "v1")

    Returns:
        pandas DataFrame with labeled patterns

    Raises:
        FileNotFoundError: If dataset file does not exist
        ValueError: If dataset is empty or invalid

    Example:
        >>> df = load_labeled_patterns()
        >>> print(f"Loaded {len(df)} patterns")
        >>> print(df[['symbol', 'pattern_type', 'correctness']].head())

    Notes:
        - Dataset path: backend/tests/datasets/labeled_patterns_{version}.parquet
        - JSON columns (volume_characteristics, spread_characteristics, preliminary_events)
          are returned as JSON strings and must be parsed if needed
        - Decimal columns (entry_price, stop_loss, target_price) are returned as strings
          to preserve precision
    """
    # Construct dataset path
    backend_dir = Path(__file__).parent.parent.parent
    dataset_path = backend_dir / f"tests/datasets/labeled_patterns_{version}.parquet"

    # Check if file exists
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Labeled pattern dataset not found: {dataset_path}\n"
            f"Available versions can be found in {dataset_path.parent}"
        )

    # Load Parquet file
    try:
        df = pd.read_parquet(dataset_path)
    except Exception as e:
        raise ValueError(f"Failed to load dataset from {dataset_path}: {e}") from e

    # Validate dataset
    if df.empty:
        raise ValueError(f"Dataset is empty: {dataset_path}")

    # Ensure required columns exist (AC 1)
    required_columns = ["symbol", "date", "pattern_type", "confidence", "correctness"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(
            f"Dataset missing required columns: {missing_columns}\n"
            f"Found columns: {list(df.columns)}"
        )

    return df


def load_labeled_patterns_as_models(version: str = "v1") -> list[dict[str, Any]]:
    """
    Load labeled pattern dataset as list of dictionaries (Pydantic-compatible).

    This function loads the dataset and converts it to a list of dictionaries
    that can be validated against the LabeledPattern Pydantic model.

    Args:
        version: Dataset version (default "v1")

    Returns:
        List of pattern dictionaries

    Example:
        >>> from models.backtest import LabeledPattern
        >>> patterns_data = load_labeled_patterns_as_models()
        >>> patterns = [LabeledPattern(**p) for p in patterns_data]
        >>> print(f"Loaded {len(patterns)} validated patterns")

    Notes:
        - JSON string columns are automatically parsed to dicts/lists
        - Decimal string columns remain as strings (Pydantic will convert)
        - Datetime columns are converted to ISO format strings
    """
    df = load_labeled_patterns(version=version)

    # Convert DataFrame to list of dictionaries
    records = df.to_dict(orient="records")

    # Parse JSON string columns back to dict/list
    json_columns = [
        "volume_characteristics",
        "spread_characteristics",
        "preliminary_events",
    ]

    for record in records:
        for col in json_columns:
            if col in record and isinstance(record[col], str):
                try:
                    record[col] = json.loads(record[col])
                except json.JSONDecodeError:
                    # Leave as string if not valid JSON
                    pass

        # Convert correctness boolean to string (for Pydantic)
        if "correctness" in record and isinstance(record["correctness"], bool):
            record["correctness"] = "CORRECT" if record["correctness"] else "INCORRECT"

        # Convert datetime to ISO format string (for Pydantic)
        if "date" in record and isinstance(record["date"], pd.Timestamp):
            record["date"] = record["date"].isoformat()
        if "created_at" in record and isinstance(record["created_at"], pd.Timestamp):
            record["created_at"] = record["created_at"].isoformat()

    return records


def get_dataset_stats(version: str = "v1") -> dict[str, Any]:
    """
    Get statistics about the labeled pattern dataset.

    Args:
        version: Dataset version (default "v1")

    Returns:
        Dictionary with dataset statistics

    Example:
        >>> stats = get_dataset_stats()
        >>> print(f"Total patterns: {stats['total_patterns']}")
        >>> print(f"Correctness: {stats['correctness_pct']:.1f}%")
    """
    df = load_labeled_patterns(version=version)

    stats = {
        "total_patterns": len(df),
        "total_columns": len(df.columns),
        "pattern_type_counts": df["pattern_type"].value_counts().to_dict(),
        "correctness_counts": df["correctness"].value_counts().to_dict(),
        "correctness_pct": (df["correctness"].sum() / len(df)) * 100,
        "verified_count": df.get("reviewer_verified", pd.Series([False] * len(df))).sum(),
        "symbol_counts": df["symbol"].value_counts().to_dict(),
        "campaign_type_counts": df["campaign_type"].value_counts().to_dict()
        if "campaign_type" in df.columns
        else {},
    }

    return stats
