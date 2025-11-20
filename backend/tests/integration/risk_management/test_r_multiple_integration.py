"""
Integration tests for R-Multiple validation in signal generation workflow.

Tests cover:
- Signal rejection when R-multiple below minimum (AC 8)
- Signal annotation with R-multiple fields (AC 10)
- Warning but acceptance scenario (AC 5)
- Full validation workflow integration

Note: These are integration-style tests that verify the validation logic
integrates properly with signal models. Actual signal generator integration
will be tested when signal generators are modified to call validation.

Author: Story 7.6
"""

from decimal import Decimal

from src.risk_management.r_multiple import validate_r_multiple


class TestRMultipleRejectionFlow:
    """Test R-multiple rejection in signal flow (AC 8)."""

    def test_sos_r_multiple_rejection(self):
        """
        SOS with R=2.3 rejected despite meeting all other criteria.

        Setup:
        - Entry: $100.00
        - Stop: $95.00 (5% risk)
        - Target: $111.50
        - R-multiple: (111.50 - 100) / (100 - 95) = 11.5 / 5 = 2.3R
        - Pattern: SOS (minimum 2.5R required)

        Expected:
        - Validation fails
        - Rejection reason includes R-multiple and minimum requirement
        - Status = REJECTED
        """
        entry = Decimal("100.00")
        stop = Decimal("95.00")
        target = Decimal("111.50")

        validation = validate_r_multiple(
            entry=entry, stop=stop, target=target, pattern_type="SOS", symbol="TEST"
        )

        # Verify rejection
        assert validation.is_valid is False
        assert validation.status == "REJECTED"
        assert validation.r_multiple == Decimal("2.30")

        # Verify rejection reason contains context
        assert validation.rejection_reason is not None
        assert "2.3" in validation.rejection_reason
        assert "2.5" in validation.rejection_reason
        assert "SOS" in validation.rejection_reason

        # In actual integration, signal generator would:
        # 1. Call validate_r_multiple
        # 2. Check validation.is_valid
        # 3. If False, reject signal with validation.rejection_reason
        # 4. Log rejection with context

    def test_spring_r_multiple_rejection(self):
        """
        Spring with R=2.8R rejected (below 3.0R minimum).

        Setup:
        - Entry: $100.00
        - Stop: $95.00
        - Target: $114.00
        - R-multiple: 2.8R
        - Pattern: SPRING (minimum 3.0R required)
        """
        entry = Decimal("100.00")
        stop = Decimal("95.00")
        target = Decimal("114.00")

        validation = validate_r_multiple(
            entry=entry, stop=stop, target=target, pattern_type="SPRING", symbol="AAPL"
        )

        assert validation.is_valid is False
        assert validation.status == "REJECTED"
        assert validation.r_multiple == Decimal("2.80")
        assert "2.8" in validation.rejection_reason
        assert "3.0" in validation.rejection_reason

    def test_utad_short_r_multiple_rejection(self):
        """
        UTAD SHORT with R=3.2R rejected (below 3.5R minimum).

        SHORT trades require higher R-multiple due to asymmetric risk.
        """
        entry = Decimal("100.00")
        stop = Decimal("95.00")
        target = Decimal("116.00")

        validation = validate_r_multiple(
            entry=entry, stop=stop, target=target, pattern_type="UTAD", symbol="SPY"
        )

        # R = (116 - 100) / (100 - 95) = 16 / 5 = 3.2R
        assert validation.is_valid is False
        assert validation.r_multiple == Decimal("3.20")
        assert "3.2" in validation.rejection_reason
        assert "3.5" in validation.rejection_reason


