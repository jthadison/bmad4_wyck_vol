"""
Tests for Story 25.7: Enforce 70% Confidence Floor Before Signal Emission.

This test module validates that the 70% confidence floor is correctly enforced
after all penalties are applied, and that signals with insufficient evidence are rejected.

Acceptance Criteria Coverage:
- AC1: Signal with confidence=60 after penalties → rejected, log shows actual value
- AC2: Signal with confidence=70 → NOT rejected
- AC3: Rejection log includes pattern_type, computed_confidence, base, penalty
- AC4: Floor applied after penalties (base=85, penalty=-25 → check 60, not 85)
- AC5: No volume_ratio → rejected (not assigned arbitrary 75)
"""

from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from src.orchestrator.orchestrator_facade import CONFIDENCE_FLOOR, _TradeSignalGenerator
from src.orchestrator.pipeline.context import PipelineContext


@pytest.fixture
def signal_generator():
    """Create a _TradeSignalGenerator instance for testing."""
    return _TradeSignalGenerator()


@pytest.fixture
def mock_context():
    """Create a mock PipelineContext."""
    context = Mock(spec=PipelineContext)
    context.symbol = "AAPL"
    context.timeframe = "1h"
    # Mock get method to return None for validation_results
    context.get = Mock(return_value=None)
    return context


@pytest.fixture
def base_pattern():
    """Create a base pattern object with required attributes."""
    pattern = Mock()
    pattern.id = uuid4()
    pattern.pattern_type = "SOS"
    pattern.symbol = "AAPL"
    pattern.timeframe = "1h"
    pattern.entry_price = Decimal("100.00")
    pattern.stop_loss = Decimal("95.00")
    pattern.target_price = Decimal("110.00")
    pattern.confidence = None  # Will be derived
    pattern.volume_ratio = Decimal("2.0")  # High volume
    pattern.session_confidence_penalty = 0  # Default: no penalty
    pattern.is_tradeable = True
    pattern.recommended_position_size = Decimal("100")
    pattern.campaign_id = None
    pattern.phase = None
    return pattern


