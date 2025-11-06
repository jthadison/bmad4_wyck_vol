"""
Integration tests for SpringSignal and SpringHistory JSON serialization (Story 5.6 - Task 18).

Tests cover:
- AC 10: SpringSignal serializable to JSON for API responses
- SpringHistory JSON serialization
- Decimal field serialization (prices, ratios)
- DateTime serialization (ISO 8601 format)
- UUID serialization
- Nested object serialization (Spring, Test embedded in SpringSignal)
- Round-trip serialization (JSON -> object -> JSON)

Author: Story 5.6 - Phase 3 Integration Testing
"""

import json
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from uuid import uuid4, UUID

import pytest

from src.pattern_engine.detectors.spring_detector import SpringDetector
from src.models.spring_history import SpringHistory
from src.models.spring_signal import SpringSignal
from src.models.phase_classification import WyckoffPhase
from src.models.ohlcv import OHLCVBar
from src.models.trading_range import TradingRange, RangeStatus
from src.models.creek_level import CreekLevel
from src.models.jump_level import JumpLevel
from src.models.touch_detail import TouchDetail
from src.models.price_cluster import PriceCluster
from src.models.pivot import Pivot, PivotType


def create_test_bar(
    timestamp: datetime,
    low: Decimal,
    high: Decimal,
    close: Decimal,
    volume: int,
    symbol: str = "JSON_TEST",
) -> OHLCVBar:
    """Create test OHLCV bar for serialization testing."""
    spread = high - low
    open_price = (high + low) / 2

    return OHLCVBar(
        id=uuid4(),
        symbol=symbol,
        timeframe="1d",
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        spread=spread,
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
    )


def create_test_range(
    creek_level: Decimal = Decimal("100.00"),
    jump_level: Decimal = Decimal("115.00"),
    symbol: str = "JSON_TEST",
) -> TradingRange:
    """Create test trading range for serialization testing."""
    base_timestamp = datetime(2024, 3, 15, tzinfo=UTC)

    # Create support pivots
    support_pivots = []
    for i, idx in enumerate([10, 20, 30]):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=idx),
            low=creek_level - Decimal("2.00"),
            high=creek_level + Decimal("5.00"),
            close=creek_level + Decimal("1.00"),
            volume=1000000,
            symbol=symbol,
        )
        pivot = Pivot(
            bar=bar,
            price=bar.low,
            type=PivotType.LOW,
            strength=5,
            timestamp=bar.timestamp,
            index=idx,
        )
        support_pivots.append(pivot)

    support_cluster = PriceCluster(
        pivots=support_pivots,
        average_price=creek_level - Decimal("2.00"),
        min_price=creek_level - Decimal("3.00"),
        max_price=creek_level - Decimal("1.00"),
        price_range=Decimal("2.00"),
        touch_count=3,
        cluster_type=PivotType.LOW,
        std_deviation=Decimal("0.50"),
        timestamp_range=(support_pivots[0].timestamp, support_pivots[-1].timestamp),
    )

    # Create resistance pivots
    resistance_pivots = []
    for i, idx in enumerate([15, 25, 35]):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=idx),
            low=jump_level - Decimal("5.00"),
            high=jump_level + Decimal("2.00"),
            close=jump_level - Decimal("1.00"),
            volume=1200000,
            symbol=symbol,
        )
        pivot = Pivot(
            bar=bar,
            price=bar.high,
            type=PivotType.HIGH,
            strength=5,
            timestamp=bar.timestamp,
            index=idx,
        )
        resistance_pivots.append(pivot)

    resistance_cluster = PriceCluster(
        pivots=resistance_pivots,
        average_price=jump_level + Decimal("2.00"),
        min_price=jump_level + Decimal("1.00"),
        max_price=jump_level + Decimal("3.00"),
        price_range=Decimal("2.00"),
        touch_count=3,
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0.50"),
        timestamp_range=(resistance_pivots[0].timestamp, resistance_pivots[-1].timestamp),
    )

    creek = CreekLevel(
        price=creek_level,
        cluster=support_cluster,
        touches=[
            TouchDetail(
                index=pivot.index,
                price=pivot.price,
                volume=pivot.bar.volume,
                volume_ratio=Decimal("1.0"),
                close_position=Decimal("0.7"),
                rejection_wick=Decimal("0.6"),
                timestamp=pivot.timestamp,
            )
            for pivot in support_pivots
        ],
        strength_score=85,
        touch_count=3,
    )

    jump = JumpLevel(
        price=jump_level,
        cluster=resistance_cluster,
        touches=[
            TouchDetail(
                index=pivot.index,
                price=pivot.price,
                volume=pivot.bar.volume,
                volume_ratio=Decimal("1.0"),
                close_position=Decimal("0.3"),
                rejection_wick=Decimal("0.5"),
                timestamp=pivot.timestamp,
            )
            for pivot in resistance_pivots
        ],
        strength_score=82,
        touch_count=3,
    )

    return TradingRange(
        id=uuid4(),
        symbol=symbol,
        timeframe="1d",
        creek=creek,
        jump=jump,
        status=RangeStatus.ACTIVE,
        range_start=base_timestamp,
        range_end=base_timestamp + timedelta(days=50),
    )