class TestRMultipleAnnotation:
    """Test R-multiple annotation in Signal model (AC 10)."""

    def test_spring_signal_ideal_r_annotation(self):
        """
        Spring signal with R=4.0R includes proper annotation.

        Setup:
        - Entry: $100.00
        - Stop: $95.00
        - Target: $120.00
        - R-multiple: 4.0R (IDEAL for SPRING)

        Expected Signal Fields:
        - r_multiple: Decimal("4.00")
        - r_multiple_status: "IDEAL"
        - r_multiple_warning: None
        """
        entry = Decimal("100.00")
        stop = Decimal("95.00")
        target = Decimal("120.00")

        validation = validate_r_multiple(
            entry=entry, stop=stop, target=target, pattern_type="SPRING", symbol="AAPL"
        )

        # Verify validation result
        assert validation.is_valid is True
        assert validation.r_multiple == Decimal("4.00")
        assert validation.status == "IDEAL"
        assert validation.warning is None

        # In actual signal creation, these values would populate:
        # signal = SpringSignal(
        #     ...
        #     r_multiple=validation.r_multiple,
        #     r_multiple_status=validation.status,
        #     r_multiple_warning=validation.warning
        # )

    def test_sos_signal_acceptable_r_annotation(self):
        """
        SOS signal with R=3.0R (ACCEPTABLE but below ideal 3.5R).

        Expected:
        - r_multiple: Decimal("3.00")
        - r_multiple_status: "ACCEPTABLE"
        - r_multiple_warning: Warning message about being below ideal
        """
        entry = Decimal("100.00")
        stop = Decimal("95.00")
        target = Decimal("115.00")

        validation = validate_r_multiple(
            entry=entry, stop=stop, target=target, pattern_type="SOS", symbol="MSFT"
        )

        assert validation.is_valid is True
        assert validation.r_multiple == Decimal("3.00")
        assert validation.status == "ACCEPTABLE"
        assert validation.warning is not None
        assert "3.0" in validation.warning
        assert "3.5" in validation.warning

    def test_validation_result_serialization(self):
        """
        Verify RMultipleValidation serializes correctly to JSON.

        Signal API endpoints will return r_multiple fields in JSON response.
        """
        validation = validate_r_multiple(
            entry=Decimal("100.00"),
            stop=Decimal("95.00"),
            target=Decimal("120.00"),
            pattern_type="SPRING",
        )

        # Serialize to dict (mimics JSON response) - Pydantic already serializes Decimal to str
        serialized = validation.model_dump()

        assert serialized["is_valid"] is True
        # model_dump() uses model_serializer which converts Decimal to string
        assert serialized["r_multiple"] == "4.00"
        assert serialized["status"] == "IDEAL"
        assert serialized["rejection_reason"] is None
        assert serialized["warning"] is None

        # Verify model serializer converts Decimal to string
        json_serialized = validation.serialize_model()
        assert json_serialized["r_multiple"] == "4.00"
        assert isinstance(json_serialized["r_multiple"], str)


class TestWarningButAcceptanceScenario:
    """Test warning but acceptance scenario (AC 5)."""

    def test_spring_suboptimal_but_acceptable(self):
        """
        Spring with R=3.5R warns but allows signal creation.

        Setup:
        - Entry: $100.00
        - Stop: $95.00
        - Target: $117.50
        - R-multiple: 3.5R (above minimum 3.0R, below ideal 4.0R)

        Expected:
        - Signal created (not rejected)
        - r_multiple_status: "ACCEPTABLE"
        - r_multiple_warning: Contains warning message
        - Warning logged in structlog
        """
        entry = Decimal("100.00")
        stop = Decimal("95.00")
        target = Decimal("117.50")

        validation = validate_r_multiple(
            entry=entry, stop=stop, target=target, pattern_type="SPRING", symbol="GOOGL"
        )

        # Signal passes validation
        assert validation.is_valid is True
        assert validation.r_multiple == Decimal("3.50")

        # But includes warning
        assert validation.status == "ACCEPTABLE"
        assert validation.warning is not None
        assert "3.5" in validation.warning
        assert "4.0" in validation.warning
        assert "acceptable but suboptimal" in validation.warning

        # No rejection reason (signal allowed)
        assert validation.rejection_reason is None

    def test_lps_suboptimal_but_acceptable(self):
        """
        LPS with R=2.8R warns but allows signal.

        - Above minimum 2.5R
        - Below ideal 3.5R
        - Should warn but not reject
        """
        entry = Decimal("101.00")  # Ice + 1%
        stop = Decimal("97.00")  # Ice - 3%
        target = Decimal("112.20")

        validation = validate_r_multiple(
            entry=entry, stop=stop, target=target, pattern_type="LPS", symbol="NVDA"
        )

        # R = (112.20 - 101) / (101 - 97) = 11.2 / 4 = 2.8R
        assert validation.is_valid is True
        assert validation.r_multiple == Decimal("2.80")
        assert validation.status == "ACCEPTABLE"
        assert validation.warning is not None
        assert "2.8" in validation.warning

    def test_st_acceptable_with_warning(self):
        """
        ST (Secondary Test) with R=3.0R acceptable but warns.

        - Above minimum 2.5R
        - Below ideal 3.5R
        """
        validation = validate_r_multiple(
            entry=Decimal("100.00"),
            stop=Decimal("95.00"),
            target=Decimal("115.00"),
            pattern_type="ST",
        )

        assert validation.is_valid is True
        assert validation.r_multiple == Decimal("3.00")
        assert validation.status == "ACCEPTABLE"
        assert validation.warning is not None

    def test_utad_short_acceptable_with_warning(self):
        """
        UTAD SHORT with R=4.2R acceptable but warns (below ideal 5.0R).
        """
        validation = validate_r_multiple(
            entry=Decimal("100.00"),
            stop=Decimal("95.00"),
            target=Decimal("121.00"),
            pattern_type="UTAD",
        )

        # R = (121 - 100) / (100 - 95) = 21 / 5 = 4.2R
        assert validation.is_valid is True
        assert validation.r_multiple == Decimal("4.20")
        assert validation.status == "ACCEPTABLE"
        assert validation.warning is not None
        assert "4.2" in validation.warning
        assert "5.0" in validation.warning