class TestConfidenceFloorEnforcement:
    """Test that the 70% confidence floor is correctly enforced."""

    @pytest.mark.parametrize(
        "base_confidence,session_penalty,expected_result",
        [
            # AC1: Below floor → rejected
            (75, -25, "REJECTED"),  # Final: 50
            (70, -10, "REJECTED"),  # Final: 60
            (69, 0, "REJECTED"),    # Final: 69

            # AC2: At floor → accepted
            (70, 0, "PASSED"),      # Final: 70

            # Above floor → accepted
            (71, 0, "PASSED"),      # Final: 71
            (85, 0, "PASSED"),      # Final: 85
            (85, -10, "PASSED"),    # Final: 75
            (95, 0, "PASSED"),      # Final: 95
            (100, -5, "PASSED"),    # Final: 95 (capped)
        ],
    )
    @patch("src.orchestrator.orchestrator_facade.logger")
    async def test_confidence_floor_with_various_values(
        self,
        mock_logger,
        signal_generator,
        base_pattern,
        mock_context,
        base_confidence,
        session_penalty,
        expected_result,
    ):
        """
        Test confidence floor enforcement with various confidence values.

        AC1: confidence < 70 → rejected
        AC2: confidence = 70 → accepted
        Boundary tests: 69, 70, 71
        """
        # Set up pattern with specific confidence and penalty
        base_pattern.confidence = base_confidence
        base_pattern.session_confidence_penalty = session_penalty
        base_pattern.volume_ratio = None  # Use explicit confidence, not derived

        final_confidence = base_confidence + session_penalty

        # Generate signal
        result = await signal_generator.generate_signal(base_pattern, None, mock_context)

        if expected_result == "REJECTED":
            # Signal should be rejected
            assert result is None

            # AC3: Verify rejection log contains required fields
            mock_logger.warning.assert_called_once()
            call_kwargs = mock_logger.warning.call_args[1]
            assert call_kwargs["pattern_type"] == "SOS"
            assert call_kwargs["computed_confidence"] == final_confidence
            assert call_kwargs["base_confidence"] == base_confidence
            assert call_kwargs["session_penalty"] == session_penalty
            assert call_kwargs["confidence_floor"] == CONFIDENCE_FLOOR

        else:  # PASSED
            # Signal should be generated successfully
            assert result is not None
            assert result.confidence_score == min(95, final_confidence)
            # Should not log rejection warning
            warning_calls = [
                call for call in mock_logger.warning.call_args_list
                if call[1].get("computed_confidence") is not None
            ]
            assert len(warning_calls) == 0


    @patch("src.orchestrator.orchestrator_facade.logger")
    async def test_ac4_penalty_applied_before_floor_check(
        self,
        mock_logger,
        signal_generator,
        base_pattern,
        mock_context,
    ):
        """
        AC4: Floor check happens AFTER penalties, not before.

        SOS ASIAN scenario: base=85, penalty=-25 → final=60
        Floor should check 60 (with penalty), not 85 (without penalty).
        Signal should be REJECTED because 60 < 70.
        """
        # Simulate SOS ASIAN: good base confidence but harsh session penalty
        base_pattern.confidence = 85
        base_pattern.session_confidence_penalty = -25  # ASIAN session
        base_pattern.volume_ratio = None  # Use explicit confidence

        # Generate signal
        result = await signal_generator.generate_signal(base_pattern, None, mock_context)

        # Should be rejected because final_confidence (60) < 70
        assert result is None

        # Verify log shows final confidence (60), not base (85)
        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args[1]
        assert call_kwargs["computed_confidence"] == 60
        assert call_kwargs["base_confidence"] == 85
        assert call_kwargs["session_penalty"] == -25
        assert "60" in call_kwargs["detail"]


    @patch("src.orchestrator.orchestrator_facade.logger")
    async def test_ac5_no_volume_ratio_rejects_signal(
        self,
        mock_logger,
        signal_generator,
        base_pattern,
        mock_context,
    ):
        """
        AC5: When volume_ratio is unavailable and no confidence is set,
        signal is rejected (NOT assigned arbitrary fallback of 75).
        """
        # Pattern with no confidence and no volume_ratio
        base_pattern.confidence = None
        base_pattern.volume_ratio = None
        base_pattern.session_confidence_penalty = 0

        # Generate signal
        result = await signal_generator.generate_signal(base_pattern, None, mock_context)

        # Should be rejected due to insufficient evidence
        assert result is None

        # Verify rejection log mentions insufficient evidence
        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args[1]
        assert "insufficient" in call_kwargs["detail"].lower()
        assert "volume_ratio unavailable" in call_kwargs["detail"]
        # Ensure 75 is NOT mentioned (no arbitrary fallback)
        assert "75" not in str(call_kwargs)


    @patch("src.orchestrator.orchestrator_facade.logger")
    async def test_volume_ratio_derived_confidence_with_penalty(
        self,
        mock_logger,
        signal_generator,
        base_pattern,
        mock_context,
    ):
        """
        Test that volume_ratio-derived confidence works correctly with penalties.

        Spring patterns derive confidence from volume_ratio.
        Lower volume_ratio → higher confidence (quality signal).
        """
        # Spring pattern with very low volume (high quality)
        base_pattern.pattern_type = "SPRING"
        base_pattern.confidence = None  # Will be derived
        base_pattern.volume_ratio = Decimal("0.35")  # Mid-range → ~82 confidence
        base_pattern.session_confidence_penalty = -15  # Some penalty

        # Expected: base ~82, penalty -15 → final ~67 → REJECTED
        # Calculation: 95 - (0.35/0.7)*25 = 95 - 12.5 = 82.5 → 82
        # Final: 82 - 15 = 67 < 70 → rejected

        result = await signal_generator.generate_signal(base_pattern, None, mock_context)

        # Should be rejected
        assert result is None

        # Verify derived confidence was calculated, then penalty applied
        call_kwargs = mock_logger.warning.call_args[1]
        assert call_kwargs["session_penalty"] == -15
        assert call_kwargs["computed_confidence"] < CONFIDENCE_FLOOR


    @patch("src.orchestrator.orchestrator_facade.logger")
    async def test_volume_ratio_derived_confidence_passes_floor(
        self,
        mock_logger,
        signal_generator,
        base_pattern,
        mock_context,
    ):
        """Test volume_ratio-derived confidence that passes the floor."""
        # Spring pattern with low volume (high quality)
        base_pattern.pattern_type = "SPRING"
        base_pattern.confidence = None  # Will be derived
        base_pattern.volume_ratio = Decimal("0.1")  # Very low → ~91 confidence
        base_pattern.session_confidence_penalty = -5  # Minor penalty

        # Expected: base ~91, penalty -5 → final ~86 → PASSED
        # Calculation: 95 - (0.1/0.7)*25 = 95 - 3.57 = 91.43 → 91
        # Final: 91 - 5 = 86 > 70 → passed

        result = await signal_generator.generate_signal(base_pattern, None, mock_context)

        # Should pass
        assert result is not None
        # Final confidence should be ~86
        assert 85 <= result.confidence_score <= 87


    @patch("src.orchestrator.orchestrator_facade.logger")
    async def test_boundary_exact_floor_value(
        self,
        mock_logger,
        signal_generator,
        base_pattern,
        mock_context,
    ):
        """Test boundary: exactly 70% confidence should PASS."""
        base_pattern.confidence = 70
        base_pattern.session_confidence_penalty = 0
        base_pattern.volume_ratio = None

        result = await signal_generator.generate_signal(base_pattern, None, mock_context)

        # Should pass at exactly 70
        assert result is not None
        assert result.confidence_score == 70


    @patch("src.orchestrator.orchestrator_facade.logger")
    async def test_confidence_capped_at_95(
        self,
        mock_logger,
        signal_generator,
        base_pattern,
        mock_context,
    ):
        """Test that confidence is capped at 95 even if calculated higher."""
        base_pattern.confidence = 100
        base_pattern.session_confidence_penalty = 5  # Boost (unusual but possible)
        base_pattern.volume_ratio = None

        result = await signal_generator.generate_signal(base_pattern, None, mock_context)

        # Should pass but capped at 95
        assert result is not None
        assert result.confidence_score == 95


    @patch("src.orchestrator.orchestrator_facade.logger")
    async def test_no_session_penalty_attribute(
        self,
        mock_logger,
        signal_generator,
        base_pattern,
        mock_context,
    ):
        """Test pattern without session_confidence_penalty attribute (defaults to 0)."""
        base_pattern.confidence = 75
        # Remove session_confidence_penalty attribute entirely
        if hasattr(base_pattern, "session_confidence_penalty"):
            delattr(base_pattern, "session_confidence_penalty")
        base_pattern.volume_ratio = None

        result = await signal_generator.generate_signal(base_pattern, None, mock_context)

        # Should pass with confidence 75 (no penalty applied)
        assert result is not None
        assert result.confidence_score == 75


