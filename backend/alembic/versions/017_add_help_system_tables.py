"""Add help system tables (Story 11.8a - Task 2)

Revision ID: 017_add_help_system_tables
Revises: 016_analytics_indexes
Create Date: 2025-12-16

This migration creates the help system tables for help articles, glossary terms,
and user feedback on help content.

Tables Created:
---------------
1. help_articles:
   - Help article content with Markdown and HTML
   - PostgreSQL full-text search with GIN index
   - View count and feedback tracking

2. glossary_terms:
   - Wyckoff terminology definitions
   - Phase association (A/B/C/D/E)
   - Related terms linking

3. help_feedback:
   - User feedback on help articles
   - Helpful/not helpful votes
   - Optional user comments
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, TIMESTAMP, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision = "017_add_help_system_tables"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create help system tables."""

    # ============================================================================
    # Table 1: help_articles
    # ============================================================================

    op.create_table(
        "help_articles",
        # Primary key
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # Article identification
        sa.Column("slug", sa.String(200), unique=True, nullable=False, index=True),
        sa.Column("title", sa.String(300), nullable=False),
        # Content
        sa.Column("content_markdown", sa.Text, nullable=False),
        sa.Column("content_html", sa.Text, nullable=False),
        # Classification
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("tags", JSON, nullable=False, server_default="[]"),
        sa.Column("keywords", sa.Text, nullable=False, server_default=""),
        # Engagement metrics
        sa.Column("view_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("helpful_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("not_helpful_count", sa.Integer, nullable=False, server_default="0"),
        # Timestamps
        sa.Column(
            "last_updated",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Check constraints
        sa.CheckConstraint(
            "category IN ('GLOSSARY', 'FAQ', 'TUTORIAL', 'REFERENCE')",
            name="chk_help_article_category",
        ),
        sa.CheckConstraint("view_count >= 0", name="chk_view_count"),
        sa.CheckConstraint("helpful_count >= 0", name="chk_helpful_count"),
        sa.CheckConstraint("not_helpful_count >= 0", name="chk_not_helpful_count"),
    )

    # PostgreSQL full-text search index (GIN)
    # Creates a tsvector column for full-text search on title, content, and keywords
    op.execute(
        """
        ALTER TABLE help_articles
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('english',
                coalesce(title, '') || ' ' ||
                coalesce(content_markdown, '') || ' ' ||
                coalesce(keywords, '')
            )
        ) STORED;
    """
    )

    op.create_index(
        "idx_help_articles_search",
        "help_articles",
        ["search_vector"],
        postgresql_using="gin",
    )

    # ============================================================================
    # Table 2: glossary_terms
    # ============================================================================

    op.create_table(
        "glossary_terms",
        # Primary key
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # Term identification
        sa.Column("term", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(200), unique=True, nullable=False, index=True),
        # Definitions
        sa.Column("short_definition", sa.String(500), nullable=False),
        sa.Column("full_description", sa.Text, nullable=False),
        sa.Column("full_description_html", sa.Text, nullable=False),
        # Wyckoff association
        sa.Column("wyckoff_phase", sa.String(1), nullable=True, index=True),
        # Related terms and tags
        sa.Column("related_terms", JSON, nullable=False, server_default="[]"),
        sa.Column("tags", JSON, nullable=False, server_default="[]"),
        # Timestamps
        sa.Column(
            "last_updated",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Check constraints
        sa.CheckConstraint(
            "wyckoff_phase IS NULL OR wyckoff_phase IN ('A', 'B', 'C', 'D', 'E')",
            name="chk_glossary_wyckoff_phase",
        ),
    )

    # ============================================================================
    # Table 3: help_feedback
    # ============================================================================

    op.create_table(
        "help_feedback",
        # Primary key
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # Article relationship
        sa.Column(
            "article_id",
            UUID(as_uuid=True),
            sa.ForeignKey("help_articles.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Feedback
        sa.Column("helpful", sa.Boolean, nullable=False),
        sa.Column("user_comment", sa.Text, nullable=True),
        # Timestamp
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    """Drop help system tables."""
    op.drop_table("help_feedback")
    op.drop_table("glossary_terms")
    op.drop_table("help_articles")