class TestFullValidationWorkflow:
    """Test complete validation workflow integration."""

    def test_validation_workflow_ideal_path(self):
        """
        Test complete validation workflow for ideal setup.

        Workflow:
        1. Pattern detected with entry/stop/target
        2. R-multiple validation called
        3. Validation passes (IDEAL)
        4. Signal created with r_multiple annotation
        5. Signal proceeds to position sizing
        """
        # Step 1: Pattern provides prices
        entry = Decimal("150.00")
        stop = Decimal("145.00")
        target = Decimal("170.00")
        pattern_type = "SPRING"

        # Step 2: Validate R-multiple
        validation = validate_r_multiple(
            entry=entry, stop=stop, target=target, pattern_type=pattern_type, symbol="TSLA"
        )

        # Step 3: Verify IDEAL status
        # R = (170 - 150) / (150 - 145) = 20 / 5 = 4.0R
        assert validation.is_valid is True
        assert validation.r_multiple == Decimal("4.00")
        assert validation.status == "IDEAL"

        # Step 4: Signal creation (simulated)
        # signal = SpringSignal(
        #     entry_price=entry,
        #     stop_loss=stop,
        #     target_price=target,
        #     r_multiple=validation.r_multiple,
        #     r_multiple_status=validation.status,
        #     r_multiple_warning=validation.warning,
        #     ...
        # )

        # Step 5: Signal would proceed to position sizing

    def test_validation_workflow_rejection_path(self):
        """
        Test validation workflow when R-multiple fails.

        Workflow:
        1. Pattern detected with poor risk/reward
        2. R-multiple validation called
        3. Validation fails (below minimum)
        4. Signal rejected (not created)
        5. Rejection logged with context
        """
        # Step 1: Pattern with poor R-multiple
        entry = Decimal("100.00")
        stop = Decimal("95.00")
        target = Decimal("109.00")  # Only 1.8R
        pattern_type = "SOS"

        # Step 2: Validate R-multiple
        validation = validate_r_multiple(
            entry=entry, stop=stop, target=target, pattern_type=pattern_type, symbol="AMD"
        )

        # Step 3: Verify rejection
        assert validation.is_valid is False
        assert validation.status == "REJECTED"
        assert validation.rejection_reason is not None

        # Step 4: Signal not created
        # if not validation.is_valid:
        #     logger.error("signal_rejected", reason=validation.rejection_reason)
        #     return None

        # Step 5: Rejection logged (verified in validation function)

    def test_edge_case_unreasonable_r_workflow(self):
        """
        Test workflow with unreasonably high R-multiple.

        Scenario: Stop placed too tight, creating unrealistic R-multiple.
        """
        entry = Decimal("100.00")
        stop = Decimal("99.50")  # Only 0.5% risk (too tight)
        target = Decimal("160.00")  # 60% reward

        validation = validate_r_multiple(
            entry=entry, stop=stop, target=target, pattern_type="SPRING"
        )

        # R = 60 / 0.5 = 120R (unreasonable)
        assert validation.is_valid is False
        assert validation.status == "REJECTED"
        assert "unreasonably high" in validation.rejection_reason

    def test_multiple_pattern_validation_consistency(self):
        """
        Verify consistent validation across different pattern types.

        All patterns should use same validation logic but different thresholds.
        """
        # Fixed setup: entry=100, stop=95, target=115 -> R=3.0
        entry = Decimal("100.00")
        stop = Decimal("95.00")
        target = Decimal("115.00")

        # SPRING: 3.0R is ACCEPTABLE (min 3.0, ideal 4.0)
        spring_val = validate_r_multiple(entry, stop, target, "SPRING")
        assert spring_val.is_valid is True
        assert spring_val.status == "ACCEPTABLE"
        assert spring_val.warning is not None

        # SOS: 3.0R is ACCEPTABLE (min 2.5, ideal 3.5)
        sos_val = validate_r_multiple(entry, stop, target, "SOS")
        assert sos_val.is_valid is True
        assert sos_val.status == "ACCEPTABLE"
        assert sos_val.warning is not None

        # UTAD: 3.0R is REJECTED (min 3.5 for SHORT trades)
        utad_val = validate_r_multiple(entry, stop, target, "UTAD")
        assert utad_val.is_valid is False
        assert utad_val.status == "REJECTED"

        # All have same calculated R-multiple
        assert spring_val.r_multiple == sos_val.r_multiple == utad_val.r_multiple
