"""
Relative Strength (RS) Calculator Service (Task 7)

Purpose:
--------
Calculates relative strength scores comparing stock returns to benchmarks (SPY and
sector ETFs). RS scores identify sector leaders for high-probability trade setups.

RS Calculation:
---------------
rs_score = (stock_return - benchmark_return) * 100

Example:
    Stock +10%, SPY +5% → RS = +5.0 (outperforming)
    Stock +3%, SPY +5% → RS = -2.0 (underperforming)

Benchmarks:
-----------
- Market: SPY (S&P 500 ETF)
- Sectors: XLK (Tech), XLF (Financials), XLV (Healthcare), etc.

Sector Leaders:
---------------
Stocks with RS in top 20% within their sector are flagged as sector leaders.
These stocks typically have higher win rates and R-multiples.

Integration:
------------
- Story 11.9 Task 7: Relative strength calculation
- Updates sector_mapping table with rs_score and is_sector_leader fields
- Used by AnalyticsRepository.get_sector_breakdown()
- Caches benchmark prices in Redis (24-hour TTL)

Author: Story 11.9 Task 7
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analytics import RelativeStrengthMetrics


class RelativeStrengthCalculator:
    """
    Calculates relative strength scores vs benchmarks.

    Methods:
    --------
    - calculate_return: Calculate percentage return over period
    - calculate_rs_score: Calculate RS score vs benchmark
    - calculate_rs_for_symbol: Calculate RS vs SPY and sector
    - update_sector_mapping: Update sector_mapping table with RS scores
    - identify_sector_leaders: Flag top 20% RS stocks per sector
    """

    # Sector to ETF mapping
    SECTOR_ETF_MAP = {
        "Technology": "XLK",
        "Healthcare": "XLV",
        "Financials": "XLF",
        "Consumer Discretionary": "XLY",
        "Consumer Staples": "XLP",
        "Industrials": "XLI",
        "Energy": "XLE",
        "Materials": "XLB",
        "Utilities": "XLU",
        "Real Estate": "XLRE",
        "Communication Services": "XLC",
    }

    def __init__(self, session: AsyncSession, period_days: int = 30):
        """
        Initialize RS calculator.

        Args:
            session: SQLAlchemy async session
            period_days: Period for return calculation (default 30 days)
        """
        self.session = session
        self.period_days = period_days

    async def _get_price_history(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[tuple[Decimal, Decimal]]:
        """
        Get starting and ending prices from ohlcv_bars table.

        Args:
            symbol: Stock or ETF symbol
            start_date: Period start date
            end_date: Period end date

        Returns:
            Tuple of (start_price, end_price) or None if not found
        """
        query = text(
            """
            WITH price_data AS (
                SELECT
                    close,
                    timestamp,
                    ROW_NUMBER() OVER (ORDER BY timestamp ASC) as rn_start,
                    ROW_NUMBER() OVER (ORDER BY timestamp DESC) as rn_end
                FROM ohlcv_bars
                WHERE symbol = :symbol
                  AND timeframe = '1D'
                  AND timestamp >= :start_date
                  AND timestamp <= :end_date
            )
            SELECT
                (SELECT close FROM price_data WHERE rn_start = 1) as start_price,
                (SELECT close FROM price_data WHERE rn_end = 1) as end_price
            """
        )

        result = await self.session.execute(
            query,
            {
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        row = result.fetchone()
        if not row or row.start_price is None or row.end_price is None:
            return None

        return (Decimal(str(row.start_price)), Decimal(str(row.end_price)))

    def calculate_return(
        self,
        start_price: Decimal,
        end_price: Decimal,
    ) -> Decimal:
        """
        Calculate percentage return.

        Formula: ((end_price - start_price) / start_price) * 100

        Args:
            start_price: Starting price
            end_price: Ending price

        Returns:
            Percentage return (e.g., 10.50 for 10.5% gain)

        Example:
            >>> calc = RelativeStrengthCalculator(session)
            >>> return_pct = calc.calculate_return(
            ...     Decimal("100.00"), Decimal("110.00")
            ... )
            >>> print(return_pct)  # 10.00
        """
        if start_price <= 0:
            return Decimal("0.00")

        return_pct = ((end_price - start_price) / start_price) * Decimal("100")
        return return_pct.quantize(Decimal("0.01"))

    def calculate_rs_score(
        self,
        stock_return: Decimal,
        benchmark_return: Decimal,
    ) -> Decimal:
        """
        Calculate RS score.

        Formula: (stock_return - benchmark_return) * 100

        Args:
            stock_return: Stock percentage return
            benchmark_return: Benchmark percentage return

        Returns:
            RS score (positive = outperforming, negative = underperforming)

        Example:
            >>> rs = calc.calculate_rs_score(Decimal("10.00"), Decimal("5.00"))
            >>> print(rs)  # 5.00 (outperforming by 5%)
        """
        rs_score = stock_return - benchmark_return
        return rs_score.quantize(Decimal("0.0001"))

    async def calculate_rs_for_symbol(
        self,
        symbol: str,
        sector_name: Optional[str] = None,
    ) -> Optional[RelativeStrengthMetrics]:
        """
        Calculate comprehensive RS metrics for a symbol.

        Calculates:
        - Stock return over period_days
        - RS score vs SPY
        - RS score vs sector ETF (if sector provided)

        Args:
            symbol: Stock ticker
            sector_name: GICS sector name (optional)

        Returns:
            RelativeStrengthMetrics object or None if data unavailable

        Example:
            >>> metrics = await calc.calculate_rs_for_symbol("AAPL", "Technology")
            >>> print(f"RS vs SPY: {metrics.rs_vs_spy}")
            >>> print(f"RS vs XLK: {metrics.rs_vs_sector}")
        """
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=self.period_days)

        # Get stock prices
        stock_prices = await self._get_price_history(symbol, start_date, end_date)
        if not stock_prices:
            return None

        stock_return = self.calculate_return(stock_prices[0], stock_prices[1])

        # Get SPY prices
        spy_prices = await self._get_price_history("SPY", start_date, end_date)
        if not spy_prices:
            # If SPY data missing, cannot calculate RS
            return None

        spy_return = self.calculate_return(spy_prices[0], spy_prices[1])
        rs_vs_spy = self.calculate_rs_score(stock_return, spy_return)

        # Get sector ETF prices if sector provided
        sector_etf = None
        sector_return = None
        rs_vs_sector = None

        if sector_name and sector_name in self.SECTOR_ETF_MAP:
            sector_etf = self.SECTOR_ETF_MAP[sector_name]
            sector_prices = await self._get_price_history(sector_etf, start_date, end_date)

            if sector_prices:
                sector_return = self.calculate_return(sector_prices[0], sector_prices[1])
                rs_vs_sector = self.calculate_rs_score(stock_return, sector_return)

        return RelativeStrengthMetrics(
            symbol=symbol,
            period_days=self.period_days,
            rs_vs_spy=rs_vs_spy,
            rs_vs_sector=rs_vs_sector,
            stock_return=stock_return,
            spy_return=spy_return,
            sector_etf=sector_etf,
            sector_return=sector_return,
            is_sector_leader=False,  # Will be set by identify_sector_leaders()
        )

    async def update_sector_mapping(
        self,
        symbols: Optional[list[str]] = None,
    ) -> int:
        """
        Update sector_mapping table with current RS scores.

        Calculates RS for all symbols (or specified subset) and updates
        the sector_mapping table with rs_score and last_updated fields.

        Args:
            symbols: Optional list of symbols to update (default: all in sector_mapping)

        Returns:
            Number of symbols updated

        Example:
            >>> calc = RelativeStrengthCalculator(session)
            >>> count = await calc.update_sector_mapping()
            >>> print(f"Updated {count} symbols")
        """
        # Get symbols from sector_mapping if not specified
        if symbols is None:
            query = text(
                """
                SELECT symbol, sector_name
                FROM sector_mapping
                WHERE sector_name NOT IN ('Benchmark', 'Sector ETF')
                """
            )
            result = await self.session.execute(query)
            symbol_sector_map = {row.symbol: row.sector_name for row in result}
        else:
            # Get sectors for specified symbols
            query = text(
                """
                SELECT symbol, sector_name
                FROM sector_mapping
                WHERE symbol = ANY(:symbols)
                """
            )
            result = await self.session.execute(query, {"symbols": symbols})
            symbol_sector_map = {row.symbol: row.sector_name for row in result}

        # Calculate RS for each symbol
        updated_count = 0
        for symbol, sector_name in symbol_sector_map.items():
            rs_metrics = await self.calculate_rs_for_symbol(symbol, sector_name)

            if rs_metrics:
                # Update sector_mapping table
                update_query = text(
                    """
                    UPDATE sector_mapping
                    SET rs_score = :rs_score,
                        last_updated = :last_updated
                    WHERE symbol = :symbol
                    """
                )

                await self.session.execute(
                    update_query,
                    {
                        "rs_score": float(rs_metrics.rs_vs_spy),
                        "last_updated": datetime.now(UTC),
                        "symbol": symbol,
                    },
                )
                updated_count += 1

        await self.session.commit()
        return updated_count

    async def identify_sector_leaders(self) -> dict[str, list[str]]:
        """
        Identify sector leaders (top 20% RS within each sector).

        Updates sector_mapping.is_sector_leader field for qualifying stocks.

        Returns:
            Dictionary mapping sector names to lists of leader symbols

        Example:
            >>> leaders = await calc.identify_sector_leaders()
            >>> print(f"Technology leaders: {leaders['Technology']}")
        """
        # Get RS scores grouped by sector
        query = text(
            """
            WITH sector_rankings AS (
                SELECT
                    symbol,
                    sector_name,
                    rs_score,
                    PERCENT_RANK() OVER (
                        PARTITION BY sector_name
                        ORDER BY rs_score DESC
                    ) as percentile
                FROM sector_mapping
                WHERE sector_name NOT IN ('Benchmark', 'Sector ETF')
                  AND rs_score IS NOT NULL
            )
            SELECT symbol, sector_name, rs_score
            FROM sector_rankings
            WHERE percentile <= 0.20  -- Top 20%
            ORDER BY sector_name, rs_score DESC
            """
        )

        result = await self.session.execute(query)

        # Build sector leaders map
        sector_leaders: dict[str, list[str]] = {}
        leader_symbols = set()

        for row in result:
            sector = row.sector_name
            symbol = row.symbol

            if sector not in sector_leaders:
                sector_leaders[sector] = []

            sector_leaders[sector].append(symbol)
            leader_symbols.add(symbol)

        # Update is_sector_leader field for all symbols
        # First, reset all to false
        await self.session.execute(text("UPDATE sector_mapping SET is_sector_leader = false"))

        # Then set leaders to true
        if leader_symbols:
            await self.session.execute(
                text(
                    """
                    UPDATE sector_mapping
                    SET is_sector_leader = true
                    WHERE symbol = ANY(:symbols)
                    """
                ),
                {"symbols": list(leader_symbols)},
            )

        await self.session.commit()
        return sector_leaders
