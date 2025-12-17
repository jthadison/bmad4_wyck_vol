---
title: "How do campaigns work?"
category: "FAQ"
tags: ["campaigns", "lifecycle", "allocation", "tracking"]
keywords: "campaigns, multi-phase lifecycle, allocation, tracking, position management"
---

# How do campaigns work?

Campaigns in BMAD4 represent the complete lifecycle of a Wyckoff trading opportunity, from initial signal detection through position entry, management, and eventual exit. Unlike simple trade records that track individual transactions, campaigns capture the multi-phase nature of Wyckoff setups, where a single accumulation range may generate multiple entry opportunities ([[SOS]], [[LPS]]) and require management through various phases of the markup or markdown. This campaign-centric approach aligns the software's tracking capabilities with the reality of how Wyckoff patterns develop and are traded.

A campaign is initiated when the system detects a high-confidence Wyckoff pattern—typically a [[Spring]] in [[Phase C]] or an SOS in [[Phase D]]. The campaign record captures the structural details of the setup including the [[Trading Range]] boundaries, the [[Creek]] and [[Ice]] levels, the calculated [[Jump]] target, and the [[Signal Confidence Score]]. Initial position sizing is determined based on the trader's risk tolerance and current portfolio heat, with the stop placed at the Ice level. As the pattern progresses, the campaign tracks additional entry opportunities—for example, an initial spring entry might be followed by an SOS entry and one or more LPS entries, all within the same campaign framework.

Campaign allocation allows traders to scale into positions as confirmation builds. Rather than committing full capital at the first signal, a prudent approach might allocate 30-40% of the intended position at the spring, 30-40% at the first LPS, and 20-30% at a subsequent LPS if one develops. This scaling strategy improves average entry price and reduces the risk of full commitment to a pattern that ultimately fails. The campaign structure tracks each entry separately while maintaining aggregate position metrics, stop levels, and target calculations. This provides a complete view of the position's development and performance across multiple entries.

Campaign lifecycle management includes tracking profit targets, stop adjustments, and exits. As price progresses toward the Jump target, the system monitors whether the campaign is meeting expectations or showing signs of weakness. If the Ice level is violated, all positions within the campaign are flagged for exit regardless of individual entry prices, as the structural invalidation applies to the entire pattern hypothesis. Upon campaign completion—whether through successful target achievement or stop violation—the system calculates comprehensive performance metrics including average entry price, total R-multiple profit or loss, holding period, and whether the pattern performed as expected. This campaign-level analysis enables traders to evaluate the effectiveness of their Wyckoff pattern recognition and execution over time, providing feedback that improves future decision-making.