class TestRejectionLogging:
    """Test that rejection logs contain all required diagnostic information."""

    @patch("src.orchestrator.orchestrator_facade.logger")
    async def test_ac3_rejection_log_completeness(
        self,
        mock_logger,
        signal_generator,
        base_pattern,
        mock_context,
    ):
        """
        AC3: Rejection log includes pattern_type, computed_confidence,
        base_confidence, session_penalty — specific enough to trace penalty chain.
        """
        base_pattern.confidence = 80
        base_pattern.session_confidence_penalty = -20
        base_pattern.volume_ratio = None
        base_pattern.pattern_type = "LPS"

        result = await signal_generator.generate_signal(base_pattern, None, mock_context)

        assert result is None

        # Verify all required fields in log
        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args[1]

        # Required fields for tracing penalty chain
        assert "pattern_type" in call_kwargs
        assert call_kwargs["pattern_type"] == "LPS"

        assert "computed_confidence" in call_kwargs
        assert call_kwargs["computed_confidence"] == 60

        assert "base_confidence" in call_kwargs
        assert call_kwargs["base_confidence"] == 80

        assert "session_penalty" in call_kwargs
        assert call_kwargs["session_penalty"] == -20

        assert "confidence_floor" in call_kwargs
        assert call_kwargs["confidence_floor"] == CONFIDENCE_FLOOR

        # Detail message should be informative
        assert "detail" in call_kwargs
        assert "60" in call_kwargs["detail"]
        assert str(CONFIDENCE_FLOOR) in call_kwargs["detail"]


    @patch("src.orchestrator.orchestrator_facade.logger")
    async def test_insufficient_evidence_log(
        self,
        mock_logger,
        signal_generator,
        base_pattern,
        mock_context,
    ):
        """Test that insufficient evidence rejection log is clear."""
        base_pattern.confidence = None
        base_pattern.volume_ratio = None
        base_pattern.pattern_type = "SPRING"

        result = await signal_generator.generate_signal(base_pattern, None, mock_context)

        assert result is None

        # Verify insufficient evidence log
        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args[1]

        assert call_kwargs["pattern_type"] == "SPRING"
        assert "insufficient" in call_kwargs["detail"].lower()
        assert "volume_ratio" in call_kwargs["detail"]


