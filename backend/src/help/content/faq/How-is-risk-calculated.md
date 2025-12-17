---
title: "How is risk calculated?"
category: "FAQ"
tags: ["risk", "position sizing", "stops", "r-multiple"]
keywords: "risk calculation, stop placement, r-multiple, creek, ice, position sizing"
---

# How is risk calculated?

Risk calculation in BMAD4 is based on structural stop placement using the Wyckoff levels that define the validity of accumulation or distribution patterns. Unlike arbitrary percentage-based stops or ATR multiples, structural stops are placed at logical points where the pattern hypothesis is invalidated—specifically at the [[Ice]] level, which represents deep penetration beyond acceptable [[Creek]] violation. This approach ensures that stop placement is dictated by market structure rather than arbitrary rules, aligning risk management with the underlying pattern logic.

For accumulation patterns like the [[Spring]], the stop is placed approximately 2 ATR (Average True Range) below the [[Creek]] support level, which corresponds to the Ice threshold. This placement provides sufficient room for the spring pattern to develop its characteristic shakeout—a brief violation of Creek that triggers retail stops—while establishing a clear boundary beyond which the accumulation hypothesis is considered failed. The distance between the entry price and the Ice level defines the R (risk) amount for the trade. For example, if entry occurs at $50.00 and Ice is at $48.00, the R amount is $2.00 per share.

Position sizing is calculated by dividing the dollar amount the trader is willing to risk on the trade by the R amount. If a trader has a $100,000 account and is willing to risk 1% ($1,000) on a trade with an R of $2.00, the position size would be 500 shares ($1,000 / $2.00 = 500). This ensures that if the stop is hit, the loss is limited to the predetermined risk tolerance. The system displays the calculated position size alongside the signal, enabling traders to execute proper sizing without manual calculation. This R-based approach ensures consistent risk exposure across trades regardless of the underlying price or volatility of the security.

The R-multiple framework extends beyond simple stop placement to become the foundation for trade management and performance evaluation. Profit targets are expressed as multiples of R—for example, a [[Jump]] target that is $6.00 away from entry with an R of $2.00 represents a 3R potential reward. This creates an objective risk-reward ratio that can be evaluated before entering the trade. Performance is tracked in R-multiples rather than dollars or percentages, allowing traders to assess the quality of their execution independent of position sizing decisions. A strategy that averages +1.5R per trade is profitable regardless of whether the trader risks $100 or $10,000 per trade. This structural approach to risk calculation transforms risk management from an afterthought into an integral component of the trading methodology.
