---
title: "What is portfolio heat?"
category: "FAQ"
tags: ["risk", "portfolio", "heat", "position sizing"]
keywords: "portfolio heat, aggregate risk, risk management, 6% threshold, concurrent positions"
---

# What is portfolio heat?

Portfolio heat represents the aggregate risk exposure across all open positions in the trading account, expressed as a percentage of total account equity. While individual position risk controls how much capital is at risk on a single trade, portfolio heat governs the total amount of capital exposed across concurrent positions. This distinction is critical because multiple uncorrelated positions with proper individual risk management can still create excessive aggregate risk if too many positions are open simultaneously.

The portfolio heat calculation is straightforward: sum the R amount (distance from entry to stop in dollars) for all open positions and divide by total account equity. For example, if a trader has a $100,000 account with three open positions risking $1,000, $800, and $1,200 respectively, the portfolio heat is ($1,000 + $800 + $1,200) / $100,000 = 3%. This metric provides an instant snapshot of how much capital is at risk if all positions simultaneously hit their stops—a worst-case scenario that, while unlikely, must be planned for in prudent risk management.

BMAD4 implements a 6% portfolio heat threshold as a default risk management control, preventing the trader from opening new positions when aggregate risk exceeds this level. This threshold is based on professional risk management principles: a trader can survive a string of losses at 6% total heat, whereas 10-15% heat creates the potential for catastrophic drawdowns. The 6% threshold typically allows for 4-6 concurrent positions when individual position risk is 1-1.5% per trade, providing sufficient diversification while maintaining prudent aggregate risk control. The system displays current portfolio heat in real-time and prevents execution of new trades when the threshold would be exceeded.

The portfolio heat framework has important implications for position sizing and trade selection. When heat is approaching the 6% threshold, traders must either wait for existing positions to close or exit lower-conviction positions to free up capacity for higher-quality setups. This forces prioritization: rather than taking every marginal signal, traders focus on the highest-confidence opportunities. It also prevents the common error of overtrading during volatile periods when many signals may trigger simultaneously. By capping aggregate risk exposure, portfolio heat management ensures that the trader maintains control over their total risk profile regardless of how many individual opportunities arise, protecting capital during adverse market conditions while allowing sufficient exposure to capture trends during favorable periods.
