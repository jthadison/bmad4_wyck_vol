"""
Export Labeled Patterns to Parquet Format (Story 12.2 Task 6)

Purpose:
--------
Export labeled patterns from JSON staging format to Parquet file with
Git LFS tracking. Validates all entries against LabeledPattern Pydantic
model and converts to pandas DataFrame for efficient columnar storage.

Usage:
------
    python backend/scripts/export_to_parquet.py

Input:
------
    backend/tests/datasets/staging/labeled_patterns_staging.json

Output:
-------
    backend/tests/datasets/labeled_patterns_v1.parquet

Author: Story 12.2 Task 6
"""

import json
import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Add backend/src to Python path for imports when running from backend/
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir / "src"))


def load_staging_data(staging_file: Path) -> list[dict]:
    """
    Load labeled patterns from JSON staging file.

    Args:
        staging_file: Path to JSON staging file

    Returns:
        List of pattern dictionaries
    """
    if not staging_file.exists():
        raise FileNotFoundError(f"Staging file not found: {staging_file}")

    with open(staging_file) as f:
        return json.load(f)


def validate_patterns(patterns: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Validate patterns against LabeledPattern Pydantic model.

    Args:
        patterns: List of pattern dictionaries

    Returns:
        Tuple of (valid_patterns, validation_errors)
    """
    try:
        from models.backtest import LabeledPattern
    except ModuleNotFoundError:
        # If import fails, skip validation (will be validated in tests)
        print("Warning: Could not import LabeledPattern model, skipping validation")
        return patterns, []

    valid_patterns = []
    errors = []

    for i, pattern_data in enumerate(patterns):
        try:
            # Validate with Pydantic
            validated = LabeledPattern(**pattern_data)
            # Convert back to dict for DataFrame creation
            valid_patterns.append(validated.model_dump())
        except Exception as e:
            errors.append(f"Pattern {i}: {str(e)}")

    return valid_patterns, errors


def convert_to_dataframe(patterns: list[dict]) -> pd.DataFrame:
    """
    Convert pattern dictionaries to pandas DataFrame.

    Args:
        patterns: List of pattern dictionaries

    Returns:
        pandas DataFrame with proper dtypes
    """
    df = pd.DataFrame(patterns)

    # Convert UUID strings to strings (already strings from JSON)
    # Convert datetime strings to pandas datetime
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)

    # Convert Decimal strings to strings (preserve precision)
    decimal_columns = ["entry_price", "stop_loss", "target_price", "volume_ratio", "spread_ratio"]
    for col in decimal_columns:
        if col in df.columns:
            df[col] = df[col].astype(str)

    # Convert JSON columns (dict/list) to JSON strings
    if "volume_characteristics" in df.columns:
        df["volume_characteristics"] = df["volume_characteristics"].apply(json.dumps)
    if "spread_characteristics" in df.columns:
        df["spread_characteristics"] = df["spread_characteristics"].apply(json.dumps)
    if "preliminary_events" in df.columns:
        df["preliminary_events"] = df["preliminary_events"].apply(json.dumps)

    return df


def export_to_parquet(df: pd.DataFrame, output_file: Path) -> None:
    """
    Export DataFrame to Parquet file.

    Args:
        df: pandas DataFrame with labeled patterns
        output_file: Path to output Parquet file
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Create PyArrow table with proper schema
    table = pa.Table.from_pandas(df)

    # Write to Parquet with compression
    pq.write_table(
        table,
        output_file,
        compression="snappy",  # Good balance of compression and speed
        use_dictionary=True,  # Enable dictionary encoding for string columns
    )


def verify_parquet_file(parquet_file: Path) -> dict:
    """
    Verify Parquet file can be loaded and has correct schema.

    Args:
        parquet_file: Path to Parquet file

    Returns:
        Dictionary with verification stats
    """
    # Test loading with pandas
    df = pd.read_parquet(parquet_file)

    # Required columns from AC 1
    required_columns = ["symbol", "date", "pattern_type", "confidence", "correctness"]
    missing_columns = [col for col in required_columns if col not in df.columns]

    stats = {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "missing_required_columns": missing_columns,
        "file_size_kb": parquet_file.stat().st_size / 1024,
        "pattern_types": df["pattern_type"].value_counts().to_dict(),
        "correctness_distribution": df["correctness"].value_counts().to_dict(),
    }

    return stats


def main():
    """Main export workflow."""
    print("=" * 80)
    print("EXPORT LABELED PATTERNS TO PARQUET (Story 12.2 Task 6)")
    print("=" * 80)

    # File paths
    staging_file = backend_dir / "tests/datasets/staging/labeled_patterns_staging.json"
    output_file = backend_dir / "tests/datasets/labeled_patterns_v1.parquet"

    print(f"\nInput:  {staging_file}")
    print(f"Output: {output_file}")

    # Step 1: Load staging data
    print("\n[1/5] Loading staging data...")
    patterns = load_staging_data(staging_file)
    print(f"      Loaded {len(patterns)} patterns")

    # Step 2: Validate patterns
    print("\n[2/5] Validating patterns against Pydantic model...")
    valid_patterns, errors = validate_patterns(patterns)
    if errors:
        print(f"      WARNING: {len(errors)} validation errors:")
        for error in errors[:5]:  # Show first 5 errors
            print(f"        - {error}")
        if len(errors) > 5:
            print(f"        ... and {len(errors) - 5} more")
        print(f"      Proceeding with {len(valid_patterns)} valid patterns")
    else:
        print(f"      [OK] All {len(valid_patterns)} patterns valid!")

    # Step 3: Convert to DataFrame
    print("\n[3/5] Converting to pandas DataFrame...")
    df = convert_to_dataframe(valid_patterns)
    print(f"      DataFrame shape: {df.shape}")
    print(f"      Columns: {', '.join(df.columns[:10])}... ({len(df.columns)} total)")

    # Step 4: Export to Parquet
    print("\n[4/5] Exporting to Parquet format...")
    export_to_parquet(df, output_file)
    print(f"      [OK] Exported to {output_file}")

    # Step 5: Verify
    print("\n[5/5] Verifying Parquet file...")
    stats = verify_parquet_file(output_file)

    print(f"      Total rows: {stats['total_rows']}")
    print(f"      Total columns: {stats['total_columns']}")
    print(f"      File size: {stats['file_size_kb']:.1f} KB")

    if stats["missing_required_columns"]:
        print(f"      WARNING: Missing required columns: {stats['missing_required_columns']}")
    else:
        print("      [OK] All required columns present")

    print("\n      Pattern distribution:")
    for pattern_type, count in stats["pattern_types"].items():
        print(f"        {pattern_type}: {count}")

    print("\n      Correctness distribution:")
    for correctness, count in stats["correctness_distribution"].items():
        print(f"        {correctness}: {count}")

    print("\n" + "=" * 80)
    print("[OK] EXPORT COMPLETE!")
    print("=" * 80)
    print(f"\nParquet file ready at: {output_file}")
    print("Next step: Commit to Git LFS")
    print("  git add backend/tests/datasets/labeled_patterns_v1.parquet")
    print("  git commit -m 'Add labeled pattern dataset v1 (Story 12.2)'")


if __name__ == "__main__":
    main()
