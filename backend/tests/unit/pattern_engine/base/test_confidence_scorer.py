"""
Unit tests for ConfidenceScorer abstract base class.

Tests verify:
1. Abstract class cannot be instantiated directly
2. Property validation (asset_class, volume_reliability, max_confidence)
3. Concrete implementations must implement all abstract methods
4. __repr__ formatting

Author: Story 0.1 - Asset-Class Base Interfaces
"""

from typing import Optional

import pytest

from src.models.creek_level import CreekLevel
from src.models.lps import LPS
from src.models.phase_classification import PhaseClassification
from src.models.sos_breakout import SOSBreakout
from src.models.spring import Spring
from src.models.spring_confidence import SpringConfidence
from src.models.test import Test
from src.models.trading_range import TradingRange
from src.pattern_engine.base.confidence_scorer import (
    VALID_ASSET_CLASSES,
    VALID_RELIABILITY,
    ConfidenceScorer,
)


class TestConfidenceScorerAbstraction:
    """Test that ConfidenceScorer is properly abstract and cannot be instantiated."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """
        Test that ConfidenceScorer cannot be instantiated directly.

        The abstract base class should raise TypeError when attempting
        direct instantiation since it has abstract methods.
        """
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            ConfidenceScorer(
                asset_class="stock",
                volume_reliability="HIGH",
                max_confidence=100,
            )

    def test_abstract_methods_defined(self) -> None:
        """
        Test that abstract methods are properly defined.

        Verify the abstract methods exist and are marked as abstract.
        """
        abstract_methods = ConfidenceScorer.__abstractmethods__
        assert "calculate_spring_confidence" in abstract_methods
        assert "calculate_sos_confidence" in abstract_methods


class TestPropertyValidation:
    """Test validation of asset_class, volume_reliability, and max_confidence."""

    def test_invalid_asset_class_raises_error(self) -> None:
        """
        Test that invalid asset_class raises ValueError.

        Asset class must be one of: "stock", "forex", "futures", "crypto"
        """

        # Create minimal concrete implementation for testing validation
        class TestScorer(ConfidenceScorer):
            def calculate_spring_confidence(
                self,
                spring: Spring,
                creek: CreekLevel,
                previous_tests: list[Test] | None = None,
            ) -> SpringConfidence:
                raise NotImplementedError

            def calculate_sos_confidence(
                self,
                sos: SOSBreakout,
                lps: Optional[LPS],
                range_: TradingRange,
                phase: PhaseClassification,
            ) -> int:
                raise NotImplementedError

        # Test invalid asset class
        with pytest.raises(ValueError, match="Invalid asset_class"):
            TestScorer(
                asset_class="commodities",  # INVALID
                volume_reliability="HIGH",
                max_confidence=100,
            )

        # Verify error message includes valid options
        with pytest.raises(ValueError) as exc_info:
            TestScorer(
                asset_class="invalid",
                volume_reliability="HIGH",
                max_confidence=100,
            )
        assert str(VALID_ASSET_CLASSES) in str(exc_info.value)

    def test_invalid_volume_reliability_raises_error(self) -> None:
        """
        Test that invalid volume_reliability raises ValueError.

        Volume reliability must be one of: "HIGH", "MEDIUM", "LOW"
        """

        class TestScorer(ConfidenceScorer):
            def calculate_spring_confidence(
                self,
                spring: Spring,
                creek: CreekLevel,
                previous_tests: list[Test] | None = None,
            ) -> SpringConfidence:
                raise NotImplementedError

            def calculate_sos_confidence(
                self,
                sos: SOSBreakout,
                lps: Optional[LPS],
                range_: TradingRange,
                phase: PhaseClassification,
            ) -> int:
                raise NotImplementedError

        # Test invalid reliability
        with pytest.raises(ValueError, match="Invalid volume_reliability"):
            TestScorer(
                asset_class="stock",
                volume_reliability="VERY_HIGH",  # INVALID
                max_confidence=100,
            )

        # Verify error message includes valid options
        with pytest.raises(ValueError) as exc_info:
            TestScorer(
                asset_class="stock",
                volume_reliability="invalid",
                max_confidence=100,
            )
        assert str(VALID_RELIABILITY) in str(exc_info.value)

    def test_invalid_max_confidence_raises_error(self) -> None:
        """
        Test that invalid max_confidence raises ValueError.

        Max confidence must be between 1 and 100.
        """

        class TestScorer(ConfidenceScorer):
            def calculate_spring_confidence(
                self,
                spring: Spring,
                creek: CreekLevel,
                previous_tests: list[Test] | None = None,
            ) -> SpringConfidence:
                raise NotImplementedError

            def calculate_sos_confidence(
                self,
                sos: SOSBreakout,
                lps: Optional[LPS],
                range_: TradingRange,
                phase: PhaseClassification,
            ) -> int:
                raise NotImplementedError

        # Test max_confidence = 0 (too low)
        with pytest.raises(ValueError, match="Invalid max_confidence"):
            TestScorer(
                asset_class="stock",
                volume_reliability="HIGH",
                max_confidence=0,  # INVALID
            )

        # Test max_confidence = 101 (too high)
        with pytest.raises(ValueError, match="Invalid max_confidence"):
            TestScorer(
                asset_class="stock",
                volume_reliability="HIGH",
                max_confidence=101,  # INVALID
            )

        # Test negative max_confidence
        with pytest.raises(ValueError, match="Invalid max_confidence"):
            TestScorer(
                asset_class="stock",
                volume_reliability="HIGH",
                max_confidence=-10,  # INVALID
            )

    def test_valid_properties_accepted(self) -> None:
        """
        Test that valid property values are accepted.

        All valid combinations of asset_class, volume_reliability,
        and max_confidence should be accepted.
        """

        class TestScorer(ConfidenceScorer):
            def calculate_spring_confidence(
                self,
                spring: Spring,
                creek: CreekLevel,
                previous_tests: list[Test] | None = None,
            ) -> SpringConfidence:
                raise NotImplementedError

            def calculate_sos_confidence(
                self,
                sos: SOSBreakout,
                lps: Optional[LPS],
                range_: TradingRange,
                phase: PhaseClassification,
            ) -> int:
                raise NotImplementedError

        # Test all valid asset classes
        for asset_class in VALID_ASSET_CLASSES:
            scorer = TestScorer(
                asset_class=asset_class,
                volume_reliability="HIGH",
                max_confidence=100,
            )
            assert scorer.asset_class == asset_class

        # Test all valid reliability levels
        for reliability in VALID_RELIABILITY:
            scorer = TestScorer(
                asset_class="stock",
                volume_reliability=reliability,
                max_confidence=100,
            )
            assert scorer.volume_reliability == reliability

        # Test boundary max_confidence values
        for max_conf in [1, 50, 85, 90, 95, 100]:
            scorer = TestScorer(
                asset_class="stock",
                volume_reliability="HIGH",
                max_confidence=max_conf,
            )
            assert scorer.max_confidence == max_conf


class TestConcreteImplementationContract:
    """Test that concrete implementations must implement all abstract methods."""

    def test_missing_calculate_spring_confidence_raises_error(self) -> None:
        """
        Test that omitting calculate_spring_confidence raises TypeError.

        Concrete implementations MUST implement all abstract methods.
        """

        # Incomplete implementation (missing calculate_spring_confidence)
        class IncompleteScorer(ConfidenceScorer):
            def calculate_sos_confidence(
                self,
                sos: SOSBreakout,
                lps: Optional[LPS],
                range_: TradingRange,
                phase: PhaseClassification,
            ) -> int:
                return 85

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteScorer(
                asset_class="stock",
                volume_reliability="HIGH",
                max_confidence=100,
            )

    def test_missing_calculate_sos_confidence_raises_error(self) -> None:
        """
        Test that omitting calculate_sos_confidence raises TypeError.

        Concrete implementations MUST implement all abstract methods.
        """

        # Incomplete implementation (missing calculate_sos_confidence)
        class IncompleteScorer(ConfidenceScorer):
            def calculate_spring_confidence(
                self,
                spring: Spring,
                creek: CreekLevel,
                previous_tests: list[Test] | None = None,
            ) -> SpringConfidence:
                # Dummy implementation
                return SpringConfidence(
                    total_score=85,
                    component_scores={},
                    quality_tier="GOOD",
                    is_tradeable=True,
                )

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteScorer(
                asset_class="stock",
                volume_reliability="HIGH",
                max_confidence=100,
            )

    def test_complete_implementation_succeeds(self) -> None:
        """
        Test that implementing all abstract methods allows instantiation.

        A complete concrete implementation should instantiate successfully.
        """

        # Complete implementation
        class CompleteScorer(ConfidenceScorer):
            def calculate_spring_confidence(
                self,
                spring: Spring,
                creek: CreekLevel,
                previous_tests: list[Test] | None = None,
            ) -> SpringConfidence:
                return SpringConfidence(
                    total_score=85,
                    component_scores={},
                    quality_tier="GOOD",
                    is_tradeable=True,
                )

            def calculate_sos_confidence(
                self,
                sos: SOSBreakout,
                lps: Optional[LPS],
                range_: TradingRange,
                phase: PhaseClassification,
            ) -> int:
                return 85

        # Should instantiate without error
        scorer = CompleteScorer(
            asset_class="stock",
            volume_reliability="HIGH",
            max_confidence=100,
        )
        assert scorer.asset_class == "stock"
        assert scorer.volume_reliability == "HIGH"
        assert scorer.max_confidence == 100


class TestReprFormatting:
    """Test __repr__ method formatting."""

    def test_repr_includes_all_properties(self) -> None:
        """
        Test that __repr__ includes asset_class, reliability, and max_confidence.
        """

        class TestScorer(ConfidenceScorer):
            def calculate_spring_confidence(
                self,
                spring: Spring,
                creek: CreekLevel,
                previous_tests: list[Test] | None = None,
            ) -> SpringConfidence:
                raise NotImplementedError

            def calculate_sos_confidence(
                self,
                sos: SOSBreakout,
                lps: Optional[LPS],
                range_: TradingRange,
                phase: PhaseClassification,
            ) -> int:
                raise NotImplementedError

        scorer = TestScorer(
            asset_class="forex",
            volume_reliability="LOW",
            max_confidence=85,
        )

        repr_str = repr(scorer)

        # Verify all properties included
        assert "forex" in repr_str
        assert "LOW" in repr_str
        assert "85" in repr_str
        assert "TestScorer" in repr_str

    def test_repr_format_for_different_configurations(self) -> None:
        """
        Test __repr__ format for various asset class configurations.
        """

        class StockScorer(ConfidenceScorer):
            def calculate_spring_confidence(
                self,
                spring: Spring,
                creek: CreekLevel,
                previous_tests: list[Test] | None = None,
            ) -> SpringConfidence:
                raise NotImplementedError

            def calculate_sos_confidence(
                self,
                sos: SOSBreakout,
                lps: Optional[LPS],
                range_: TradingRange,
                phase: PhaseClassification,
            ) -> int:
                raise NotImplementedError

        # Stock configuration
        stock_scorer = StockScorer(
            asset_class="stock", volume_reliability="HIGH", max_confidence=100
        )
        assert "stock" in repr(stock_scorer)
        assert "HIGH" in repr(stock_scorer)
        assert "100" in repr(stock_scorer)

        # Forex configuration
        forex_scorer = StockScorer(asset_class="forex", volume_reliability="LOW", max_confidence=85)
        assert "forex" in repr(forex_scorer)
        assert "LOW" in repr(forex_scorer)
        assert "85" in repr(forex_scorer)

        # Crypto configuration
        crypto_scorer = StockScorer(
            asset_class="crypto", volume_reliability="MEDIUM", max_confidence=95
        )
        assert "crypto" in repr(crypto_scorer)
        assert "MEDIUM" in repr(crypto_scorer)
        assert "95" in repr(crypto_scorer)
