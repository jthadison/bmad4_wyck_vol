"""
Integration tests for HelpRepository (Story 11.8a - Task 6)

Tests:
------
- Article CRUD operations
- Glossary term retrieval
- Full-text search functionality
- Feedback submission
- View count tracking
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.help import HelpFeedback
from src.repositories.help_repository import (
    ArticleNotFoundError,
    HelpRepository,
    SearchQueryError,
)


@pytest.mark.integration
class TestHelpRepository:
    """Integration test suite for HelpRepository."""

    async def test_get_articles_all_categories(self, db_session: AsyncSession):
        """Test getting articles with ALL categories filter."""
        repo = HelpRepository(db_session)

        # Note: Assumes database has been seeded with content
        articles, total = await repo.get_articles(category="ALL", limit=50, offset=0)

        assert isinstance(articles, list)
        assert isinstance(total, int)
        assert total >= 0

    async def test_get_articles_with_category_filter(self, db_session: AsyncSession):
        """Test getting articles filtered by category."""
        repo = HelpRepository(db_session)

        # Insert test article
        await db_session.execute(
            text(
                """
            INSERT INTO help_articles (
                id, slug, title, content_markdown, content_html,
                category, tags, keywords, last_updated, created_at
            )
            VALUES (
                :id, 'test-glossary', 'Test Glossary', 'Content', '<p>Content</p>',
                'GLOSSARY', '[]', 'test', :now, :now
            )
            ON CONFLICT (slug) DO NOTHING
            """
            ),
            {"id": str(uuid4()), "now": datetime.now(UTC)},
        )
        await db_session.commit()

        # Get GLOSSARY articles
        articles, total = await repo.get_articles(category="GLOSSARY", limit=50)

        assert total > 0
        for article in articles:
            assert article.category == "GLOSSARY"

    async def test_get_article_by_slug(self, db_session: AsyncSession):
        """Test getting article by slug."""
        repo = HelpRepository(db_session)

        # Insert test article
        test_slug = f"test-article-{uuid4()}"
        await db_session.execute(
            text(
                """
            INSERT INTO help_articles (
                id, slug, title, content_markdown, content_html,
                category, tags, keywords, last_updated, created_at
            )
            VALUES (
                :id, :slug, 'Test Article', 'Content', '<p>Content</p>',
                'FAQ', '[]', 'test', :now, :now
            )
            """
            ),
            {"id": str(uuid4()), "slug": test_slug, "now": datetime.now(UTC)},
        )
        await db_session.commit()

        # Retrieve article
        article = await repo.get_article_by_slug(test_slug)

        assert article.slug == test_slug
        assert article.title == "Test Article"
        assert article.category == "FAQ"

    async def test_get_article_not_found(self, db_session: AsyncSession):
        """Test getting non-existent article raises error."""
        repo = HelpRepository(db_session)

        with pytest.raises(ArticleNotFoundError):
            await repo.get_article_by_slug("nonexistent-slug-xyz")

    async def test_increment_view_count(self, db_session: AsyncSession):
        """Test incrementing article view count."""
        repo = HelpRepository(db_session)

        # Insert test article
        test_slug = f"test-views-{uuid4()}"
        article_id = uuid4()
        await db_session.execute(
            text(
                """
            INSERT INTO help_articles (
                id, slug, title, content_markdown, content_html,
                category, tags, keywords, last_updated, created_at, view_count
            )
            VALUES (
                :id, :slug, 'Test', 'Content', '<p>Content</p>',
                'FAQ', '[]', 'test', :now, :now, 0
            )
            """
            ),
            {"id": str(article_id), "slug": test_slug, "now": datetime.now(UTC)},
        )
        await db_session.commit()

        # Increment view count
        await repo.increment_view_count(article_id)

        # Verify increment
        result = await db_session.execute(
            text("SELECT view_count FROM help_articles WHERE id = :id"),
            {"id": str(article_id)},
        )
        view_count = result.scalar()
        assert view_count == 1

    @pytest.mark.skip(reason="PostgreSQL full-text search not available in SQLite")
    async def test_search_articles(self, db_session: AsyncSession):
        """Test full-text search."""
        repo = HelpRepository(db_session)

        # Insert test article with searchable content
        test_slug = f"search-test-{uuid4()}"
        await db_session.execute(
            text(
                """
            INSERT INTO help_articles (
                id, slug, title, content_markdown, content_html,
                category, tags, keywords, last_updated, created_at
            )
            VALUES (
                :id, :slug, 'Unique Search Term XYZ', 'Content with XYZ',
                '<p>Content with XYZ</p>',
                'FAQ', '[]', 'xyz unique', :now, :now
            )
            """
            ),
            {"id": str(uuid4()), "slug": test_slug, "now": datetime.now(UTC)},
        )
        await db_session.commit()

        # Search for unique term
        results, total = await repo.search_articles(query="XYZ", limit=20)

        assert total > 0
        assert any(r.slug == test_slug for r in results)

    async def test_search_empty_query(self, db_session: AsyncSession):
        """Test that empty search query raises error."""
        repo = HelpRepository(db_session)

        with pytest.raises(SearchQueryError):
            await repo.search_articles(query="", limit=20)

    async def test_get_glossary_terms(self, db_session: AsyncSession):
        """Test getting glossary terms."""
        repo = HelpRepository(db_session)

        # Insert test glossary term
        test_slug = f"test-term-{uuid4()}"
        await db_session.execute(
            text(
                """
            INSERT INTO glossary_terms (
                id, term, slug, short_definition, full_description,
                full_description_html, wyckoff_phase, related_terms, tags,
                last_updated, created_at
            )
            VALUES (
                :id, 'Test Term', :slug, 'Definition', '', '<p>Full</p>',
                'C', '[]', '[]', :now, :now
            )
            """
            ),
            {"id": str(uuid4()), "slug": test_slug, "now": datetime.now(UTC)},
        )
        await db_session.commit()

        # Get all terms
        terms, total = await repo.get_glossary_terms()

        assert total > 0
        assert any(t.slug == test_slug for t in terms)

    async def test_get_glossary_terms_by_phase(self, db_session: AsyncSession):
        """Test getting glossary terms filtered by phase."""
        repo = HelpRepository(db_session)

        # Insert term with specific phase
        test_slug = f"phase-test-{uuid4()}"
        await db_session.execute(
            text(
                """
            INSERT INTO glossary_terms (
                id, term, slug, short_definition, full_description,
                full_description_html, wyckoff_phase, related_terms, tags,
                last_updated, created_at
            )
            VALUES (
                :id, 'Phase Test', :slug, 'Def', '', '<p>Full</p>',
                'D', '[]', '[]', :now, :now
            )
            """
            ),
            {"id": str(uuid4()), "slug": test_slug, "now": datetime.now(UTC)},
        )
        await db_session.commit()

        # Filter by phase D
        terms, total = await repo.get_glossary_terms(wyckoff_phase="D")

        assert all(t.wyckoff_phase == "D" for t in terms)

    async def test_create_feedback(self, db_session: AsyncSession):
        """Test creating user feedback."""
        repo = HelpRepository(db_session)

        # Insert test article
        article_id = uuid4()
        await db_session.execute(
            text(
                """
            INSERT INTO help_articles (
                id, slug, title, content_markdown, content_html,
                category, tags, keywords, last_updated, created_at
            )
            VALUES (
                :id, :slug, 'Feedback Test', 'Content', '<p>Content</p>',
                'FAQ', '[]', 'test', :now, :now
            )
            """
            ),
            {"id": str(article_id), "slug": f"feedback-test-{uuid4()}", "now": datetime.now(UTC)},
        )
        await db_session.commit()

        # Create feedback
        feedback = HelpFeedback(
            article_id=article_id,
            helpful=True,
            user_comment="Very helpful!",
        )

        feedback_id = await repo.create_feedback(feedback)

        assert feedback_id is not None

        # Verify feedback was created
        result = await db_session.execute(
            text("SELECT COUNT(*) FROM help_feedback WHERE id = :id"),
            {"id": str(feedback_id)},
        )
        count = result.scalar()
        assert count == 1

    async def test_update_feedback_counts(self, db_session: AsyncSession):
        """Test updating helpful/not_helpful counts."""
        repo = HelpRepository(db_session)

        # Insert test article
        article_id = uuid4()
        await db_session.execute(
            text(
                """
            INSERT INTO help_articles (
                id, slug, title, content_markdown, content_html,
                category, tags, keywords, last_updated, created_at,
                helpful_count, not_helpful_count
            )
            VALUES (
                :id, :slug, 'Count Test', 'Content', '<p>Content</p>',
                'FAQ', '[]', 'test', :now, :now, 0, 0
            )
            """
            ),
            {"id": str(article_id), "slug": f"count-test-{uuid4()}", "now": datetime.now(UTC)},
        )
        await db_session.commit()

        # Update helpful count
        await repo.update_feedback_counts(article_id, helpful=True)
        await db_session.commit()

        # Verify count
        result = await db_session.execute(
            text("SELECT helpful_count FROM help_articles WHERE id = :id"),
            {"id": str(article_id)},
        )
        count = result.scalar()
        assert count == 1