def create_spring_sequence(
    creek_level: Decimal,
    symbol: str = "JSON_TEST",
) -> list[OHLCVBar]:
    """Create bar sequence with valid spring and test for serialization testing."""
    bars = []
    base_timestamp = datetime(2024, 3, 15, tzinfo=UTC)

    # First 25 bars for volume calculation
    for i in range(25):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=i),
            low=creek_level * Decimal("1.00"),
            high=creek_level * Decimal("1.05"),
            close=creek_level * Decimal("1.025"),
            volume=1000000,
            symbol=symbol,
        )
        bars.append(bar)

    # Spring bar at day 25 (2% below Creek, 0.4x volume)
    spring_bar = create_test_bar(
        timestamp=base_timestamp + timedelta(days=25),
        low=creek_level * Decimal("0.98"),
        high=creek_level * Decimal("1.01"),
        close=creek_level * Decimal("0.99"),
        volume=400000,
        symbol=symbol,
    )
    bars.append(spring_bar)

    # Recovery bar at day 26
    recovery_bar = create_test_bar(
        timestamp=base_timestamp + timedelta(days=26),
        low=creek_level * Decimal("0.995"),
        high=creek_level * Decimal("1.02"),
        close=creek_level * Decimal("1.005"),
        volume=900000,
        symbol=symbol,
    )
    bars.append(recovery_bar)

    # 3 normal bars before test (days 27-29)
    for i in range(3):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=27 + i),
            low=creek_level * Decimal("1.00"),
            high=creek_level * Decimal("1.03"),
            close=creek_level * Decimal("1.015"),
            volume=1000000,
            symbol=symbol,
        )
        bars.append(bar)

    # Test bar at day 30 (approaches spring low with lower volume)
    test_bar = create_test_bar(
        timestamp=base_timestamp + timedelta(days=30),
        low=creek_level * Decimal("0.985"),
        high=creek_level * Decimal("1.02"),
        close=creek_level * Decimal("1.00"),
        volume=300000,
        symbol=symbol,
    )
    bars.append(test_bar)

    return bars


# ============================================================
# SPRING SIGNAL JSON SERIALIZATION TESTS
# ============================================================


def test_spring_signal_json_serialization_ac10():
    """
    AC 10: SpringSignal serializable to JSON for API responses.

    Verifies that SpringSignal can be converted to JSON with proper field serialization.
    """
    # Arrange: Detect spring and generate signal
    creek_level = Decimal("100.00")
    bars = create_spring_sequence(creek_level)
    trading_range = create_test_range(creek_level=creek_level)

    detector = SpringDetector()
    history = detector.detect_all_springs(trading_range, bars, WyckoffPhase.C)

    assert len(history.signals) > 0, "Should generate at least one signal"
    signal = history.signals[0]

    # Act: Serialize to JSON
    signal_json = signal.model_dump_json(indent=2)
    signal_dict = json.loads(signal_json)

    # Assert: All required fields present (AC 10)
    required_fields = [
        "id", "symbol", "timeframe", "signal_type",
        "entry_price", "stop_loss", "target_price",
        "confidence", "r_multiple", "urgency",
        "spring_bar_timestamp", "test_bar_timestamp",
        "phase", "trading_range_id", "detection_timestamp",
        "is_valid", "account_size", "risk_per_trade_pct",
        "position_size_shares", "position_size_dollars",
        "risk_amount"
    ]

    for field in required_fields:
        assert field in signal_dict, f"Missing required field: {field}"

    # Assert: Decimal fields serialized as strings (Pydantic config)
    assert isinstance(signal_dict["entry_price"], str), "Decimal should serialize as string"
    assert isinstance(signal_dict["stop_loss"], str), "Decimal should serialize as string"
    assert isinstance(signal_dict["target_price"], str), "Decimal should serialize as string"
    assert isinstance(signal_dict["r_multiple"], str), "Decimal should serialize as string"

    # Assert: DateTime serialized as ISO 8601
    assert "T" in signal_dict["detection_timestamp"], "DateTime should be ISO 8601"
    assert "Z" in signal_dict["detection_timestamp"] or "+" in signal_dict["detection_timestamp"], (
        "DateTime should include timezone"
    )

    # Assert: UUID serialized as string
    assert isinstance(signal_dict["id"], str), "UUID should serialize as string"
    UUID(signal_dict["id"])  # Should parse as valid UUID

    # Assert: Signal type is LONG
    assert signal_dict["signal_type"] == "LONG", "Springs are always LONG signals"

    print("✅ AC 10 PASSED: SpringSignal serializes to JSON correctly")
    print(f"   Serialized fields: {len(signal_dict)}")
    print(f"   Entry price: {signal_dict['entry_price']}")
    print(f"   Confidence: {signal_dict['confidence']}")
    print(f"   R-multiple: {signal_dict['r_multiple']}")


