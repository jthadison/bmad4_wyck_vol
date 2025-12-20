#!/usr/bin/env python3
"""
Live Orchestrator Test - Verify all Story 11.9 detectors are loaded and functional.

This script performs a comprehensive validation of the orchestrator with database connection.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.container import OrchestratorContainer


def main():
    """Test orchestrator health and detector loading."""
    print("\n" + "=" * 70)
    print("LIVE ORCHESTRATOR VALIDATION - Story 11.9")
    print("=" * 70)

    # Initialize orchestrator
    print("\n[1] Initializing OrchestratorContainer...")
    try:
        container = OrchestratorContainer()
        print("    [OK] Container initialized successfully")
    except Exception as e:
        print(f"    [FAIL] FAILED to initialize container: {e}")
        return False

    # Check health
    print("\n[2] Running health check...")
    try:
        health = container.health_check()
        print(f"    Status: {health['status'].upper()}")
        print(f"    Loaded: {health['loaded_count']} detectors")
        print(f"    Failed: {health['failed_count']} detectors")
    except Exception as e:
        print(f"    [FAIL] FAILED health check: {e}")
        return False

    # Validate HEALTHY status
    print("\n[3] Validating orchestrator status...")
    if health["status"] != "healthy":
        print(f"    [FAIL] FAILED: Expected 'healthy', got '{health['status']}'")
        return False
    print("    [OK] Status is HEALTHY")

    # Validate detector count
    print("\n[4] Validating detector count...")
    if health["loaded_count"] < 9:
        print(f"    [FAIL] FAILED: Expected 9+ detectors, got {health['loaded_count']}")
        return False
    print(f"    [OK] All {health['loaded_count']} detectors loaded")

    # List loaded detectors
    print("\n[5] Loaded Detectors:")
    for i, detector_name in enumerate(health["loaded"], 1):
        marker = (
            "[NEW]"
            if detector_name
            in [
                "pivot_detector",
                "range_quality_scorer",
                "level_calculator",
                "zone_mapper",
            ]
            else "  "
        )
        print(f"    {i:2}. {marker} {detector_name}")

    # Test specific Story 11.9 detectors
    print("\n[6] Testing Story 11.9 Detectors:")

    story_119_detectors = {
        "pivot_detector": "PivotDetector (11.9a)",
        "range_quality_scorer": "RangeQualityScorer (11.9b)",
        "level_calculator": "LevelCalculator (11.9c)",
        "zone_mapper": "ZoneMapper (11.9d)",
    }

    all_passed = True
    for detector_key, detector_name in story_119_detectors.items():
        try:
            detector = getattr(container, detector_key)
            if detector is None:
                print(f"    [FAIL] {detector_name}: NOT LOADED")
                all_passed = False
            else:
                print(f"    [OK] {detector_name}: {type(detector).__name__}")
        except Exception as e:
            print(f"    [FAIL] {detector_name}: ERROR - {e}")
            all_passed = False

    # Final summary
    print("\n" + "=" * 70)
    if all_passed and health["status"] == "healthy" and health["loaded_count"] >= 9:
        print("VALIDATION RESULT: [OK] PASS")
        print(f"All {health['loaded_count']} detectors loaded successfully!")
        print("Orchestrator Status: HEALTHY")
        print("Story 11.9 Implementation: VERIFIED")
        print("=" * 70 + "\n")
        return True
    else:
        print("VALIDATION RESULT: [FAIL] FAIL")
        print("=" * 70 + "\n")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
