"""Create Sector Mapping Table (Task 3)

Revision ID: 015
Revises: 014
Create Date: 2025-12-12

This migration creates the sector_mapping table for sector breakdown analytics.
Maps stock symbols to GICS sectors for performance analysis.

Changes:
--------
1. Create sector_mapping table:
   - symbol (VARCHAR(10), PRIMARY KEY)
   - sector_name (VARCHAR(50), NOT NULL) - GICS sector classification
   - industry (VARCHAR(100), nullable) - GICS industry group
   - rs_score (NUMERIC(10,4), nullable) - Relative strength vs SPY (Task 7)
   - is_sector_leader (BOOLEAN, default FALSE) - Top 20% RS flag
   - last_updated (TIMESTAMPTZ) - When RS was last calculated

2. Create index on sector_name for sector aggregation queries

3. Seed data for common symbols (100+ stocks across 11 GICS sectors)

GICS Sectors:
-------------
1. Technology
2. Healthcare
3. Financials
4. Consumer Discretionary
5. Consumer Staples
6. Industrials
7. Energy
8. Materials
9. Utilities
10. Real Estate
11. Communication Services
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create sector_mapping table and seed with initial data.
    """

    # Create sector_mapping table
    op.create_table(
        "sector_mapping",
        sa.Column(
            "symbol",
            sa.String(length=10),
            primary_key=True,
            comment="Stock ticker symbol",
        ),
        sa.Column(
            "sector_name",
            sa.String(length=50),
            nullable=False,
            comment="GICS sector classification",
        ),
        sa.Column(
            "industry",
            sa.String(length=100),
            nullable=True,
            comment="GICS industry group",
        ),
        sa.Column(
            "rs_score",
            sa.NUMERIC(precision=10, scale=4),
            nullable=True,
            comment="Relative strength score vs SPY",
        ),
        sa.Column(
            "is_sector_leader",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="True if top 20% RS within sector",
        ),
        sa.Column(
            "last_updated",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="When RS was last calculated",
        ),
    )

    # Create index for sector aggregation queries
    op.create_index(
        "idx_sector_mapping_sector",
        "sector_mapping",
        ["sector_name"],
    )

    # Seed common technology stocks
    op.execute(
        """
        INSERT INTO sector_mapping (symbol, sector_name, industry) VALUES
        ('AAPL', 'Technology', 'Technology Hardware, Storage & Peripherals'),
        ('MSFT', 'Technology', 'Software'),
        ('NVDA', 'Technology', 'Semiconductors'),
        ('GOOGL', 'Communication Services', 'Interactive Media & Services'),
        ('GOOG', 'Communication Services', 'Interactive Media & Services'),
        ('AMZN', 'Consumer Discretionary', 'Broadline Retail'),
        ('META', 'Communication Services', 'Interactive Media & Services'),
        ('TSLA', 'Consumer Discretionary', 'Automobiles'),
        ('AVGO', 'Technology', 'Semiconductors'),
        ('ORCL', 'Technology', 'Software'),
        ('AMD', 'Technology', 'Semiconductors'),
        ('INTC', 'Technology', 'Semiconductors'),
        ('CRM', 'Technology', 'Software'),
        ('ADBE', 'Technology', 'Software'),
        ('CSCO', 'Technology', 'Communications Equipment'),
        ('QCOM', 'Technology', 'Semiconductors'),
        ('IBM', 'Technology', 'IT Services'),
        ('TXN', 'Technology', 'Semiconductors'),
        ('NOW', 'Technology', 'Software'),
        ('PANW', 'Technology', 'Software')
        """
    )

    # Seed healthcare stocks
    op.execute(
        """
        INSERT INTO sector_mapping (symbol, sector_name, industry) VALUES
        ('UNH', 'Healthcare', 'Health Care Providers & Services'),
        ('JNJ', 'Healthcare', 'Pharmaceuticals'),
        ('LLY', 'Healthcare', 'Pharmaceuticals'),
        ('ABBV', 'Healthcare', 'Biotechnology'),
        ('PFE', 'Healthcare', 'Pharmaceuticals'),
        ('MRK', 'Healthcare', 'Pharmaceuticals'),
        ('TMO', 'Healthcare', 'Life Sciences Tools & Services'),
        ('ABT', 'Healthcare', 'Health Care Equipment & Supplies'),
        ('DHR', 'Healthcare', 'Health Care Equipment & Supplies'),
        ('AMGN', 'Healthcare', 'Biotechnology'),
        ('CVS', 'Healthcare', 'Health Care Providers & Services'),
        ('BMY', 'Healthcare', 'Pharmaceuticals'),
        ('GILD', 'Healthcare', 'Biotechnology'),
        ('ISRG', 'Healthcare', 'Health Care Equipment & Supplies'),
        ('VRTX', 'Healthcare', 'Biotechnology')
        """
    )

    # Seed financial stocks
    op.execute(
        """
        INSERT INTO sector_mapping (symbol, sector_name, industry) VALUES
        ('BRK.B', 'Financials', 'Multi-Sector Holdings'),
        ('JPM', 'Financials', 'Banks'),
        ('V', 'Financials', 'Financial Services'),
        ('MA', 'Financials', 'Financial Services'),
        ('BAC', 'Financials', 'Banks'),
        ('WFC', 'Financials', 'Banks'),
        ('GS', 'Financials', 'Capital Markets'),
        ('MS', 'Financials', 'Capital Markets'),
        ('AXP', 'Financials', 'Consumer Finance'),
        ('BLK', 'Financials', 'Capital Markets'),
        ('SCHW', 'Financials', 'Capital Markets'),
        ('C', 'Financials', 'Banks'),
        ('CB', 'Financials', 'Insurance'),
        ('PGR', 'Financials', 'Insurance'),
        ('MMC', 'Financials', 'Insurance')
        """
    )

    # Seed consumer discretionary stocks
    op.execute(
        """
        INSERT INTO sector_mapping (symbol, sector_name, industry) VALUES
        ('HD', 'Consumer Discretionary', 'Specialty Retail'),
        ('NKE', 'Consumer Discretionary', 'Textiles, Apparel & Luxury Goods'),
        ('MCD', 'Consumer Discretionary', 'Hotels, Restaurants & Leisure'),
        ('LOW', 'Consumer Discretionary', 'Specialty Retail'),
        ('SBUX', 'Consumer Discretionary', 'Hotels, Restaurants & Leisure'),
        ('TJX', 'Consumer Discretionary', 'Specialty Retail'),
        ('BKNG', 'Consumer Discretionary', 'Hotels, Restaurants & Leisure'),
        ('CMG', 'Consumer Discretionary', 'Hotels, Restaurants & Leisure'),
        ('F', 'Consumer Discretionary', 'Automobiles'),
        ('GM', 'Consumer Discretionary', 'Automobiles')
        """
    )

    # Seed consumer staples stocks
    op.execute(
        """
        INSERT INTO sector_mapping (symbol, sector_name, industry) VALUES
        ('WMT', 'Consumer Staples', 'Consumer Staples Distribution & Retail'),
        ('PG', 'Consumer Staples', 'Household Products'),
        ('KO', 'Consumer Staples', 'Beverages'),
        ('PEP', 'Consumer Staples', 'Beverages'),
        ('COST', 'Consumer Staples', 'Consumer Staples Distribution & Retail'),
        ('PM', 'Consumer Staples', 'Tobacco'),
        ('MO', 'Consumer Staples', 'Tobacco'),
        ('CL', 'Consumer Staples', 'Household Products'),
        ('KMB', 'Consumer Staples', 'Household Products'),
        ('MDLZ', 'Consumer Staples', 'Food Products')
        """
    )

    # Seed industrial stocks
    op.execute(
        """
        INSERT INTO sector_mapping (symbol, sector_name, industry) VALUES
        ('BA', 'Industrials', 'Aerospace & Defense'),
        ('CAT', 'Industrials', 'Machinery'),
        ('UNP', 'Industrials', 'Ground Transportation'),
        ('HON', 'Industrials', 'Industrial Conglomerates'),
        ('RTX', 'Industrials', 'Aerospace & Defense'),
        ('UPS', 'Industrials', 'Air Freight & Logistics'),
        ('DE', 'Industrials', 'Machinery'),
        ('LMT', 'Industrials', 'Aerospace & Defense'),
        ('GE', 'Industrials', 'Industrial Conglomerates'),
        ('MMM', 'Industrials', 'Industrial Conglomerates')
        """
    )

    # Seed energy stocks
    op.execute(
        """
        INSERT INTO sector_mapping (symbol, sector_name, industry) VALUES
        ('XOM', 'Energy', 'Oil, Gas & Consumable Fuels'),
        ('CVX', 'Energy', 'Oil, Gas & Consumable Fuels'),
        ('COP', 'Energy', 'Oil, Gas & Consumable Fuels'),
        ('SLB', 'Energy', 'Energy Equipment & Services'),
        ('EOG', 'Energy', 'Oil, Gas & Consumable Fuels'),
        ('PSX', 'Energy', 'Oil, Gas & Consumable Fuels'),
        ('VLO', 'Energy', 'Oil, Gas & Consumable Fuels'),
        ('MPC', 'Energy', 'Oil, Gas & Consumable Fuels'),
        ('OXY', 'Energy', 'Oil, Gas & Consumable Fuels'),
        ('HAL', 'Energy', 'Energy Equipment & Services')
        """
    )

    # Seed materials stocks
    op.execute(
        """
        INSERT INTO sector_mapping (symbol, sector_name, industry) VALUES
        ('LIN', 'Materials', 'Chemicals'),
        ('APD', 'Materials', 'Chemicals'),
        ('SHW', 'Materials', 'Chemicals'),
        ('FCX', 'Materials', 'Metals & Mining'),
        ('NEM', 'Materials', 'Metals & Mining'),
        ('ECL', 'Materials', 'Chemicals'),
        ('DOW', 'Materials', 'Chemicals'),
        ('DD', 'Materials', 'Chemicals'),
        ('NUE', 'Materials', 'Metals & Mining'),
        ('VMC', 'Materials', 'Construction Materials')
        """
    )

    # Seed utilities stocks
    op.execute(
        """
        INSERT INTO sector_mapping (symbol, sector_name, industry) VALUES
        ('NEE', 'Utilities', 'Electric Utilities'),
        ('DUK', 'Utilities', 'Electric Utilities'),
        ('SO', 'Utilities', 'Electric Utilities'),
        ('D', 'Utilities', 'Electric Utilities'),
        ('AEP', 'Utilities', 'Electric Utilities'),
        ('EXC', 'Utilities', 'Electric Utilities'),
        ('SRE', 'Utilities', 'Multi-Utilities'),
        ('XEL', 'Utilities', 'Electric Utilities'),
        ('PCG', 'Utilities', 'Electric Utilities'),
        ('ED', 'Utilities', 'Electric Utilities')
        """
    )

    # Seed real estate stocks
    op.execute(
        """
        INSERT INTO sector_mapping (symbol, sector_name, industry) VALUES
        ('PLD', 'Real Estate', 'Industrial REITs'),
        ('AMT', 'Real Estate', 'Specialized REITs'),
        ('EQIX', 'Real Estate', 'Specialized REITs'),
        ('CCI', 'Real Estate', 'Specialized REITs'),
        ('PSA', 'Real Estate', 'Specialized REITs'),
        ('SPG', 'Real Estate', 'Retail REITs'),
        ('O', 'Real Estate', 'Retail REITs'),
        ('WELL', 'Real Estate', 'Health Care REITs'),
        ('DLR', 'Real Estate', 'Specialized REITs'),
        ('AVB', 'Real Estate', 'Residential REITs')
        """
    )

    # Add benchmark ETFs
    op.execute(
        """
        INSERT INTO sector_mapping (symbol, sector_name, industry) VALUES
        ('SPY', 'Benchmark', 'S&P 500 ETF'),
        ('QQQ', 'Benchmark', 'NASDAQ-100 ETF'),
        ('DIA', 'Benchmark', 'Dow Jones ETF'),
        ('IWM', 'Benchmark', 'Russell 2000 ETF'),
        ('XLK', 'Sector ETF', 'Technology Sector ETF'),
        ('XLV', 'Sector ETF', 'Healthcare Sector ETF'),
        ('XLF', 'Sector ETF', 'Financials Sector ETF'),
        ('XLY', 'Sector ETF', 'Consumer Discretionary ETF'),
        ('XLP', 'Sector ETF', 'Consumer Staples ETF'),
        ('XLI', 'Sector ETF', 'Industrials Sector ETF'),
        ('XLE', 'Sector ETF', 'Energy Sector ETF'),
        ('XLB', 'Sector ETF', 'Materials Sector ETF'),
        ('XLU', 'Sector ETF', 'Utilities Sector ETF'),
        ('XLRE', 'Sector ETF', 'Real Estate Sector ETF')
        """
    )


def downgrade() -> None:
    """
    Drop sector_mapping table.
    """
    op.drop_index("idx_sector_mapping_sector", table_name="sector_mapping")
    op.drop_table("sector_mapping")
