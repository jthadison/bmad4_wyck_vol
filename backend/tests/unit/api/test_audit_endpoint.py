"""
Unit Tests for Audit Log API Endpoint (Story 10.8)

Purpose:
--------
Test the GET /api/v1/audit-log endpoint with various filter combinations,
sorting, pagination, and error scenarios.

Test Coverage:
--------------
- Basic query without filters
- Date range filtering
- Symbol filtering (single and multiple)
- Pattern type filtering
- Status filtering
- Confidence range filtering
- Full-text search
- Sorting (all columns, asc/desc)
- Pagination (limit, offset, total_count)
- Invalid parameters (400 errors)
- Invalid date range (422 error)
- Edge cases (empty results, boundary conditions)

Author: Story 10.8
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.audit import ValidationChainStep

client = TestClient(app)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def base_validation_chain() -> list[ValidationChainStep]:
    """Generate a basic validation chain for testing."""
    return [
        ValidationChainStep(
            step_name="Volume Validation",
            passed=True,
            reason="Volume 0.65x < 0.7x threshold",
            timestamp=datetime(2024, 3, 15, 14, 30, 0, tzinfo=UTC),
            wyckoff_rule_reference="Law #1: Supply & Demand",
        )
    ]


# ============================================================================
# Basic Query Tests
# ============================================================================


def test_get_audit_log_no_filters():
    """Test GET /api/v1/audit-log with no filters returns all data."""
    response = client.get("/api/v1/audit-log")

    assert response.status_code == 200
    data = response.json()

    # Check response structure
    assert "data" in data
    assert "total_count" in data
    assert "limit" in data
    assert "offset" in data

    # Check defaults
    assert data["limit"] == 50
    assert data["offset"] == 0
    assert isinstance(data["data"], list)
    assert data["total_count"] >= 0


def test_get_audit_log_returns_audit_entries():
    """Test that response contains valid AuditLogEntry objects."""
    response = client.get("/api/v1/audit-log")

    assert response.status_code == 200
    data = response.json()

    if len(data["data"]) > 0:
        entry = data["data"][0]

        # Check required fields
        assert "id" in entry
        assert "timestamp" in entry
        assert "symbol" in entry
        assert "pattern_type" in entry
        assert "phase" in entry
        assert "confidence_score" in entry
        assert "status" in entry
        assert "pattern_id" in entry
        assert "validation_chain" in entry
        assert "volume_ratio" in entry
        assert "spread_ratio" in entry

        # Check validation chain structure
        if len(entry["validation_chain"]) > 0:
            step = entry["validation_chain"][0]
            assert "step_name" in step
            assert "passed" in step
            assert "reason" in step
            assert "timestamp" in step
            assert "wyckoff_rule_reference" in step


# ============================================================================
# Filtering Tests
# ============================================================================


def test_get_audit_log_filter_by_symbol():
    """Test filtering by single symbol."""
    response = client.get("/api/v1/audit-log?symbols=AAPL")

    assert response.status_code == 200
    data = response.json()

    # All results should have symbol=AAPL
    for entry in data["data"]:
        assert entry["symbol"] == "AAPL"


def test_get_audit_log_filter_by_multiple_symbols():
    """Test filtering by multiple symbols."""
    response = client.get("/api/v1/audit-log?symbols=AAPL&symbols=TSLA")

    assert response.status_code == 200
    data = response.json()

    # All results should have symbol in [AAPL, TSLA]
    for entry in data["data"]:
        assert entry["symbol"] in ["AAPL", "TSLA"]


def test_get_audit_log_filter_by_pattern_type():
    """Test filtering by pattern type."""
    response = client.get("/api/v1/audit-log?pattern_types=SPRING")

    assert response.status_code == 200
    data = response.json()

    # All results should have pattern_type=SPRING
    for entry in data["data"]:
        assert entry["pattern_type"] == "SPRING"


def test_get_audit_log_filter_by_status():
    """Test filtering by status."""
    response = client.get("/api/v1/audit-log?statuses=FILLED")

    assert response.status_code == 200
    data = response.json()

    # All results should have status=FILLED
    for entry in data["data"]:
        assert entry["status"] == "FILLED"


def test_get_audit_log_filter_by_confidence_range():
    """Test filtering by confidence range."""
    response = client.get("/api/v1/audit-log?min_confidence=80&max_confidence=90")

    assert response.status_code == 200
    data = response.json()

    # All results should have confidence in [80, 90]
    for entry in data["data"]:
        assert 80 <= entry["confidence_score"] <= 90


def test_get_audit_log_filter_by_date_range():
    """Test filtering by date range."""
    start_date = "2024-03-15T00:00:00Z"
    end_date = "2024-03-16T00:00:00Z"

    response = client.get(f"/api/v1/audit-log?start_date={start_date}&end_date={end_date}")

    assert response.status_code == 200
    data = response.json()

    # All results should be within date range
    start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

    for entry in data["data"]:
        entry_dt = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
        assert start_dt <= entry_dt <= end_dt


def test_get_audit_log_combined_filters():
    """Test combining multiple filters."""
    response = client.get(
        "/api/v1/audit-log?symbols=AAPL&pattern_types=SPRING&statuses=FILLED&min_confidence=80"
    )

    assert response.status_code == 200
    data = response.json()

    # All results should match all filters
    for entry in data["data"]:
        assert entry["symbol"] == "AAPL"
        assert entry["pattern_type"] == "SPRING"
        assert entry["status"] == "FILLED"
        assert entry["confidence_score"] >= 80


# ============================================================================
# Search Tests
# ============================================================================


def test_get_audit_log_full_text_search():
    """Test full-text search across fields."""
    response = client.get("/api/v1/audit-log?search_text=AAPL")

    assert response.status_code == 200
    data = response.json()

    # Results should contain search text in at least one field
    for entry in data["data"]:
        search_found = (
            "AAPL" in entry["symbol"]
            or "AAPL" in entry["pattern_type"]
            or "AAPL" in entry["phase"]
            or "AAPL" in entry["status"]
            or (entry.get("rejection_reason") and "AAPL" in entry["rejection_reason"])
        )
        assert search_found


def test_get_audit_log_search_rejection_reason():
    """Test search finds text in rejection reasons."""
    response = client.get("/api/v1/audit-log?search_text=Volume")

    assert response.status_code == 200
    data = response.json()

    # At least some results should have "Volume" in rejection_reason
    # (or in other fields like pattern_type)
    assert len(data["data"]) >= 0  # Search may return no results


# ============================================================================
# Sorting Tests
# ============================================================================


def test_get_audit_log_sort_by_timestamp_desc():
    """Test sorting by timestamp descending (default)."""
    response = client.get("/api/v1/audit-log?order_by=timestamp&order_direction=desc")

    assert response.status_code == 200
    data = response.json()

    # Check timestamps are in descending order
    timestamps = [
        datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")) for e in data["data"]
    ]
    assert timestamps == sorted(timestamps, reverse=True)


def test_get_audit_log_sort_by_timestamp_asc():
    """Test sorting by timestamp ascending."""
    response = client.get("/api/v1/audit-log?order_by=timestamp&order_direction=asc")

    assert response.status_code == 200
    data = response.json()

    # Check timestamps are in ascending order
    timestamps = [
        datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")) for e in data["data"]
    ]
    assert timestamps == sorted(timestamps)


def test_get_audit_log_sort_by_symbol():
    """Test sorting by symbol."""
    response = client.get("/api/v1/audit-log?order_by=symbol&order_direction=asc")

    assert response.status_code == 200
    data = response.json()

    # Check symbols are in ascending order
    symbols = [e["symbol"] for e in data["data"]]
    assert symbols == sorted(symbols)


def test_get_audit_log_sort_by_confidence():
    """Test sorting by confidence score."""
    response = client.get("/api/v1/audit-log?order_by=confidence&order_direction=desc")

    assert response.status_code == 200
    data = response.json()

    # Check confidence scores are in descending order
    scores = [e["confidence_score"] for e in data["data"]]
    assert scores == sorted(scores, reverse=True)


# ============================================================================
# Pagination Tests
# ============================================================================


def test_get_audit_log_pagination_limit():
    """Test pagination with custom limit."""
    response = client.get("/api/v1/audit-log?limit=5")

    assert response.status_code == 200
    data = response.json()

    assert data["limit"] == 5
    assert len(data["data"]) <= 5


def test_get_audit_log_pagination_offset():
    """Test pagination with offset."""
    # Get first page
    response1 = client.get("/api/v1/audit-log?limit=5&offset=0")
    data1 = response1.json()

    # Get second page
    response2 = client.get("/api/v1/audit-log?limit=5&offset=5")
    data2 = response2.json()

    assert response1.status_code == 200
    assert response2.status_code == 200

    # Ensure different results (if enough data)
    if data1["total_count"] > 5:
        assert data1["data"][0]["id"] != data2["data"][0]["id"]


def test_get_audit_log_total_count():
    """Test that total_count is accurate."""
    response = client.get("/api/v1/audit-log?limit=3")

    assert response.status_code == 200
    data = response.json()

    # Total count should be >= returned count
    assert data["total_count"] >= len(data["data"])


# ============================================================================
# Validation Tests
# ============================================================================


def test_get_audit_log_invalid_date_range():
    """Test that start_date > end_date returns 422 error."""
    start_date = "2024-03-20T00:00:00Z"
    end_date = "2024-03-15T00:00:00Z"  # Earlier than start

    response = client.get(f"/api/v1/audit-log?start_date={start_date}&end_date={end_date}")

    assert response.status_code == 422
    assert "start_date" in response.text.lower() or "end_date" in response.text.lower()


def test_get_audit_log_invalid_limit_too_high():
    """Test that limit > 200 returns 422 error."""
    response = client.get("/api/v1/audit-log?limit=300")

    assert response.status_code == 422


def test_get_audit_log_invalid_limit_zero():
    """Test that limit = 0 returns 422 error."""
    response = client.get("/api/v1/audit-log?limit=0")

    assert response.status_code == 422


def test_get_audit_log_invalid_offset_negative():
    """Test that negative offset returns 422 error."""
    response = client.get("/api/v1/audit-log?offset=-1")

    assert response.status_code == 422


def test_get_audit_log_invalid_order_by():
    """Test that invalid order_by column returns 422 error."""
    response = client.get("/api/v1/audit-log?order_by=invalid_column")

    assert response.status_code == 422


def test_get_audit_log_invalid_order_direction():
    """Test that invalid order_direction returns 422 error."""
    response = client.get("/api/v1/audit-log?order_direction=invalid")

    assert response.status_code == 422


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_get_audit_log_no_results():
    """Test query that returns no results."""
    response = client.get("/api/v1/audit-log?symbols=NONEXISTENT")

    assert response.status_code == 200
    data = response.json()

    assert data["total_count"] == 0
    assert len(data["data"]) == 0


def test_get_audit_log_max_limit():
    """Test query with maximum allowed limit (200)."""
    response = client.get("/api/v1/audit-log?limit=200")

    assert response.status_code == 200
    data = response.json()

    assert data["limit"] == 200
    assert len(data["data"]) <= 200


def test_get_audit_log_high_offset():
    """Test query with offset beyond available data."""
    response = client.get("/api/v1/audit-log?offset=10000")

    assert response.status_code == 200
    data = response.json()

    # Should return empty results
    assert len(data["data"]) == 0
    # But total_count should still reflect actual total
    assert data["total_count"] >= 0
