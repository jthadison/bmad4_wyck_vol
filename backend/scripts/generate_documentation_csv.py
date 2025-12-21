"""
Generate Documentation CSV (Story 12.2 Task 7)

Purpose:
--------
Generate documentation CSV with pattern IDs and justifications for all
labeled patterns. This provides human-readable documentation alongside
the Parquet dataset for review and verification.

Usage:
------
    python backend/scripts/generate_documentation_csv.py

Input:
------
    backend/tests/datasets/staging/labeled_patterns_staging.json

Output:
-------
    backend/tests/datasets/labeled_patterns_v1_documentation.csv

Author: Story 12.2 Task 7
"""

import csv
import json
from pathlib import Path


def load_staging_data(staging_file: Path) -> list[dict]:
    """Load labeled patterns from JSON staging file."""
    with open(staging_file) as f:
        return json.load(f)


def generate_documentation_csv(patterns: list[dict], output_file: Path) -> None:
    """
    Generate documentation CSV from labeled patterns.

    Args:
        patterns: List of pattern dictionaries
        output_file: Path to output CSV file
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # CSV columns from AC 8 Subtask 7.1
    fieldnames = [
        "pattern_id",
        "symbol",
        "date",
        "pattern_type",
        "correctness",
        "justification",
        "labeler",
        "verification_status",
        "campaign_type",
        "campaign_phase",
        "sequential_validity",
        "false_positive_reason",
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for pattern in patterns:
            row = {
                "pattern_id": pattern["id"],
                "symbol": pattern["symbol"],
                "date": pattern["date"],
                "pattern_type": pattern["pattern_type"],
                "correctness": pattern["correctness"],
                "justification": pattern["justification"],
                "labeler": "Automated Dataset Generation (Story 12.2)",
                "verification_status": "verified"
                if pattern.get("reviewer_verified", False)
                else "unverified",
                "campaign_type": pattern.get("campaign_type", ""),
                "campaign_phase": pattern.get("campaign_phase", ""),
                "sequential_validity": pattern.get("sequential_validity", True),
                "false_positive_reason": pattern.get("false_positive_reason") or "",
            }
            writer.writerow(row)


def main():
    """Main documentation generation workflow."""
    print("=" * 80)
    print("GENERATE DOCUMENTATION CSV (Story 12.2 Task 7)")
    print("=" * 80)

    backend_dir = Path(__file__).parent.parent
    staging_file = backend_dir / "tests/datasets/staging/labeled_patterns_staging.json"
    output_file = backend_dir / "tests/datasets/labeled_patterns_v1_documentation.csv"

    print(f"\nInput:  {staging_file}")
    print(f"Output: {output_file}")

    # Load patterns
    print("\n[1/2] Loading labeled patterns...")
    patterns = load_staging_data(staging_file)
    print(f"      Loaded {len(patterns)} patterns")

    # Generate CSV
    print("\n[2/2] Generating documentation CSV...")
    generate_documentation_csv(patterns, output_file)

    # Stats
    verified_count = sum(1 for p in patterns if p.get("reviewer_verified", False))
    correct_count = sum(1 for p in patterns if p["correctness"])

    print(f"      Total patterns: {len(patterns)}")
    print(f"      Verified: {verified_count} ({verified_count/len(patterns)*100:.1f}%)")
    print(f"      Correct: {correct_count} ({correct_count/len(patterns)*100:.1f}%)")
    print(
        f"      Incorrect: {len(patterns)-correct_count} ({(len(patterns)-correct_count)/len(patterns)*100:.1f}%)"
    )

    file_size = output_file.stat().st_size / 1024
    print("\n[OK] Documentation CSV generated!")
    print(f"      File: {output_file}")
    print(f"      Size: {file_size:.1f} KB")

    print("\nNext step: Commit to Git (not LFS)")
    print("  git add backend/tests/datasets/labeled_patterns_v1_documentation.csv")


if __name__ == "__main__":
    main()
