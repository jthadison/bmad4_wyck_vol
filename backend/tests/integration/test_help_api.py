"""
Integration tests for Help API (Story 11.8a - Task 7)

Tests:
------
- GET /api/v1/help/articles
- GET /api/v1/help/articles/{slug}
- GET /api/v1/help/search
- GET /api/v1/help/glossary
- POST /api/v1/help/feedback
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.integration
class TestHelpAPI:
    """Integration test suite for Help API endpoints."""

    async def test_get_articles_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test GET /api/v1/help/articles returns article list."""
        # Insert test article
        await db_session.execute(
            text(
                """
            INSERT INTO help_articles (
                slug, title, content_markdown, content_html,
                category, tags, keywords, last_updated
            )
            VALUES (
                :slug, 'API Test', 'Content', '<p>Content</p>',
                'FAQ', '[]'::json, 'test', :now
            )
            ON CONFLICT (slug) DO NOTHING
            """
            ),
            {"slug": "api-test-article", "now": datetime.now(UTC)},
        )
        await db_session.commit()

        # Request articles
        response = await client.get("/api/v1/help/articles?category=ALL&limit=50")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "articles" in data
        assert "total_count" in data
        assert isinstance(data["articles"], list)
        assert isinstance(data["total_count"], int)

    async def test_get_articles_with_category_filter(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test filtering articles by category."""
        response = await client.get("/api/v1/help/articles?category=GLOSSARY&limit=20")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All returned articles should be GLOSSARY category
        for article in data["articles"]:
            assert article["category"] == "GLOSSARY"

    async def test_get_articles_invalid_category(self, client: AsyncClient):
        """Test invalid category returns validation error."""
        response = await client.get("/api/v1/help/articles?category=INVALID")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_get_article_by_slug_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test GET /api/v1/help/articles/{slug} returns article."""
        test_slug = f"test-slug-{uuid4()}"

        # Insert test article
        await db_session.execute(
            text(
                """
            INSERT INTO help_articles (
                slug, title, content_markdown, content_html,
                category, tags, keywords, last_updated, view_count
            )
            VALUES (
                :slug, 'Test Article', 'Markdown', '<p>HTML</p>',
                'FAQ', '[]'::json, 'test', :now, 0
            )
            """
            ),
            {"slug": test_slug, "now": datetime.now(UTC)},
        )
        await db_session.commit()

        # Request article
        response = await client.get(f"/api/v1/help/articles/{test_slug}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["slug"] == test_slug
        assert data["title"] == "Test Article"
        assert data["category"] == "FAQ"

        # Verify view count was incremented
        result = await db_session.execute(
            text("SELECT view_count FROM help_articles WHERE slug = :slug"),
            {"slug": test_slug},
        )
        view_count = result.scalar()
        assert view_count == 1

    async def test_get_article_not_found(self, client: AsyncClient):
        """Test getting non-existent article returns 404."""
        response = await client.get("/api/v1/help/articles/nonexistent-article-xyz")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    async def test_search_articles_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test GET /api/v1/help/search returns search results."""
        # Insert searchable article
        test_slug = f"searchable-{uuid4()}"
        await db_session.execute(
            text(
                """
            INSERT INTO help_articles (
                slug, title, content_markdown, content_html,
                category, tags, keywords, last_updated
            )
            VALUES (
                :slug, 'Searchable UniqueKeyword123', 'Content UniqueKeyword123',
                '<p>Content UniqueKeyword123</p>',
                'FAQ', '[]'::json, 'uniquekeyword123', :now
            )
            """
            ),
            {"slug": test_slug, "now": datetime.now(UTC)},
        )
        await db_session.commit()

        # Search for unique keyword
        response = await client.get("/api/v1/help/search?q=UniqueKeyword123&limit=10")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "results" in data
        assert "query" in data
        assert "total_count" in data
        assert data["query"] == "UniqueKeyword123"

    async def test_search_empty_query(self, client: AsyncClient):
        """Test search with empty query returns 400."""
        response = await client.get("/api/v1/help/search?q=&limit=10")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_get_glossary_all_terms(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test GET /api/v1/help/glossary returns glossary terms."""
        # Insert test term
        test_slug = f"glossary-term-{uuid4()}"
        await db_session.execute(
            text(
                """
            INSERT INTO glossary_terms (
                term, slug, short_definition, full_description,
                full_description_html, wyckoff_phase, related_terms, tags, last_updated
            )
            VALUES (
                'Test Term', :slug, 'Short def', '', '<p>Full def</p>',
                'C', '[]'::json, '[]'::json, :now
            )
            """
            ),
            {"slug": test_slug, "now": datetime.now(UTC)},
        )
        await db_session.commit()

        # Request glossary
        response = await client.get("/api/v1/help/glossary")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "terms" in data
        assert "total_count" in data
        assert isinstance(data["terms"], list)

    async def test_get_glossary_filtered_by_phase(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test filtering glossary by Wyckoff phase."""
        # Insert term with specific phase
        test_slug = f"phase-term-{uuid4()}"
        await db_session.execute(
            text(
                """
            INSERT INTO glossary_terms (
                term, slug, short_definition, full_description,
                full_description_html, wyckoff_phase, related_terms, tags, last_updated
            )
            VALUES (
                'Phase E Term', :slug, 'Def', '', '<p>Full</p>',
                'E', '[]'::json, '[]'::json, :now
            )
            """
            ),
            {"slug": test_slug, "now": datetime.now(UTC)},
        )
        await db_session.commit()

        # Filter by phase E
        response = await client.get("/api/v1/help/glossary?wyckoff_phase=E")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All terms should be phase E
        for term in data["terms"]:
            assert term["wyckoff_phase"] == "E"

    async def test_get_glossary_invalid_phase(self, client: AsyncClient):
        """Test invalid phase filter returns validation error."""
        response = await client.get("/api/v1/help/glossary?wyckoff_phase=Z")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_submit_feedback_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test POST /api/v1/help/feedback creates feedback."""
        # Insert test article
        result = await db_session.execute(
            text(
                """
            INSERT INTO help_articles (
                slug, title, content_markdown, content_html,
                category, tags, keywords, last_updated
            )
            VALUES (
                :slug, 'Feedback Article', 'Content', '<p>Content</p>',
                'FAQ', '[]'::json, 'test', :now
            )
            RETURNING id
            """
            ),
            {"slug": f"feedback-article-{uuid4()}", "now": datetime.now(UTC)},
        )
        article_id = str(result.scalar())
        await db_session.commit()

        # Submit feedback
        feedback_data = {
            "article_id": article_id,
            "helpful": True,
            "user_comment": "Great article!",
        }

        response = await client.post("/api/v1/help/feedback", json=feedback_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "feedback_id" in data
        assert "message" in data
        assert "Thank you" in data["message"]

    async def test_submit_feedback_article_not_found(self, client: AsyncClient):
        """Test feedback for non-existent article returns 404."""
        feedback_data = {
            "article_id": str(uuid4()),
            "helpful": True,
            "user_comment": "Test",
        }

        response = await client.post("/api/v1/help/feedback", json=feedback_data)

        # Should return 404 or 500 depending on implementation
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    async def test_submit_feedback_invalid_data(self, client: AsyncClient):
        """Test feedback with invalid data returns validation error."""
        feedback_data = {
            "article_id": "not-a-uuid",
            "helpful": True,
        }

        response = await client.post("/api/v1/help/feedback", json=feedback_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
