"""
Integration Tests for Audit Repository (Story 10.8)

Purpose:
--------
Test the AuditRepository with mock data to verify filtering, sorting,
pagination, and query logic.

Test Coverage:
--------------
- Query with various filter combinations
- Sorting by different columns
- Pagination logic (limit, offset, total_count)
- Full-text search functionality
- Validation chain generation
- Mock data structure integrity

Note:
-----
In production, this would test actual database queries with seeded test data.
For now, we test the repository's filtering/sorting logic with mock data.

Author: Story 10.8
"""

from datetime import UTC, datetime

import pytest

from src.models.audit import AuditLogQueryParams
from src.repositories.audit_repository import AuditRepository

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def repository() -> AuditRepository:
    """Create audit repository instance."""
    return AuditRepository()


# ============================================================================
# Basic Query Tests
# ============================================================================


def test_repository_get_audit_log_returns_data(repository: AuditRepository):
    """Test that repository returns audit log data."""
    params = AuditLogQueryParams()
    entries, total_count = repository.get_audit_log(params)

    assert isinstance(entries, list)
    assert isinstance(total_count, int)
    assert total_count >= 0
    assert len(entries) <= params.limit


def test_repository_audit_entries_have_required_fields(repository: AuditRepository):
    """Test that audit entries have all required fields."""
    params = AuditLogQueryParams(limit=1)
    entries, _ = repository.get_audit_log(params)

    if len(entries) > 0:
        entry = entries[0]

        # Check required fields
        assert entry.id is not None
        assert entry.timestamp is not None
        assert entry.symbol is not None
        assert entry.pattern_type is not None
        assert entry.phase is not None
        assert entry.confidence_score >= 70
        assert entry.confidence_score <= 95
        assert entry.status is not None
        assert entry.pattern_id is not None
        assert entry.validation_chain is not None
        assert entry.volume_ratio is not None
        assert entry.spread_ratio is not None


def test_repository_validation_chain_has_wyckoff_rules(repository: AuditRepository):
    """Test that validation chain steps include Wyckoff rule references."""
    params = AuditLogQueryParams(limit=1)
    entries, _ = repository.get_audit_log(params)

    if len(entries) > 0:
        entry = entries[0]
        if len(entry.validation_chain) > 0:
            step = entry.validation_chain[0]

            # Check Wyckoff rule reference exists and is valid
            assert step.wyckoff_rule_reference is not None
            valid_rules = [
                "Law #1: Supply & Demand",
                "Law #2: Cause & Effect",
                "Law #3: Effort vs Result",
                "Phase Progression",
                "Test Principle",
                "Wyckoff Schematics",
            ]
            assert step.wyckoff_rule_reference in valid_rules


# ============================================================================
# Filtering Tests
# ============================================================================


def test_repository_filter_by_symbol(repository: AuditRepository):
    """Test filtering by symbol."""
    params = AuditLogQueryParams(symbols=["AAPL"])
    entries, _ = repository.get_audit_log(params)

    # All entries should have symbol=AAPL
    for entry in entries:
        assert entry.symbol == "AAPL"


def test_repository_filter_by_multiple_symbols(repository: AuditRepository):
    """Test filtering by multiple symbols."""
    params = AuditLogQueryParams(symbols=["AAPL", "TSLA"])
    entries, _ = repository.get_audit_log(params)

    # All entries should have symbol in [AAPL, TSLA]
    for entry in entries:
        assert entry.symbol in ["AAPL", "TSLA"]


def test_repository_filter_by_pattern_type(repository: AuditRepository):
    """Test filtering by pattern type."""
    params = AuditLogQueryParams(pattern_types=["SPRING"])
    entries, _ = repository.get_audit_log(params)

    # All entries should have pattern_type=SPRING
    for entry in entries:
        assert entry.pattern_type == "SPRING"


