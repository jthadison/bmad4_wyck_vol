"""
Cost Validation and Realistic Expectation Checks (Story 12.5 Task 12).

Validates that transaction costs produce realistic impact on backtest results,
ensuring backtests don't show over-optimistic performance.

AC10: Theoretical 2.5R → 2.2R net after costs (12% degradation is realistic)

Author: Story 12.5 Task 12
"""

from decimal import Decimal
from typing import Any

import structlog

from src.models.backtest import BacktestCostSummary, BacktestResult

logger = structlog.get_logger(__name__)


class CostValidator:
    """
    Validate transaction cost impact on backtest results.

    Ensures cost modeling produces realistic degradation in performance
    metrics, preventing over-optimistic backtest results.

    Validation Rules (AC10):
    1. R-multiple degradation should be 5-15% for typical strategies
    2. Commission per trade should be realistic ($1-$50 typical range)
    3. Slippage should be proportional to liquidity
    4. Market impact should increase non-linearly with order size

    Methods:
        validate_r_multiple_degradation: Check R-multiple impact is realistic
        validate_commission_costs: Check commission costs are reasonable
        validate_slippage_costs: Check slippage costs are realistic
        validate_full_backtest: Run all validations and return report

    Example:
        validator = CostValidator()
        backtest_result = BacktestResult(...)

        validation = validator.validate_full_backtest(backtest_result)
        if not validation["is_valid"]:
            print("⚠️ Backtest validation failed!")
            for warning in validation["warnings"]:
                print(f"  - {warning}")

    Author: Story 12.5 Task 12
    """

    # Validation thresholds
    MIN_R_MULTIPLE_DEGRADATION_PCT = Decimal("3")  # 3% minimum degradation
    MAX_R_MULTIPLE_DEGRADATION_PCT = Decimal("20")  # 20% maximum degradation
    REALISTIC_R_MULTIPLE_DEGRADATION_PCT = Decimal("12")  # 12% is typical (AC10)

    MIN_COMMISSION_PER_TRADE = Decimal("0")  # Zero-commission brokers exist
    MAX_COMMISSION_PER_TRADE = Decimal("50")  # $50 is unusually high

    MIN_SLIPPAGE_PER_TRADE = Decimal("0")  # Limit orders can have zero slippage
    MAX_SLIPPAGE_PER_TRADE = Decimal("100")  # $100 slippage suggests issues

    def validate_r_multiple_degradation(
        self, cost_summary: BacktestCostSummary
    ) -> tuple[bool, list[str]]:
        """
        Validate R-multiple degradation is realistic.

        Subtask 12.2: Check degradation is between 3-20%
        Subtask 12.2: Warn if degradation is outside realistic range
        Subtask 12.2: Flag if degradation is zero (costs not applied)

        Args:
            cost_summary: Backtest cost summary

        Returns:
            Tuple of (is_valid, list of warning messages)

        Validation:
            - Degradation = 0%: ERROR - No costs applied
            - Degradation < 3%: WARNING - Costs may be too low
            - Degradation 3-20%: VALID - Realistic range
            - Degradation > 20%: WARNING - Costs may be too high

        Example:
            cost_summary = BacktestCostSummary(
                gross_avg_r_multiple=Decimal("2.5"),
                net_avg_r_multiple=Decimal("2.2"),
                r_multiple_degradation=Decimal("0.3"),  # 12% degradation
                ...
            )
            is_valid, warnings = validator.validate_r_multiple_degradation(cost_summary)
            # is_valid = True, warnings = []

        Author: Story 12.5 Subtask 12.2
        """
        warnings = []
        is_valid = True

        # Calculate degradation percentage
        if cost_summary.gross_avg_r_multiple != Decimal("0"):
            degradation_pct = (
                cost_summary.r_multiple_degradation
                / cost_summary.gross_avg_r_multiple
                * Decimal("100")
            )
        else:
            degradation_pct = Decimal("0")

        # Check for zero degradation (ERROR)
        if degradation_pct == Decimal("0"):
            warnings.append(
                "❌ ERROR: R-multiple degradation is 0% - Transaction costs not applied! "
                "Backtest results are unrealistic."
            )
            is_valid = False
        # Check for too low degradation (WARNING)
        elif degradation_pct < self.MIN_R_MULTIPLE_DEGRADATION_PCT:
            warnings.append(
                f"⚠️  WARNING: R-multiple degradation is {degradation_pct:.1f}% - "
                f"This is unusually low (expected {self.MIN_R_MULTIPLE_DEGRADATION_PCT}%-{self.MAX_R_MULTIPLE_DEGRADATION_PCT}%). "
                f"Verify commission/slippage configs are realistic."
            )
        # Check for too high degradation (WARNING)
        elif degradation_pct > self.MAX_R_MULTIPLE_DEGRADATION_PCT:
            warnings.append(
                f"⚠️  WARNING: R-multiple degradation is {degradation_pct:.1f}% - "
                f"This is unusually high (expected {self.MIN_R_MULTIPLE_DEGRADATION_PCT}%-{self.MAX_R_MULTIPLE_DEGRADATION_PCT}%). "
                f"Consider: reducing position sizes, using limit orders, or trading more liquid instruments."
            )
        # Valid range - check if matches AC10 target
        elif abs(degradation_pct - self.REALISTIC_R_MULTIPLE_DEGRADATION_PCT) <= Decimal("2"):
            logger.info(
                "R-multiple degradation validation passed (matches AC10 target)",
                degradation_pct=float(degradation_pct),
                target_pct=float(self.REALISTIC_R_MULTIPLE_DEGRADATION_PCT),
            )
        else:
            logger.info(
                "R-multiple degradation validation passed",
                degradation_pct=float(degradation_pct),
            )

        return is_valid, warnings

    def validate_commission_costs(
        self, cost_summary: BacktestCostSummary
    ) -> tuple[bool, list[str]]:
        """
        Validate commission costs are reasonable.

        Subtask 12.3: Check average commission per trade is in realistic range
        Subtask 12.3: Warn if commission is unusually high or suspiciously low

        Args:
            cost_summary: Backtest cost summary

        Returns:
            Tuple of (is_valid, list of warning messages)

        Validation:
            - Avg commission $0-$50: VALID (typical range)
            - Avg commission > $50: WARNING - Unusually high
            - Note: Zero commission is valid (Robinhood, TD Ameritrade, etc.)

        Example:
            cost_summary = BacktestCostSummary(
                avg_commission_per_trade=Decimal("10.00"),  # Typical for IB
                ...
            )
            is_valid, warnings = validator.validate_commission_costs(cost_summary)
            # is_valid = True, warnings = []

        Author: Story 12.5 Subtask 12.3
        """
        warnings = []
        is_valid = True

        avg_commission = cost_summary.avg_commission_per_trade

        # Check for unusually high commission
        if avg_commission > self.MAX_COMMISSION_PER_TRADE:
            warnings.append(
                f"⚠️  WARNING: Average commission per trade is ${avg_commission:.2f} - "
                f"This is unusually high (expected ${self.MIN_COMMISSION_PER_TRADE}-${self.MAX_COMMISSION_PER_TRADE}). "
                f"Verify commission configuration or consider a different broker profile."
            )
        # Zero commission is valid (many brokers now commission-free)
        elif avg_commission == Decimal("0"):
            logger.info(
                "Commission validation passed (zero-commission broker)",
                avg_commission=float(avg_commission),
            )
        else:
            logger.info(
                "Commission validation passed",
                avg_commission=float(avg_commission),
            )

        return is_valid, warnings

    def validate_slippage_costs(self, cost_summary: BacktestCostSummary) -> tuple[bool, list[str]]:
        """
        Validate slippage costs are realistic.

        Subtask 12.4: Check average slippage per trade is reasonable
        Subtask 12.4: Warn if slippage is unusually high (suggests liquidity issues)

        Args:
            cost_summary: Backtest cost summary

        Returns:
            Tuple of (is_valid, list of warning messages)

        Validation:
            - Avg slippage $0-$100: VALID (typical range)
            - Avg slippage > $100: WARNING - Unusually high (liquidity issues)
            - Zero slippage: Valid for limit orders only

        Example:
            cost_summary = BacktestCostSummary(
                avg_slippage_per_trade=Decimal("4.00"),  # Typical
                ...
            )
            is_valid, warnings = validator.validate_slippage_costs(cost_summary)
            # is_valid = True, warnings = []

        Author: Story 12.5 Subtask 12.4
        """
        warnings = []
        is_valid = True

        avg_slippage = cost_summary.avg_slippage_per_trade

        # Check for unusually high slippage
        if avg_slippage > self.MAX_SLIPPAGE_PER_TRADE:
            warnings.append(
                f"⚠️  WARNING: Average slippage per trade is ${avg_slippage:.2f} - "
                f"This is unusually high (expected ${self.MIN_SLIPPAGE_PER_TRADE}-${self.MAX_SLIPPAGE_PER_TRADE}). "
                f"This suggests: (1) Trading illiquid instruments, "
                f"(2) Position sizes too large, or (3) Market impact too high. "
                f"Consider trading more liquid instruments or reducing position sizes."
            )
        elif avg_slippage == Decimal("0"):
            logger.info(
                "Slippage validation passed (zero slippage - likely using limit orders)",
                avg_slippage=float(avg_slippage),
            )
        else:
            logger.info("Slippage validation passed", avg_slippage=float(avg_slippage))

        return is_valid, warnings

    def validate_cost_distribution(
        self, cost_summary: BacktestCostSummary
    ) -> tuple[bool, list[str]]:
        """
        Validate distribution of commission vs slippage costs.

        Subtask 12.5: Check commission/slippage ratio is reasonable
        Subtask 12.5: Warn if one cost dominates excessively

        Args:
            cost_summary: Backtest cost summary

        Returns:
            Tuple of (is_valid, list of warning messages)

        Validation:
            - Commission/Slippage ratio should typically be 0.5-5.0
            - If commission >> slippage: Broker costs too high
            - If slippage >> commission: Liquidity issues or market impact too high

        Example:
            cost_summary = BacktestCostSummary(
                total_commission_paid=Decimal("1000"),
                total_slippage_cost=Decimal("400"),  # Ratio 2.5:1 (reasonable)
                ...
            )
            is_valid, warnings = validator.validate_cost_distribution(cost_summary)
            # is_valid = True, warnings = []

        Author: Story 12.5 Subtask 12.5
        """
        warnings = []
        is_valid = True

        total_commission = cost_summary.total_commission_paid
        total_slippage = cost_summary.total_slippage_cost

        # Calculate ratio (handle zero slippage edge case)
        if total_slippage > Decimal("0"):
            commission_to_slippage_ratio = total_commission / total_slippage
        else:
            commission_to_slippage_ratio = Decimal("inf") if total_commission > 0 else Decimal("1")

        # Check if commission dominates (ratio > 5)
        if commission_to_slippage_ratio > Decimal("5"):
            warnings.append(
                f"⚠️  WARNING: Commission costs (${total_commission:.2f}) are much higher "
                f"than slippage costs (${total_slippage:.2f}). "
                f"Ratio: {commission_to_slippage_ratio:.1f}:1. "
                f"Consider switching to a lower-commission broker profile."
            )
        # Check if slippage dominates (ratio < 0.5)
        elif total_slippage > Decimal("0") and commission_to_slippage_ratio < Decimal("0.5"):
            warnings.append(
                f"⚠️  WARNING: Slippage costs (${total_slippage:.2f}) are much higher "
                f"than commission costs (${total_commission:.2f}). "
                f"Ratio: {commission_to_slippage_ratio:.1f}:1. "
                f"This suggests liquidity issues or excessive market impact. "
                f"Consider: reducing position sizes or trading more liquid instruments."
            )
        else:
            logger.info(
                "Cost distribution validation passed",
                commission_to_slippage_ratio=float(commission_to_slippage_ratio),
            )

        return is_valid, warnings

    def validate_ac10_compliance(self, cost_summary: BacktestCostSummary) -> tuple[bool, list[str]]:
        """
        Validate AC10: Theoretical 2.5R → 2.2R net after costs.

        Subtask 12.6: Check if backtest achieves AC10 target degradation
        Subtask 12.6: Validate gross R-multiple is realistic (1.5-4.0 typical range)

        Args:
            cost_summary: Backtest cost summary

        Returns:
            Tuple of (is_valid, list of warning messages)

        AC10 Validation:
            - Gross avg R-multiple should be 1.5-4.0 (realistic profitable strategy)
            - Degradation should be ~12% (2.5R → 2.2R as per AC10)
            - Net avg R-multiple should be > 1.0 (profitable after costs)

        Example:
            cost_summary = BacktestCostSummary(
                gross_avg_r_multiple=Decimal("2.5"),
                net_avg_r_multiple=Decimal("2.2"),
                r_multiple_degradation=Decimal("0.3"),  # 12% degradation
                ...
            )
            is_valid, warnings = validator.validate_ac10_compliance(cost_summary)
            # is_valid = True, warnings = []

        Author: Story 12.5 Subtask 12.6
        """
        warnings = []
        is_valid = True

        gross_r = cost_summary.gross_avg_r_multiple
        net_r = cost_summary.net_avg_r_multiple
        degradation = cost_summary.r_multiple_degradation

        # Check gross R-multiple is realistic
        if gross_r < Decimal("1.5"):
            warnings.append(
                f"⚠️  WARNING: Gross avg R-multiple ({gross_r:.2f}R) is low. "
                f"Expected 1.5R-4.0R for a profitable strategy."
            )
        elif gross_r > Decimal("4.0"):
            warnings.append(
                f"⚠️  WARNING: Gross avg R-multiple ({gross_r:.2f}R) is unusually high. "
                f"Expected 1.5R-4.0R. Verify strategy is not over-optimized."
            )

        # Check net R-multiple is profitable
        if net_r < Decimal("1.0"):
            warnings.append(
                f"⚠️  WARNING: Net avg R-multiple ({net_r:.2f}R) is below 1.0R. "
                f"Strategy is not profitable after transaction costs."
            )

        # Check AC10 compliance (2.5R → 2.2R)
        ac10_target_gross = Decimal("2.5")
        ac10_target_net = Decimal("2.2")
        ac10_target_degradation = ac10_target_gross - ac10_target_net  # 0.3R

        # Allow ±20% tolerance on AC10 targets
        if abs(gross_r - ac10_target_gross) <= ac10_target_gross * Decimal("0.2"):
            if abs(net_r - ac10_target_net) <= ac10_target_net * Decimal("0.2"):
                logger.info(
                    "✅ AC10 COMPLIANCE: Backtest achieves target cost degradation",
                    gross_r=float(gross_r),
                    net_r=float(net_r),
                    degradation=float(degradation),
                    ac10_target_gross=float(ac10_target_gross),
                    ac10_target_net=float(ac10_target_net),
                )

        return is_valid, warnings

    def validate_full_backtest(self, backtest_result: BacktestResult) -> dict[str, Any]:
        """
        Run all cost validations on backtest result.

        Subtask 12.7: Execute all validation checks
        Subtask 12.7: Aggregate warnings and errors
        Subtask 12.8: Return validation report with recommendations

        Args:
            backtest_result: Complete backtest result

        Returns:
            Validation report dictionary with:
                - is_valid: bool (True if no errors)
                - warnings: List of warning messages
                - errors: List of error messages
                - recommendations: List of recommended actions

        Example:
            validator = CostValidator()
            result = BacktestResult(...)
            validation = validator.validate_full_backtest(result)

            if validation["is_valid"]:
                print("✅ Backtest validation passed")
            else:
                print("❌ Backtest validation failed")
                for error in validation["errors"]:
                    print(f"  ERROR: {error}")
                for warning in validation["warnings"]:
                    print(f"  WARNING: {warning}")

        Author: Story 12.5 Subtask 12.7, 12.8
        """
        if not backtest_result.cost_summary:
            return {
                "is_valid": False,
                "errors": ["No cost summary available - Transaction costs not calculated"],
                "warnings": [],
                "recommendations": [
                    "Ensure BacktestConfig includes commission_config and slippage_config"
                ],
            }

        cost_summary = backtest_result.cost_summary

        all_warnings = []
        all_errors = []
        recommendations = []

        # Run all validations
        validators = [
            ("R-Multiple Degradation", self.validate_r_multiple_degradation),
            ("Commission Costs", self.validate_commission_costs),
            ("Slippage Costs", self.validate_slippage_costs),
            ("Cost Distribution", self.validate_cost_distribution),
            ("AC10 Compliance", self.validate_ac10_compliance),
        ]

        for validator_name, validator_func in validators:
            is_valid, warnings = validator_func(cost_summary)
            if not is_valid:
                all_errors.extend(warnings)
            else:
                all_warnings.extend(warnings)

            logger.debug(
                f"{validator_name} validation complete",
                is_valid=is_valid,
                warning_count=len(warnings),
            )

        # Generate recommendations based on warnings
        if len(all_warnings) > 0 or len(all_errors) > 0:
            if any("degradation is 0%" in msg for msg in all_errors):
                recommendations.append(
                    "Add commission_config and slippage_config to BacktestConfig"
                )
            if any("commission" in msg.lower() and "high" in msg.lower() for msg in all_warnings):
                recommendations.append(
                    "Consider switching to a lower-commission broker profile (e.g., zero-commission brokers)"
                )
            if any("slippage" in msg.lower() and "high" in msg.lower() for msg in all_warnings):
                recommendations.append(
                    "Reduce position sizes to minimize market impact and slippage"
                )
                recommendations.append(
                    "Consider trading more liquid instruments with higher average dollar volume"
                )
            if any("degradation" in msg.lower() and "high" in msg.lower() for msg in all_warnings):
                recommendations.append(
                    "Use limit orders instead of market orders to reduce slippage"
                )

        is_overall_valid = len(all_errors) == 0

        validation_report = {
            "is_valid": is_overall_valid,
            "errors": all_errors,
            "warnings": all_warnings,
            "recommendations": recommendations,
            "cost_summary": {
                "gross_avg_r_multiple": float(cost_summary.gross_avg_r_multiple),
                "net_avg_r_multiple": float(cost_summary.net_avg_r_multiple),
                "r_multiple_degradation": float(cost_summary.r_multiple_degradation),
                "degradation_pct": float(
                    cost_summary.r_multiple_degradation / cost_summary.gross_avg_r_multiple * 100
                    if cost_summary.gross_avg_r_multiple != 0
                    else 0
                ),
            },
        }

        logger.info(
            "Full backtest validation complete",
            is_valid=is_overall_valid,
            error_count=len(all_errors),
            warning_count=len(all_warnings),
        )

        return validation_report
