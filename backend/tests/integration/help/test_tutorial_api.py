"""
Integration tests for Tutorial API endpoints (Story 11.8b - Task 17)

Purpose:
--------
Tests the complete tutorial API flow including database interactions,
seeding, retrieval, filtering, and completion tracking.

Tests:
------
- GET /help/tutorials (list with filtering)
- GET /help/tutorials/{slug} (single tutorial retrieval)
- POST /help/tutorials/{slug}/complete (completion tracking)
- Error handling (404, validation errors)
- Data integrity and JSONB step storage

Author: Story 11.8b (Task 17)
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.orm.models import TutorialORM


@pytest.mark.integration
class TestTutorialListAPI:
    """Test GET /help/tutorials endpoint."""

    @pytest.mark.asyncio
    async def test_get_tutorials_empty(self, async_client: AsyncClient):
        """Test getting tutorials when database is empty."""
        response = await async_client.get("/api/v1/help/tutorials")

        assert response.status_code == 200
        data = response.json()
        assert "tutorials" in data
        assert "total_count" in data
        assert data["total_count"] == 0
        assert data["tutorials"] == []

    @pytest.mark.asyncio
    async def test_get_tutorials_with_data(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test getting tutorials when tutorials exist."""
        # Create sample tutorials
        tutorial1 = TutorialORM(
            id=uuid4(),
            slug="test-tutorial-1",
            title="Test Tutorial 1",
            description="First test tutorial",
            difficulty="BEGINNER",
            estimated_time_minutes=10,
            steps=[
                {
                    "step_number": 1,
                    "title": "Step 1",
                    "content_markdown": "Content",
                    "content_html": "<p>Content</p>",
                    "action_required": None,
                    "ui_highlight": None,
                }
            ],
            tags=["test"],
            completion_count=0,
        )

        tutorial2 = TutorialORM(
            id=uuid4(),
            slug="test-tutorial-2",
            title="Test Tutorial 2",
            description="Second test tutorial",
            difficulty="INTERMEDIATE",
            estimated_time_minutes=15,
            steps=[
                {
                    "step_number": 1,
                    "title": "Step 1",
                    "content_markdown": "Content",
                    "content_html": "<p>Content</p>",
                    "action_required": None,
                    "ui_highlight": None,
                }
            ],
            tags=["test"],
            completion_count=5,
        )

        db_session.add(tutorial1)
        db_session.add(tutorial2)
        await db_session.commit()

        # Fetch tutorials
        response = await async_client.get("/api/v1/help/tutorials")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2
        assert len(data["tutorials"]) == 2

        # Check ordering (should be by difficulty ASC, then estimated_time ASC)
        assert data["tutorials"][0]["difficulty"] == "BEGINNER"
        assert data["tutorials"][1]["difficulty"] == "INTERMEDIATE"

    @pytest.mark.asyncio
    async def test_get_tutorials_filter_by_difficulty(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test filtering tutorials by difficulty."""
        # Create tutorials with different difficulties
        beginner = TutorialORM(
            id=uuid4(),
            slug="beginner-tutorial",
            title="Beginner Tutorial",
            description="For beginners",
            difficulty="BEGINNER",
            estimated_time_minutes=10,
            steps=[
                {
                    "step_number": 1,
                    "title": "Step 1",
                    "content_markdown": "Content",
                    "content_html": "<p>Content</p>",
                    "action_required": None,
                    "ui_highlight": None,
                }
            ],
            tags=[],
            completion_count=0,
        )

        intermediate = TutorialORM(
            id=uuid4(),
            slug="intermediate-tutorial",
            title="Intermediate Tutorial",
            description="For intermediate users",
            difficulty="INTERMEDIATE",
            estimated_time_minutes=20,
            steps=[
                {
                    "step_number": 1,
                    "title": "Step 1",
                    "content_markdown": "Content",
                    "content_html": "<p>Content</p>",
                    "action_required": None,
                    "ui_highlight": None,
                }
            ],
            tags=[],
            completion_count=0,
        )

        db_session.add(beginner)
        db_session.add(intermediate)
        await db_session.commit()

        # Filter by BEGINNER
        response = await async_client.get("/api/v1/help/tutorials?difficulty=BEGINNER")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert data["tutorials"][0]["difficulty"] == "BEGINNER"
        assert data["tutorials"][0]["slug"] == "beginner-tutorial"

        # Filter by INTERMEDIATE
        response = await async_client.get("/api/v1/help/tutorials?difficulty=INTERMEDIATE")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert data["tutorials"][0]["difficulty"] == "INTERMEDIATE"
        assert data["tutorials"][0]["slug"] == "intermediate-tutorial"

    @pytest.mark.asyncio
    async def test_get_tutorials_pagination(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test pagination of tutorial list."""
        # Create 5 tutorials
        for i in range(5):
            tutorial = TutorialORM(
                id=uuid4(),
                slug=f"tutorial-{i}",
                title=f"Tutorial {i}",
                description=f"Description {i}",
                difficulty="BEGINNER",
                estimated_time_minutes=10 + i,
                steps=[
                    {
                        "step_number": 1,
                        "title": "Step 1",
                        "content_markdown": "Content",
                        "content_html": "<p>Content</p>",
                        "action_required": None,
                        "ui_highlight": None,
                    }
                ],
                tags=[],
                completion_count=0,
            )
            db_session.add(tutorial)

        await db_session.commit()

        # Get first 3
        response = await async_client.get("/api/v1/help/tutorials?limit=3&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["tutorials"]) == 3
        assert data["total_count"] == 5

        # Get next 2
        response = await async_client.get("/api/v1/help/tutorials?limit=3&offset=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["tutorials"]) == 2
        assert data["total_count"] == 5


@pytest.mark.integration
class TestTutorialDetailAPI:
    """Test GET /help/tutorials/{slug} endpoint."""

    @pytest.mark.asyncio
    async def test_get_tutorial_by_slug_success(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test getting a single tutorial by slug."""
        tutorial = TutorialORM(
            id=uuid4(),
            slug="test-spring-tutorial",
            title="Identifying Springs",
            description="Learn to identify Spring patterns",
            difficulty="INTERMEDIATE",
            estimated_time_minutes=15,
            steps=[
                {
                    "step_number": 1,
                    "title": "What is a Spring?",
                    "content_markdown": "A Spring is...",
                    "content_html": "<p>A Spring is...</p>",
                    "action_required": "Read the definition",
                    "ui_highlight": None,
                },
                {
                    "step_number": 2,
                    "title": "Identify Creek Level",
                    "content_markdown": "Find the Creek...",
                    "content_html": "<p>Find the Creek...</p>",
                    "action_required": "Mark the Creek level",
                    "ui_highlight": "#creek-marker",
                },
            ],
            tags=["spring", "patterns", "intermediate"],
            completion_count=10,
        )

        db_session.add(tutorial)
        await db_session.commit()

        # Fetch by slug
        response = await async_client.get("/api/v1/help/tutorials/test-spring-tutorial")

        assert response.status_code == 200
        data = response.json()

        assert data["slug"] == "test-spring-tutorial"
        assert data["title"] == "Identifying Springs"
        assert data["difficulty"] == "INTERMEDIATE"
        assert data["estimated_time_minutes"] == 15
        assert len(data["steps"]) == 2

        # Check step details
        step1 = data["steps"][0]
        assert step1["step_number"] == 1
        assert step1["title"] == "What is a Spring?"
        assert step1["action_required"] == "Read the definition"
        assert step1["ui_highlight"] is None

        step2 = data["steps"][1]
        assert step2["step_number"] == 2
        assert step2["title"] == "Identify Creek Level"
        assert step2["ui_highlight"] == "#creek-marker"

    @pytest.mark.asyncio
    async def test_get_tutorial_by_slug_not_found(self, async_client: AsyncClient):
        """Test getting non-existent tutorial returns 404."""
        response = await async_client.get("/api/v1/help/tutorials/non-existent-tutorial")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


@pytest.mark.integration
class TestTutorialCompletionAPI:
    """Test POST /help/tutorials/{slug}/complete endpoint."""

    @pytest.mark.asyncio
    async def test_complete_tutorial_success(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test completing a tutorial increments completion_count."""
        tutorial = TutorialORM(
            id=uuid4(),
            slug="completion-test",
            title="Completion Test",
            description="Test completion",
            difficulty="BEGINNER",
            estimated_time_minutes=5,
            steps=[
                {
                    "step_number": 1,
                    "title": "Step 1",
                    "content_markdown": "Content",
                    "content_html": "<p>Content</p>",
                    "action_required": None,
                    "ui_highlight": None,
                }
            ],
            tags=[],
            completion_count=5,
        )

        db_session.add(tutorial)
        await db_session.commit()

        # Complete the tutorial
        response = await async_client.post("/api/v1/help/tutorials/completion-test/complete")

        assert response.status_code == 204

        # Verify completion_count incremented
        await db_session.refresh(tutorial)
        assert tutorial.completion_count == 6

    @pytest.mark.asyncio
    async def test_complete_tutorial_not_found(self, async_client: AsyncClient):
        """Test completing non-existent tutorial returns 404."""
        response = await async_client.post("/api/v1/help/tutorials/non-existent/complete")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_complete_tutorial_multiple_times(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test that completing tutorial multiple times increments each time."""
        tutorial = TutorialORM(
            id=uuid4(),
            slug="multi-complete",
            title="Multi Complete",
            description="Test",
            difficulty="BEGINNER",
            estimated_time_minutes=5,
            steps=[
                {
                    "step_number": 1,
                    "title": "Step 1",
                    "content_markdown": "Content",
                    "content_html": "<p>Content</p>",
                    "action_required": None,
                    "ui_highlight": None,
                }
            ],
            tags=[],
            completion_count=0,
        )

        db_session.add(tutorial)
        await db_session.commit()

        # Complete 3 times
        for i in range(3):
            response = await async_client.post("/api/v1/help/tutorials/multi-complete/complete")
            assert response.status_code == 204

        # Verify count is 3
        await db_session.refresh(tutorial)
        assert tutorial.completion_count == 3


@pytest.mark.integration
class TestTutorialDataIntegrity:
    """Test data integrity for tutorial storage."""

    @pytest.mark.asyncio
    async def test_tutorial_steps_jsonb_storage(self, db_session: AsyncSession):
        """Test that tutorial steps are correctly stored as JSONB."""
        tutorial = TutorialORM(
            id=uuid4(),
            slug="jsonb-test",
            title="JSONB Test",
            description="Test JSONB storage",
            difficulty="BEGINNER",
            estimated_time_minutes=10,
            steps=[
                {
                    "step_number": 1,
                    "title": "First Step",
                    "content_markdown": "# Heading\\n\\nParagraph",
                    "content_html": "<h1>Heading</h1><p>Paragraph</p>",
                    "action_required": "Click here",
                    "ui_highlight": "#button",
                },
                {
                    "step_number": 2,
                    "title": "Second Step",
                    "content_markdown": "More content",
                    "content_html": "<p>More content</p>",
                    "action_required": None,
                    "ui_highlight": None,
                },
            ],
            tags=["jsonb", "test"],
            completion_count=0,
        )

        db_session.add(tutorial)
        await db_session.commit()

        # Retrieve and verify
        result = await db_session.execute(
            select(TutorialORM).where(TutorialORM.slug == "jsonb-test")
        )
        retrieved = result.scalar_one()

        assert len(retrieved.steps) == 2
        assert retrieved.steps[0]["step_number"] == 1
        assert retrieved.steps[0]["title"] == "First Step"
        assert retrieved.steps[0]["action_required"] == "Click here"
        assert retrieved.steps[0]["ui_highlight"] == "#button"

        assert retrieved.steps[1]["step_number"] == 2
        assert retrieved.steps[1]["action_required"] is None

    @pytest.mark.asyncio
    async def test_tutorial_unique_slug_constraint(self, db_session: AsyncSession):
        """Test that slug uniqueness is enforced."""
        tutorial1 = TutorialORM(
            id=uuid4(),
            slug="unique-slug",
            title="Tutorial 1",
            description="First",
            difficulty="BEGINNER",
            estimated_time_minutes=5,
            steps=[
                {
                    "step_number": 1,
                    "title": "Step",
                    "content_markdown": "Content",
                    "content_html": "<p>Content</p>",
                    "action_required": None,
                    "ui_highlight": None,
                }
            ],
            tags=[],
            completion_count=0,
        )

        tutorial2 = TutorialORM(
            id=uuid4(),
            slug="unique-slug",  # Same slug
            title="Tutorial 2",
            description="Second",
            difficulty="BEGINNER",
            estimated_time_minutes=5,
            steps=[
                {
                    "step_number": 1,
                    "title": "Step",
                    "content_markdown": "Content",
                    "content_html": "<p>Content</p>",
                    "action_required": None,
                    "ui_highlight": None,
                }
            ],
            tags=[],
            completion_count=0,
        )

        db_session.add(tutorial1)
        await db_session.commit()

        db_session.add(tutorial2)

        # Should raise integrity error on commit
        with pytest.raises(Exception):  # SQLAlchemy IntegrityError
            await db_session.commit()
