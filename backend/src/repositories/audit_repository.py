"""
Audit Log Repository (Story 10.8)

Purpose:
--------
Repository for querying audit log data - aggregates pattern detections and signals
to provide complete audit trail with filtering, sorting, and pagination.

This is a mock implementation since Pattern/Signal database tables don't exist yet.
When those tables are created, this repository will query them via LEFT JOIN.

Query Strategy:
---------------
Future implementation will use:

SELECT
    p.id, p.detection_time, p.symbol, p.pattern_type,
    p.phase, p.confidence_score,
    COALESCE(s.status, CASE WHEN p.rejection_reason IS NOT NULL
                        THEN 'REJECTED' ELSE 'PENDING' END) as status,
    p.rejection_reason, s.id as signal_id,
    p.entry_price, p.target_price, p.stop_loss,
    s.r_multiple, p.volume_ratio, p.spread_ratio,
    p.metadata  -- Contains validation_chain JSON
FROM patterns p
LEFT JOIN signals s ON p.id = s.pattern_id
WHERE [filters]
ORDER BY [sort]
LIMIT [limit] OFFSET [offset]

Performance:
------------
- Composite index: (detection_time DESC, symbol, pattern_type, confidence_score)
- Index on signals: (pattern_id, status)
- Target: <500ms query time for 10,000+ patterns

Integration:
------------
- Story 10.8: Audit log endpoint
- GET /api/v1/audit-log with filtering/sorting/pagination

Author: Story 10.8
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from src.models.audit import AuditLogEntry, AuditLogQueryParams, ValidationChainStep


class AuditRepository:
    """
    Repository for audit log queries.

    Provides methods to query pattern detections and signals with filtering,
    sorting, full-text search, and pagination.

    Methods:
    --------
    - get_audit_log: Query audit log with filters and pagination
    - count_audit_log: Count total results for pagination
    """

    def __init__(self):
        """Initialize audit repository."""
        # Mock data for demonstration
        self._mock_data = self._generate_mock_data()

    def _generate_mock_data(self) -> list[AuditLogEntry]:
        """
        Generate mock audit log data for demonstration.

        In production, this will be replaced with actual database queries.
        """
        base_timestamp = datetime(2024, 3, 15, 14, 30, 0, tzinfo=UTC)
        mock_entries = []

        # Mock data: Mix of FILLED, REJECTED, and PENDING signals
        patterns = [
            ("AAPL", "SPRING", "C", 85, "FILLED", None),
            ("TSLA", "SOS", "D", 82, "TARGET_HIT", None),
            ("MSFT", "SPRING", "C", 78, "REJECTED", "Volume ratio 0.75x > 0.7x threshold"),
            ("NVDA", "LPS", "D", 88, "FILLED", None),
            ("AAPL", "UTAD", "D", 75, "REJECTED", "Phase mismatch: UTAD requires Phase C"),
            ("GOOGL", "SPRING", "C", 90, "APPROVED", None),
            ("META", "SOS", "D", 84, "PENDING", None),
            ("AMZN", "SPRING", "C", 72, "STOPPED", None),
            ("NFLX", "LPS", "D", 86, "EXPIRED", None),
            ("AMD", "SPRING", "C", 80, "REJECTED", "Test confirmation failed: only 2 bars"),
        ]

        for i, (symbol, pattern, phase, confidence, status, rejection) in enumerate(patterns):
            timestamp = base_timestamp.replace(hour=14 + i, minute=30)
            pattern_id = str(uuid4())
            signal_id = str(uuid4()) if status != "REJECTED" else None

            # Generate validation chain based on status
            validation_chain = self._generate_validation_chain(status, rejection)

            entry = AuditLogEntry(
                id=signal_id if signal_id else pattern_id,
                timestamp=timestamp,
                symbol=symbol,
                pattern_type=pattern,  # type: ignore
                phase=phase,  # type: ignore
                confidence_score=confidence,
                status=status,  # type: ignore
                rejection_reason=rejection,
                signal_id=signal_id,
                pattern_id=pattern_id,
                validation_chain=validation_chain,
                entry_price=Decimal("150.00") if status != "REJECTED" else None,
                target_price=Decimal("156.00") if status != "REJECTED" else None,
                stop_loss=Decimal("148.00") if status != "REJECTED" else None,
                r_multiple=Decimal("3.0") if status != "REJECTED" else None,
                volume_ratio=Decimal("0.65") if status != "REJECTED" else Decimal("0.75"),
                spread_ratio=Decimal("0.85"),
            )
            mock_entries.append(entry)

        return mock_entries

    def _generate_validation_chain(
        self, status: str, rejection_reason: Optional[str]
    ) -> list[ValidationChainStep]:
        """Generate mock validation chain based on status."""
        base_timestamp = datetime(2024, 3, 15, 14, 30, 0, tzinfo=UTC)

        if status == "REJECTED" and rejection_reason:
            # Failed validation
            if "Volume" in rejection_reason:
                return [
                    ValidationChainStep(
                        step_name="Volume Validation",
                        passed=False,
                        reason=rejection_reason,
                        timestamp=base_timestamp,
                        wyckoff_rule_reference="Law #1: Supply & Demand",
                    )
                ]
            elif "Phase" in rejection_reason:
                return [
                    ValidationChainStep(
                        step_name="Volume Validation",
                        passed=True,
                        reason="Volume 0.65x < 0.7x threshold",
                        timestamp=base_timestamp,
                        wyckoff_rule_reference="Law #1: Supply & Demand",
                    ),
                    ValidationChainStep(
                        step_name="Phase Validation",
                        passed=False,
                        reason=rejection_reason,
                        timestamp=base_timestamp.replace(second=1),
                        wyckoff_rule_reference="Phase Progression",
                    ),
                ]
            elif "Test confirmation" in rejection_reason:
                return [
                    ValidationChainStep(
                        step_name="Volume Validation",
                        passed=True,
                        reason="Volume 0.65x < 0.7x threshold",
                        timestamp=base_timestamp,
                        wyckoff_rule_reference="Law #1: Supply & Demand",
                    ),
                    ValidationChainStep(
                        step_name="Phase Validation",
                        passed=True,
                        reason="Pattern in Phase C as required",
                        timestamp=base_timestamp.replace(second=1),
                        wyckoff_rule_reference="Phase Progression",
                    ),
                    ValidationChainStep(
                        step_name="Test Confirmation",
                        passed=False,
                        reason=rejection_reason,
                        timestamp=base_timestamp.replace(second=2),
                        wyckoff_rule_reference="Test Principle",
                    ),
                ]

        # All passed
        return [
            ValidationChainStep(
                step_name="Volume Validation",
                passed=True,
                reason="Volume 0.65x < 0.7x threshold",
                timestamp=base_timestamp,
                wyckoff_rule_reference="Law #1: Supply & Demand",
            ),
            ValidationChainStep(
                step_name="Phase Validation",
                passed=True,
                reason="Pattern in Phase C as required",
                timestamp=base_timestamp.replace(second=1),
                wyckoff_rule_reference="Phase Progression",
            ),
            ValidationChainStep(
                step_name="Test Confirmation",
                passed=True,
                reason="Test confirmed after 5 bars",
                timestamp=base_timestamp.replace(second=2),
                wyckoff_rule_reference="Test Principle",
            ),
            ValidationChainStep(
                step_name="Spread Validation",
                passed=True,
                reason="Spread 0.85x indicates absorption",
                timestamp=base_timestamp.replace(second=3),
                wyckoff_rule_reference="Law #3: Effort vs Result",
            ),
            ValidationChainStep(
                step_name="Price Structure",
                passed=True,
                reason="Price structure follows Wyckoff accumulation schematic",
                timestamp=base_timestamp.replace(second=4),
                wyckoff_rule_reference="Wyckoff Schematics",
            ),
        ]

    def get_audit_log(self, params: AuditLogQueryParams) -> tuple[list[AuditLogEntry], int]:
        """
        Query audit log with filtering, sorting, and pagination.

        Args:
            params: Query parameters (filters, sort, pagination)

        Returns:
            Tuple of (filtered/sorted/paginated entries, total count)

        Example:
            >>> repo = AuditRepository()
            >>> params = AuditLogQueryParams(
            ...     symbols=["AAPL"],
            ...     pattern_types=["SPRING"],
            ...     limit=50,
            ...     offset=0
            ... )
            >>> entries, total = repo.get_audit_log(params)
        """
        filtered_data = self._mock_data.copy()

        # Apply filters
        if params.start_date:
            filtered_data = [e for e in filtered_data if e.timestamp >= params.start_date]

        if params.end_date:
            filtered_data = [e for e in filtered_data if e.timestamp <= params.end_date]

        if params.symbols:
            filtered_data = [e for e in filtered_data if e.symbol in params.symbols]

        if params.pattern_types:
            filtered_data = [e for e in filtered_data if e.pattern_type in params.pattern_types]

        if params.statuses:
            filtered_data = [e for e in filtered_data if e.status in params.statuses]

        if params.min_confidence is not None:
            filtered_data = [
                e for e in filtered_data if e.confidence_score >= params.min_confidence
            ]

        if params.max_confidence is not None:
            filtered_data = [
                e for e in filtered_data if e.confidence_score <= params.max_confidence
            ]

        # Full-text search
        if params.search_text:
            search_lower = params.search_text.lower()
            filtered_data = [
                e
                for e in filtered_data
                if search_lower in e.symbol.lower()
                or search_lower in e.pattern_type.lower()
                or search_lower in e.phase.lower()
                or search_lower in e.status.lower()
                or (e.rejection_reason and search_lower in e.rejection_reason.lower())
            ]

        # Get total count before pagination
        total_count = len(filtered_data)

        # Sorting
        reverse = params.order_direction == "desc"
        if params.order_by == "timestamp":
            filtered_data.sort(key=lambda e: e.timestamp, reverse=reverse)
        elif params.order_by == "symbol":
            filtered_data.sort(key=lambda e: e.symbol, reverse=reverse)
        elif params.order_by == "pattern_type":
            filtered_data.sort(key=lambda e: e.pattern_type, reverse=reverse)
        elif params.order_by == "confidence":
            filtered_data.sort(key=lambda e: e.confidence_score, reverse=reverse)
        elif params.order_by == "status":
            filtered_data.sort(key=lambda e: e.status, reverse=reverse)

        # Pagination
        paginated_data = filtered_data[params.offset : params.offset + params.limit]

        return paginated_data, total_count

    def count_audit_log(self, params: AuditLogQueryParams) -> int:
        """
        Count total results matching filters (for pagination).

        Args:
            params: Query parameters (filters only)

        Returns:
            Total number of results matching filters
        """
        _, total_count = self.get_audit_log(params)
        return total_count