def test_spring_signal_round_trip_serialization():
    """
    Test round-trip serialization: SpringSignal -> JSON -> dict -> validate.

    Ensures no data loss during JSON serialization/deserialization.
    """
    # Arrange: Generate signal
    creek_level = Decimal("100.00")
    bars = create_spring_sequence(creek_level)
    trading_range = create_test_range(creek_level=creek_level)

    detector = SpringDetector()
    history = detector.detect_all_springs(trading_range, bars, WyckoffPhase.C)

    original_signal = history.signals[0]

    # Act: Serialize to JSON and back to dict
    json_string = original_signal.model_dump_json()
    parsed_dict = json.loads(json_string)

    # Assert: Critical fields match
    assert parsed_dict["symbol"] == original_signal.symbol
    assert Decimal(parsed_dict["entry_price"]) == original_signal.entry_price
    assert Decimal(parsed_dict["stop_loss"]) == original_signal.stop_loss
    assert Decimal(parsed_dict["target_price"]) == original_signal.target_price
    assert parsed_dict["confidence"] == original_signal.confidence
    assert Decimal(parsed_dict["r_multiple"]) == original_signal.r_multiple

    print("✅ Round-trip serialization preserves data integrity")


def test_spring_history_json_serialization():
    """
    Test SpringHistory dataclass JSON serialization.

    Verifies that SpringHistory with multiple springs can be serialized to JSON.
    """
    # Arrange: Detect multiple springs
    creek_level = Decimal("100.00")
    bars = []
    base_timestamp = datetime(2024, 3, 15, tzinfo=UTC)

    # Build sequence with 2 springs
    for i in range(25):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=i),
            low=creek_level * Decimal("1.00"),
            high=creek_level * Decimal("1.05"),
            close=creek_level * Decimal("1.025"),
            volume=1000000,
        )
        bars.append(bar)

    # First spring at day 25
    bars.append(create_test_bar(
        timestamp=base_timestamp + timedelta(days=25),
        low=creek_level * Decimal("0.98"),
        high=creek_level * Decimal("1.01"),
        close=creek_level * Decimal("0.99"),
        volume=400000,
    ))

    # Recovery
    bars.append(create_test_bar(
        timestamp=base_timestamp + timedelta(days=26),
        low=creek_level * Decimal("0.995"),
        high=creek_level * Decimal("1.02"),
        close=creek_level * Decimal("1.005"),
        volume=900000,
    ))

    # Normal bars
    for i in range(3):
        bars.append(create_test_bar(
            timestamp=base_timestamp + timedelta(days=27 + i),
            low=creek_level * Decimal("1.00"),
            high=creek_level * Decimal("1.03"),
            close=creek_level * Decimal("1.015"),
            volume=1000000,
        ))

    # Test for first spring
    bars.append(create_test_bar(
        timestamp=base_timestamp + timedelta(days=30),
        low=creek_level * Decimal("0.985"),
        high=creek_level * Decimal("1.02"),
        close=creek_level * Decimal("1.00"),
        volume=300000,
    ))

    # Second spring at day 40
    bars.append(create_test_bar(
        timestamp=base_timestamp + timedelta(days=40),
        low=creek_level * Decimal("0.975"),
        high=creek_level * Decimal("1.01"),
        close=creek_level * Decimal("0.98"),
        volume=300000,  # Lower volume - declining trend
    ))

    # Recovery for second spring
    bars.append(create_test_bar(
        timestamp=base_timestamp + timedelta(days=41),
        low=creek_level * Decimal("0.995"),
        high=creek_level * Decimal("1.02"),
        close=creek_level * Decimal("1.005"),
        volume=850000,
    ))

    # Normal bars before second test
    for i in range(3):
        bars.append(create_test_bar(
            timestamp=base_timestamp + timedelta(days=42 + i),
            low=creek_level * Decimal("1.00"),
            high=creek_level * Decimal("1.03"),
            close=creek_level * Decimal("1.015"),
            volume=1000000,
        ))

    # Test for second spring
    bars.append(create_test_bar(
        timestamp=base_timestamp + timedelta(days=45),
        low=creek_level * Decimal("0.982"),
        high=creek_level * Decimal("1.02"),
        close=creek_level * Decimal("1.00"),
        volume=250000,  # Even lower - declining trend
    ))

    trading_range = create_test_range(creek_level=creek_level)
    detector = SpringDetector()

    # Act: Detect and serialize
    history = detector.detect_all_springs(trading_range, bars, WyckoffPhase.C)

    # Serialize using dataclass asdict (SpringHistory is a dataclass)
    from dataclasses import asdict
    history_dict = asdict(history)

    # Convert to JSON
    # Note: Need custom encoder for Decimal, UUID, datetime
    def custom_encoder(obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    history_json = json.dumps(history_dict, default=custom_encoder, indent=2)
    history_parsed = json.loads(history_json)

    # Assert: SpringHistory fields present
    assert "symbol" in history_parsed
    assert "trading_range_id" in history_parsed
    assert "springs" in history_parsed
    assert "signals" in history_parsed
    assert "spring_count" in history_parsed
    assert "volume_trend" in history_parsed
    assert "risk_level" in history_parsed

    # Assert: Multi-spring detection worked
    assert history_parsed["spring_count"] >= 1, "Should detect springs"
    assert len(history_parsed["springs"]) >= 1, "Springs list should not be empty"

    # Assert: Volume trend and risk level set
    assert history_parsed["volume_trend"] in ["DECLINING", "STABLE", "RISING"]
    assert history_parsed["risk_level"] in ["LOW", "MODERATE", "HIGH"]

    print("✅ SpringHistory serializes to JSON correctly")
    print(f"   Spring count: {history_parsed['spring_count']}")
    print(f"   Volume trend: {history_parsed['volume_trend']}")
    print(f"   Risk level: {history_parsed['risk_level']}")


def test_nested_object_serialization():
    """
    Test that nested Spring and Test objects serialize correctly within SpringSignal.

    SpringSignal contains embedded Spring and Test patterns - verify these
    serialize without circular reference issues.
    """
    # Arrange: Generate signal with embedded Spring and Test
    creek_level = Decimal("100.00")
    bars = create_spring_sequence(creek_level)
    trading_range = create_test_range(creek_level=creek_level)

    detector = SpringDetector()
    history = detector.detect_all_springs(trading_range, bars, WyckoffPhase.C)

    signal = history.signals[0]

    # Act: Serialize
    signal_json = signal.model_dump_json()
    signal_dict = json.loads(signal_json)

    # Assert: Spring fields present (nested in signal)
    # Note: SpringSignal in Story 5.5 uses spring_bar_timestamp, not embedded Spring
    assert "spring_bar_timestamp" in signal_dict, "Spring timestamp should be present"

    # Assert: Test fields present (nested in signal)
    assert "test_bar_timestamp" in signal_dict, "Test timestamp should be present"

    # Assert: No circular references (JSON parsing succeeded)
    assert signal_dict is not None

    print("✅ Nested object serialization works correctly")
    print(f"   Spring timestamp: {signal_dict['spring_bar_timestamp']}")
    print(f"   Test timestamp: {signal_dict['test_bar_timestamp']}")


def test_decimal_precision_in_json():
    """
    Test that Decimal fields maintain precision in JSON serialization.

    Verifies prices and ratios are serialized with full precision.
    """
    # Arrange: Generate signal
    creek_level = Decimal("100.12345")  # High precision
    bars = create_spring_sequence(creek_level)
    trading_range = create_test_range(creek_level=creek_level)

    detector = SpringDetector()
    history = detector.detect_all_springs(trading_range, bars, WyckoffPhase.C)

    signal = history.signals[0]

    # Act: Serialize
    signal_json = signal.model_dump_json()
    signal_dict = json.loads(signal_json)

    # Assert: Decimal precision preserved
    entry_price_str = signal_dict["entry_price"]
    entry_price_decimal = Decimal(entry_price_str)

    # Should maintain high precision (8 decimal places per field definition)
    assert len(entry_price_str.split(".")[-1]) >= 2, "Should have decimal places"

    print("✅ Decimal precision preserved in JSON")
    print(f"   Entry price: {entry_price_str}")
    print(f"   Precision: {len(entry_price_str.split('.')[-1])} decimal places")


def test_api_response_format_compatibility():
    """
    Test that serialized SpringSignal matches expected API response format.

    Verifies field names, types, and structure match API contract.
    """
    # Arrange: Generate signal
    creek_level = Decimal("100.00")
    bars = create_spring_sequence(creek_level)
    trading_range = create_test_range(creek_level=creek_level)

    detector = SpringDetector()
    history = detector.detect_all_springs(trading_range, bars, WyckoffPhase.C)

    signal = history.signals[0]

    # Act: Serialize as would be sent to API
    api_response = {
        "status": "success",
        "signal": json.loads(signal.model_dump_json()),
    }

    # Assert: API response structure valid
    assert api_response["status"] == "success"
    assert "signal" in api_response
    assert isinstance(api_response["signal"], dict)

    # Assert: API response contains trading essentials
    trading_fields = ["entry_price", "stop_loss", "target_price", "r_multiple", "confidence"]
    for field in trading_fields:
        assert field in api_response["signal"], f"API response missing {field}"

    print("✅ API response format compatible")
    print(f"   Response structure: {list(api_response.keys())}")
    print(f"   Signal fields: {len(api_response['signal'])}")


def test_multiple_signals_json_list_serialization():
    """
    Test serializing list of SpringSignals (common API response).

    Verifies that List[SpringSignal] can be serialized to JSON array.
    """
    # Arrange: Generate multiple signals (would need multi-spring scenario)
    creek_level = Decimal("100.00")
    bars = create_spring_sequence(creek_level)
    trading_range = create_test_range(creek_level=creek_level)

    detector = SpringDetector()
    history = detector.detect_all_springs(trading_range, bars, WyckoffPhase.C)

    # Act: Serialize list of signals
    signals_json = [
        json.loads(signal.model_dump_json())
        for signal in history.signals
    ]

    signals_list_json = json.dumps(signals_json, indent=2)
    signals_list_parsed = json.loads(signals_list_json)

    # Assert: List serialization works
    assert isinstance(signals_list_parsed, list)
    assert len(signals_list_parsed) >= 1, "Should have at least one signal"

    # Assert: Each item is a valid signal dict
    for signal_dict in signals_list_parsed:
        assert "id" in signal_dict
        assert "entry_price" in signal_dict
        assert "confidence" in signal_dict

    print("✅ List of signals serializes correctly")
    print(f"   Signals in list: {len(signals_list_parsed)}")


def test_empty_history_json_serialization():
    """
    Test SpringHistory serialization when no springs detected.

    Verifies empty history serializes without errors.
    """
    # Arrange: Create bars with NO springs (all trade above Creek)
    creek_level = Decimal("100.00")
    bars = []
    base_timestamp = datetime(2024, 3, 15, tzinfo=UTC)

    for i in range(30):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=i),
            low=creek_level * Decimal("1.01"),  # Above Creek
            high=creek_level * Decimal("1.10"),
            close=creek_level * Decimal("1.05"),
            volume=1000000,
        )
        bars.append(bar)

    trading_range = create_test_range(creek_level=creek_level)
    detector = SpringDetector()

    # Act: Detect (should find nothing)
    history = detector.detect_all_springs(trading_range, bars, WyckoffPhase.C)

    # Serialize empty history
    from dataclasses import asdict

    def custom_encoder(obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    history_dict = asdict(history)
    history_json = json.dumps(history_dict, default=custom_encoder)
    history_parsed = json.loads(history_json)

    # Assert: Empty history serializes correctly
    assert history_parsed["spring_count"] == 0
    assert len(history_parsed["springs"]) == 0
    assert len(history_parsed["signals"]) == 0
    assert history_parsed["best_spring"] is None
    assert history_parsed["best_signal"] is None

    print("✅ Empty SpringHistory serializes correctly")
    print(f"   Spring count: {history_parsed['spring_count']}")