class TestEdgeCases:
    """Test edge cases and unusual scenarios."""

    @patch("src.orchestrator.orchestrator_facade.logger")
    async def test_negative_base_confidence(
        self,
        mock_logger,
        signal_generator,
        base_pattern,
        mock_context,
    ):
        """Test handling of negative base confidence (should reject)."""
        base_pattern.confidence = -10
        base_pattern.session_confidence_penalty = 0
        base_pattern.volume_ratio = None

        result = await signal_generator.generate_signal(base_pattern, None, mock_context)

        # Should be rejected
        assert result is None


    @patch("src.orchestrator.orchestrator_facade.logger")
    async def test_zero_confidence(
        self,
        mock_logger,
        signal_generator,
        base_pattern,
        mock_context,
    ):
        """Test handling of zero confidence (should reject)."""
        base_pattern.confidence = 0
        base_pattern.session_confidence_penalty = 0
        base_pattern.volume_ratio = None

        result = await signal_generator.generate_signal(base_pattern, None, mock_context)

        # Should be rejected
        assert result is None


    @patch("src.orchestrator.orchestrator_facade.logger")
    async def test_large_positive_penalty(
        self,
        mock_logger,
        signal_generator,
        base_pattern,
        mock_context,
    ):
        """Test handling of large positive penalty (boost)."""
        base_pattern.confidence = 60
        base_pattern.session_confidence_penalty = 20  # Boost
        base_pattern.volume_ratio = None

        result = await signal_generator.generate_signal(base_pattern, None, mock_context)

        # Should pass: 60 + 20 = 80 > 70
        assert result is not None
        assert result.confidence_score == 80


    @patch("src.orchestrator.orchestrator_facade.logger")
    async def test_volume_ratio_at_boundaries(
        self,
        mock_logger,
        signal_generator,
        base_pattern,
        mock_context,
    ):
        """Test volume_ratio at validator boundaries."""
        # volume_ratio = 0 → confidence = 95 (max)
        base_pattern.confidence = None
        base_pattern.volume_ratio = Decimal("0.0")
        base_pattern.session_confidence_penalty = 0

        result = await signal_generator.generate_signal(base_pattern, None, mock_context)

        assert result is not None
        assert result.confidence_score == 95

        # volume_ratio = 0.7 → confidence = 70 (min before floor)
        base_pattern.volume_ratio = Decimal("0.7")

        result = await signal_generator.generate_signal(base_pattern, None, mock_context)

        assert result is not None
        assert result.confidence_score == 70