def test_repository_filter_by_status(repository: AuditRepository):
    """Test filtering by status."""
    params = AuditLogQueryParams(statuses=["REJECTED"])
    entries, _ = repository.get_audit_log(params)

    # All entries should have status=REJECTED
    for entry in entries:
        assert entry.status == "REJECTED"


def test_repository_filter_by_confidence_range(repository: AuditRepository):
    """Test filtering by confidence range."""
    params = AuditLogQueryParams(min_confidence=80, max_confidence=90)
    entries, _ = repository.get_audit_log(params)

    # All entries should have confidence in [80, 90]
    for entry in entries:
        assert 80 <= entry.confidence_score <= 90


def test_repository_filter_by_date_range(repository: AuditRepository):
    """Test filtering by date range."""
    start_date = datetime(2024, 3, 15, 14, 0, 0, tzinfo=UTC)
    end_date = datetime(2024, 3, 15, 20, 0, 0, tzinfo=UTC)

    params = AuditLogQueryParams(start_date=start_date, end_date=end_date)
    entries, _ = repository.get_audit_log(params)

    # All entries should be within date range
    for entry in entries:
        assert start_date <= entry.timestamp <= end_date


def test_repository_combined_filters(repository: AuditRepository):
    """Test combining multiple filters."""
    params = AuditLogQueryParams(symbols=["AAPL"], pattern_types=["SPRING"], min_confidence=80)
    entries, _ = repository.get_audit_log(params)

    # All entries should match all filters
    for entry in entries:
        assert entry.symbol == "AAPL"
        assert entry.pattern_type == "SPRING"
        assert entry.confidence_score >= 80


# ============================================================================
# Search Tests
# ============================================================================


def test_repository_full_text_search(repository: AuditRepository):
    """Test full-text search functionality."""
    params = AuditLogQueryParams(search_text="AAPL")
    entries, _ = repository.get_audit_log(params)

    # Results should contain search text in at least one field
    for entry in entries:
        search_found = (
            "AAPL" in entry.symbol.upper()
            or "AAPL" in entry.pattern_type.upper()
            or "AAPL" in entry.phase.upper()
            or "AAPL" in entry.status.upper()
            or (entry.rejection_reason and "AAPL" in entry.rejection_reason.upper())
        )
        assert search_found


def test_repository_search_case_insensitive(repository: AuditRepository):
    """Test that search is case-insensitive."""
    params1 = AuditLogQueryParams(search_text="aapl")
    params2 = AuditLogQueryParams(search_text="AAPL")

    entries1, count1 = repository.get_audit_log(params1)
    entries2, count2 = repository.get_audit_log(params2)

    # Should return same results regardless of case
    assert count1 == count2


# ============================================================================
# Sorting Tests
# ============================================================================


def test_repository_sort_by_timestamp_desc(repository: AuditRepository):
    """Test sorting by timestamp descending."""
    params = AuditLogQueryParams(order_by="timestamp", order_direction="desc")
    entries, _ = repository.get_audit_log(params)

    # Check timestamps are in descending order
    timestamps = [e.timestamp for e in entries]
    assert timestamps == sorted(timestamps, reverse=True)


def test_repository_sort_by_timestamp_asc(repository: AuditRepository):
    """Test sorting by timestamp ascending."""
    params = AuditLogQueryParams(order_by="timestamp", order_direction="asc")
    entries, _ = repository.get_audit_log(params)

    # Check timestamps are in ascending order
    timestamps = [e.timestamp for e in entries]
    assert timestamps == sorted(timestamps)


def test_repository_sort_by_symbol(repository: AuditRepository):
    """Test sorting by symbol."""
    params = AuditLogQueryParams(order_by="symbol", order_direction="asc")
    entries, _ = repository.get_audit_log(params)

    # Check symbols are in ascending order
    symbols = [e.symbol for e in entries]
    assert symbols == sorted(symbols)


def test_repository_sort_by_confidence(repository: AuditRepository):
    """Test sorting by confidence score."""
    params = AuditLogQueryParams(order_by="confidence", order_direction="desc")
    entries, _ = repository.get_audit_log(params)

    # Check confidence scores are in descending order
    scores = [e.confidence_score for e in entries]
    assert scores == sorted(scores, reverse=True)


