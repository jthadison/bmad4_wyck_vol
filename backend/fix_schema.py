"""Fix backtest_results table schema."""
import asyncio
import sys

from sqlalchemy import text

from src.database import engine


async def fix_schema():
    """Fix the backtest_results table schema."""
    print("Fixing backtest_results table schema...")

    async with engine.begin() as conn:
        # Drop the existing table
        await conn.execute(text("DROP TABLE IF EXISTS backtest_results CASCADE"))
        print("[OK] Dropped existing backtest_results table")

        # Create the table with correct schema
        await conn.execute(
            text(
                """
            CREATE TABLE backtest_results (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                backtest_run_id UUID NOT NULL UNIQUE,
                symbol VARCHAR(20) NOT NULL,
                timeframe VARCHAR(10) NOT NULL DEFAULT '1d',
                start_date TIMESTAMP WITH TIME ZONE NOT NULL,
                end_date TIMESTAMP WITH TIME ZONE NOT NULL,
                config JSONB NOT NULL,
                equity_curve JSONB NOT NULL DEFAULT '[]'::jsonb,
                trades JSONB NOT NULL DEFAULT '[]'::jsonb,
                metrics JSONB NOT NULL,
                look_ahead_bias_check BOOLEAN NOT NULL DEFAULT FALSE,
                execution_time_seconds NUMERIC NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """
            )
        )
        print("[OK] Created backtest_results table with correct schema")

        # Create index
        await conn.execute(
            text(
                """
            CREATE INDEX idx_backtest_results_run_id ON backtest_results(backtest_run_id)
        """
            )
        )
        print("[OK] Created index on backtest_run_id")

    print("\n[SUCCESS] Schema fixed successfully!")


if __name__ == "__main__":
    # Use SelectorEventLoop on Windows for psycopg compatibility
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(fix_schema())