def test_repository_sort_by_status(repository: AuditRepository):
    """Test sorting by status."""
    params = AuditLogQueryParams(order_by="status", order_direction="asc")
    entries, _ = repository.get_audit_log(params)

    # Check statuses are in ascending order
    statuses = [e.status for e in entries]
    assert statuses == sorted(statuses)


# ============================================================================
# Pagination Tests
# ============================================================================


def test_repository_pagination_limit(repository: AuditRepository):
    """Test pagination with custom limit."""
    params = AuditLogQueryParams(limit=5)
    entries, total_count = repository.get_audit_log(params)

    assert len(entries) <= 5
    assert total_count >= len(entries)


def test_repository_pagination_offset(repository: AuditRepository):
    """Test pagination with offset."""
    # Get first page
    params1 = AuditLogQueryParams(limit=5, offset=0)
    entries1, total1 = repository.get_audit_log(params1)

    # Get second page
    params2 = AuditLogQueryParams(limit=5, offset=5)
    entries2, total2 = repository.get_audit_log(params2)

    # Total count should be same
    assert total1 == total2

    # Entries should be different (if enough data)
    if total1 > 5:
        assert entries1[0].id != entries2[0].id


def test_repository_pagination_total_count_accurate(repository: AuditRepository):
    """Test that total_count is accurate."""
    params = AuditLogQueryParams(limit=3)
    entries, total_count = repository.get_audit_log(params)

    # Get all data with high limit
    params_all = AuditLogQueryParams(limit=200)
    all_entries, _ = repository.get_audit_log(params_all)

    # Total count should match actual count
    assert total_count == len(all_entries)


def test_repository_pagination_beyond_data(repository: AuditRepository):
    """Test pagination with offset beyond available data."""
    params = AuditLogQueryParams(offset=10000)
    entries, total_count = repository.get_audit_log(params)

    # Should return empty list
    assert len(entries) == 0
    # But total count should still be accurate
    assert total_count >= 0


# ============================================================================
# Data Integrity Tests
# ============================================================================


def test_repository_rejected_patterns_have_rejection_reason(repository: AuditRepository):
    """Test that REJECTED patterns have rejection_reason."""
    params = AuditLogQueryParams(statuses=["REJECTED"])
    entries, _ = repository.get_audit_log(params)

    for entry in entries:
        if entry.status == "REJECTED":
            assert entry.rejection_reason is not None
            assert len(entry.rejection_reason) > 0


def test_repository_filled_patterns_have_prices(repository: AuditRepository):
    """Test that FILLED patterns have entry/target/stop prices."""
    params = AuditLogQueryParams(statuses=["FILLED"])
    entries, _ = repository.get_audit_log(params)

    for entry in entries:
        if entry.status == "FILLED":
            assert entry.entry_price is not None
            assert entry.target_price is not None
            assert entry.stop_loss is not None
            assert entry.r_multiple is not None


def test_repository_all_entries_have_validation_chain(repository: AuditRepository):
    """Test that all entries have validation chain."""
    params = AuditLogQueryParams()
    entries, _ = repository.get_audit_log(params)

    for entry in entries:
        assert entry.validation_chain is not None
        assert isinstance(entry.validation_chain, list)
        assert len(entry.validation_chain) > 0


# ============================================================================
# Count Method Tests
# ============================================================================


def test_repository_count_audit_log(repository: AuditRepository):
    """Test count_audit_log method."""
    params = AuditLogQueryParams()
    count = repository.count_audit_log(params)

    assert isinstance(count, int)
    assert count >= 0


def test_repository_count_matches_get(repository: AuditRepository):
    """Test that count_audit_log matches get_audit_log total_count."""
    params = AuditLogQueryParams(symbols=["AAPL"])

    count = repository.count_audit_log(params)
    _, total_count = repository.get_audit_log(params)

    assert count == total_count
