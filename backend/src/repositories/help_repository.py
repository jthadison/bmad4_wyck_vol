"""
Help Repository (Story 11.8a - Task 6, Story 11.8b - Task 4)

Purpose:
--------
Database operations for help system including articles, glossary terms,
tutorials, and user feedback. Implements PostgreSQL full-text search.

Classes:
--------
- HelpRepository: Async repository for help content
- ArticleNotFoundError: Raised when article doesn't exist
- TutorialNotFoundError: Raised when tutorial doesn't exist
- SearchQueryError: Raised when search query is invalid

Integration:
------------
- Used by help API endpoints
- Implements PostgreSQL full-text search with ts_vector
- Handles feedback submission and view count tracking
- Tutorial CRUD operations and completion tracking

Author: Story 11.8a (Task 6), Story 11.8b (Task 4)
"""

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.help import (
    GlossaryTerm,
    HelpArticle,
    HelpFeedback,
    HelpSearchResult,
    Tutorial,
)
from src.orm.models import GlossaryTermORM, HelpArticleORM, TutorialORM

logger = structlog.get_logger(__name__)


class ArticleNotFoundError(Exception):
    """Raised when help article doesn't exist."""

    pass


class TutorialNotFoundError(Exception):
    """Raised when tutorial doesn't exist (Story 11.8b)."""

    pass


class SearchQueryError(Exception):
    """Raised when search query is invalid."""

    pass


class HelpRepository:
    """
    Repository for help content database operations.

    Provides async methods for managing help articles, glossary terms,
    and user feedback with full-text search support.

    Example:
    --------
    >>> async with session.begin():
    ...     repo = HelpRepository(session)
    ...     articles = await repo.get_articles(category="GLOSSARY", limit=10)
    ...     article = await repo.get_article_by_slug("spring-pattern")
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Parameters:
        -----------
        session : AsyncSession
            SQLAlchemy async session
        """
        self.session = session

    async def get_articles(
        self,
        category: str = "ALL",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[HelpArticle], int]:
        """
        Get help articles with optional category filtering.

        Parameters:
        -----------
        category : str
            Filter by category (GLOSSARY, FAQ, TUTORIAL, REFERENCE, ALL)
            Default: ALL
        limit : int
            Maximum number of articles to return (default: 50, max: 100)
        offset : int
            Number of articles to skip for pagination (default: 0)

        Returns:
        --------
        tuple[list[HelpArticle], int]
            Tuple of (articles list, total count before pagination)

        Example:
        --------
        >>> articles, total = await repo.get_articles(category="FAQ", limit=20)
        >>> print(f"Showing {len(articles)} of {total} FAQ articles")
        """
        # Enforce limit constraints
        limit = min(limit, 100)

        # Build base query using ORM
        query = select(HelpArticleORM)

        # Add category filter using parameterized query
        if category != "ALL":
            query = query.where(HelpArticleORM.category == category)

        # Get total count using ORM
        count_query = select(func.count()).select_from(HelpArticleORM)
        if category != "ALL":
            count_query = count_query.where(HelpArticleORM.category == category)

        count_result = await self.session.execute(count_query)
        total_count = count_result.scalar() or 0

        # Add pagination
        query = query.order_by(HelpArticleORM.title).limit(limit).offset(offset)

        # Execute query
        result = await self.session.execute(query)
        orm_articles = result.scalars().all()

        # Convert ORM objects to Pydantic models
        articles = [self._orm_to_article(orm_obj) for orm_obj in orm_articles]

        logger.info(
            "Fetched articles",
            category=category,
            count=len(articles),
            total=total_count,
            limit=limit,
            offset=offset,
        )

        return articles, total_count

    async def get_article_by_slug(self, slug: str) -> HelpArticle:
        """
        Get help article by slug.

        Parameters:
        -----------
        slug : str
            Article slug (URL-friendly identifier)

        Returns:
        --------
        HelpArticle
            Help article model

        Raises:
        -------
        ArticleNotFoundError
            If article with slug doesn't exist

        Example:
        --------
        >>> article = await repo.get_article_by_slug("spring-pattern")
        >>> print(article.title)
        'Spring Pattern'
        """
        query = text(
            """
            SELECT *
            FROM help_articles
            WHERE slug = :slug
            """
        )

        result = await self.session.execute(query, {"slug": slug})
        row = result.first()

        if not row:
            raise ArticleNotFoundError(f"Article not found: {slug}")

        logger.debug("Fetched article by slug", slug=slug)

        return self._row_to_article(row)

    async def increment_view_count(self, article_id: UUID) -> None:
        """
        Increment view count for an article.

        Parameters:
        -----------
        article_id : UUID
            Article identifier

        Example:
        --------
        >>> await repo.increment_view_count(article.id)
        """
        query = text(
            """
            UPDATE help_articles
            SET view_count = view_count + 1
            WHERE id = :article_id
            """
        )

        await self.session.execute(query, {"article_id": article_id})
        await self.session.commit()

        logger.debug("Incremented view count", article_id=str(article_id))

    async def search_articles(
        self,
        query: str,
        limit: int = 20,
    ) -> tuple[list[HelpSearchResult], int]:
        """
        Full-text search across help articles.

        Uses PostgreSQL's ts_vector for full-text search with ranking.

        Parameters:
        -----------
        query : str
            Search query string
        limit : int
            Maximum number of results (default: 20)

        Returns:
        --------
        tuple[list[HelpSearchResult], int]
            Tuple of (search results, total count)

        Raises:
        -------
        SearchQueryError
            If query is empty or invalid

        Example:
        --------
        >>> results, total = await repo.search_articles("spring pattern")
        >>> for result in results:
        ...     print(f"{result.title}: {result.snippet}")
        """
        if not query or not query.strip():
            raise SearchQueryError("Search query cannot be empty")

        # Sanitize query for PostgreSQL full-text search
        # Convert to tsquery format: replace spaces with &
        sanitized_query = " & ".join(query.strip().split())

        try:
            # PostgreSQL full-text search query with ranking and count in single query
            # Optimized for <200ms performance: removed snippet generation, using ts_rank (faster than ts_rank_cd)
            search_query = text(
                """
                WITH search_results AS (
                    SELECT
                        id,
                        slug,
                        title,
                        category,
                        ts_rank(search_vector, query) AS rank,
                        LEFT(content_markdown, 150) AS snippet,
                        COUNT(*) OVER() AS total_count
                    FROM help_articles,
                         to_tsquery('english', :query) AS query
                    WHERE search_vector @@ query
                    ORDER BY rank DESC
                    LIMIT :limit
                )
                SELECT * FROM search_results
                """
            )

            result = await self.session.execute(
                search_query,
                {"query": sanitized_query, "limit": limit},
            )
            rows = result.fetchall()

            # Get total count from first row (all rows have same count due to window function)
            total_count = rows[0].total_count if rows else 0

            # Convert rows to HelpSearchResult models
            results = [
                HelpSearchResult(
                    id=row.id,
                    slug=row.slug,
                    title=row.title,
                    category=row.category,
                    snippet=row.snippet,
                    rank=float(row.rank),
                )
                for row in rows
            ]

            logger.info(
                "Search completed",
                query=query,
                results_count=len(results),
                total=total_count,
            )

            return results, total_count

        except Exception as e:
            logger.error("Search query failed", query=query, error=str(e), exc_info=True)
            raise SearchQueryError(f"Invalid search query: {e}") from e

    async def get_glossary_terms(
        self,
        wyckoff_phase: str | None = None,
    ) -> tuple[list[GlossaryTerm], int]:
        """
        Get glossary terms with optional phase filtering.

        Parameters:
        -----------
        wyckoff_phase : str | None
            Filter by Wyckoff phase (A/B/C/D/E) or None for all

        Returns:
        --------
        tuple[list[GlossaryTerm], int]
            Tuple of (glossary terms, total count)

        Example:
        --------
        >>> terms, total = await repo.get_glossary_terms(wyckoff_phase="C")
        >>> for term in terms:
        ...     print(f"{term.term}: {term.short_definition}")
        """
        # Build query using ORM
        query = select(GlossaryTermORM)

        if wyckoff_phase:
            query = query.where(GlossaryTermORM.wyckoff_phase == wyckoff_phase)

        query = query.order_by(GlossaryTermORM.term)

        # Get total count using ORM
        count_query = select(func.count()).select_from(GlossaryTermORM)
        if wyckoff_phase:
            count_query = count_query.where(GlossaryTermORM.wyckoff_phase == wyckoff_phase)

        count_result = await self.session.execute(count_query)
        total_count = count_result.scalar() or 0

        # Execute query
        result = await self.session.execute(query)
        orm_terms = result.scalars().all()

        # Convert ORM objects to Pydantic models
        terms = [self._orm_to_glossary_term(orm_obj) for orm_obj in orm_terms]

        logger.info(
            "Fetched glossary terms",
            wyckoff_phase=wyckoff_phase,
            count=len(terms),
            total=total_count,
        )

        return terms, total_count

    async def get_glossary_term_by_slug(self, slug: str) -> GlossaryTerm:
        """
        Get glossary term by slug.

        Parameters:
        -----------
        slug : str
            Term slug

        Returns:
        --------
        GlossaryTerm
            Glossary term model

        Raises:
        -------
        ArticleNotFoundError
            If term doesn't exist

        Example:
        --------
        >>> term = await repo.get_glossary_term_by_slug("spring")
        >>> print(term.short_definition)
        """
        query = text(
            """
            SELECT *
            FROM glossary_terms
            WHERE slug = :slug
            """
        )

        result = await self.session.execute(query, {"slug": slug})
        row = result.first()

        if not row:
            raise ArticleNotFoundError(f"Glossary term not found: {slug}")

        logger.debug("Fetched glossary term by slug", slug=slug)

        return self._row_to_glossary_term(row)

    async def create_feedback(self, feedback: HelpFeedback) -> UUID:
        """
        Create user feedback on help article.

        Also updates helpful/not_helpful counts on the article.

        Parameters:
        -----------
        feedback : HelpFeedback
            Feedback model

        Returns:
        --------
        UUID
            Feedback ID

        Example:
        --------
        >>> feedback = HelpFeedback(
        ...     article_id=article.id,
        ...     helpful=True,
        ...     user_comment="Very clear explanation"
        ... )
        >>> feedback_id = await repo.create_feedback(feedback)
        """
        try:
            # Insert feedback
            insert_query = text(
                """
                INSERT INTO help_feedback (id, article_id, helpful, user_comment, created_at)
                VALUES (:id, :article_id, :helpful, :user_comment, :created_at)
                RETURNING id
                """
            )

            await self.session.execute(
                insert_query,
                {
                    "id": feedback.id,
                    "article_id": feedback.article_id,
                    "helpful": feedback.helpful,
                    "user_comment": feedback.user_comment,
                    "created_at": feedback.created_at,
                },
            )

            # Update article helpful counts
            await self.update_feedback_counts(feedback.article_id, feedback.helpful)

            await self.session.commit()

            logger.info(
                "Created feedback",
                feedback_id=str(feedback.id),
                article_id=str(feedback.article_id),
                helpful=feedback.helpful,
            )

            return feedback.id

        except IntegrityError as e:
            await self.session.rollback()
            logger.error(
                "Failed to create feedback",
                article_id=str(feedback.article_id),
                error=str(e),
            )
            raise

    async def update_feedback_counts(self, article_id: UUID, helpful: bool) -> None:
        """
        Update helpful/not_helpful counts on article.

        Parameters:
        -----------
        article_id : UUID
            Article identifier
        helpful : bool
            Whether feedback was helpful

        Example:
        --------
        >>> await repo.update_feedback_counts(article_id, helpful=True)
        """
        # Use explicit conditional instead of f-string interpolation
        if helpful:
            query = text(
                """
                UPDATE help_articles
                SET helpful_count = helpful_count + 1
                WHERE id = :article_id
                """
            )
        else:
            query = text(
                """
                UPDATE help_articles
                SET not_helpful_count = not_helpful_count + 1
                WHERE id = :article_id
                """
            )

        await self.session.execute(query, {"article_id": article_id})

        logger.debug(
            "Updated feedback count",
            article_id=str(article_id),
            helpful=helpful,
        )

    async def get_tutorials(
        self,
        difficulty: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Tutorial], int]:
        """
        Get tutorials with optional difficulty filtering (Story 11.8b - Task 4).

        Parameters:
        -----------
        difficulty : str | None
            Filter by difficulty (BEGINNER, INTERMEDIATE, ADVANCED, None for all)
            Default: None (all difficulties)
        limit : int
            Maximum number of tutorials to return (default: 50, max: 100)
        offset : int
            Number of tutorials to skip for pagination (default: 0)

        Returns:
        --------
        tuple[list[Tutorial], int]
            Tuple of (tutorials list, total count)

        Example:
        --------
        >>> tutorials, total = await repo.get_tutorials(difficulty="BEGINNER", limit=10)
        """
        # Build base query
        query = select(TutorialORM)

        # Apply difficulty filter if specified
        if difficulty:
            query = query.where(TutorialORM.difficulty == difficulty)

        # Order by difficulty ASC, then estimated time ASC
        query = query.order_by(
            TutorialORM.difficulty.asc(), TutorialORM.estimated_time_minutes.asc()
        )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total_count = count_result.scalar() or 0

        # Apply pagination
        query = query.limit(min(limit, 100)).offset(offset)

        # Execute query
        result = await self.session.execute(query)
        rows = result.scalars().all()

        tutorials = [self._orm_to_tutorial(row) for row in rows]

        logger.debug(
            "Retrieved tutorials",
            difficulty=difficulty,
            count=len(tutorials),
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

        return tutorials, total_count

    async def get_tutorial_by_slug(self, slug: str) -> Tutorial:
        """
        Get tutorial by slug (Story 11.8b - Task 4).

        Parameters:
        -----------
        slug : str
            Tutorial slug

        Returns:
        --------
        Tutorial
            Tutorial model

        Raises:
        -------
        TutorialNotFoundError
            If tutorial doesn't exist

        Example:
        --------
        >>> tutorial = await repo.get_tutorial_by_slug("identifying-springs")
        """
        query = select(TutorialORM).where(TutorialORM.slug == slug)

        result = await self.session.execute(query)
        row = result.scalars().first()

        if not row:
            logger.warning("Tutorial not found", slug=slug)
            raise TutorialNotFoundError(f"Tutorial not found: {slug}")

        tutorial = self._orm_to_tutorial(row)

        logger.debug("Retrieved tutorial by slug", slug=slug, title=tutorial.title)

        return tutorial

    async def increment_completion_count(self, tutorial_id: UUID) -> None:
        """
        Increment tutorial completion count (Story 11.8b - Task 4).

        Parameters:
        -----------
        tutorial_id : UUID
            Tutorial UUID

        Example:
        --------
        >>> await repo.increment_completion_count(tutorial_id)
        """
        query = (
            update(TutorialORM)
            .where(TutorialORM.id == tutorial_id)
            .values(completion_count=TutorialORM.completion_count + 1)
        )

        await self.session.execute(query)

        logger.debug("Incremented tutorial completion count", tutorial_id=str(tutorial_id))

    async def save_tutorial_progress(
        self,
        user_id: UUID,
        tutorial_id: UUID,
        current_step: int,
        completed: bool,
    ) -> None:
        """
        Save user tutorial progress (Story 11.8b - Task 4 - OPTIONAL).

        Note: This method is implemented but not used in MVP (Story 11.8b uses localStorage).
        It's available for future enhancement when user authentication is implemented.

        Parameters:
        -----------
        user_id : UUID
            User UUID
        tutorial_id : UUID
            Tutorial UUID
        current_step : int
            Current step number (1-indexed)
        completed : bool
            Whether tutorial is completed

        Example:
        --------
        >>> await repo.save_tutorial_progress(user_id, tutorial_id, 5, False)
        """
        from datetime import UTC, datetime

        # Upsert tutorial progress
        query = text(
            """
            INSERT INTO tutorial_progress (user_id, tutorial_id, current_step, completed, last_accessed)
            VALUES (:user_id, :tutorial_id, :current_step, :completed, :last_accessed)
            ON CONFLICT (user_id, tutorial_id)
            DO UPDATE SET
                current_step = EXCLUDED.current_step,
                completed = EXCLUDED.completed,
                last_accessed = EXCLUDED.last_accessed
            """
        )

        await self.session.execute(
            query,
            {
                "user_id": user_id,
                "tutorial_id": tutorial_id,
                "current_step": current_step,
                "completed": completed,
                "last_accessed": datetime.now(UTC),
            },
        )

        logger.debug(
            "Saved tutorial progress",
            user_id=str(user_id),
            tutorial_id=str(tutorial_id),
            current_step=current_step,
            completed=completed,
        )

    async def get_tutorial_progress(
        self, user_id: UUID, tutorial_id: UUID
    ) -> dict[str, Any] | None:
        """
        Get user tutorial progress (Story 11.8b - Task 4 - OPTIONAL).

        Note: This method is implemented but not used in MVP (Story 11.8b uses localStorage).
        It's available for future enhancement when user authentication is implemented.

        Parameters:
        -----------
        user_id : UUID
            User UUID
        tutorial_id : UUID
            Tutorial UUID

        Returns:
        --------
        dict | None
            Progress data or None if not found

        Example:
        --------
        >>> progress = await repo.get_tutorial_progress(user_id, tutorial_id)
        >>> if progress:
        ...     print(f"Current step: {progress['current_step']}")
        """
        from src.orm.models import TutorialProgressORM

        query = select(TutorialProgressORM).where(
            TutorialProgressORM.user_id == user_id,
            TutorialProgressORM.tutorial_id == tutorial_id,
        )

        result = await self.session.execute(query)
        row = result.scalars().first()

        if not row:
            return None

        return {
            "current_step": row.current_step,
            "completed": row.completed,
            "last_accessed": row.last_accessed,
        }

    def _row_to_article(self, row: Any) -> HelpArticle:
        """Convert database row to HelpArticle model."""
        return HelpArticle(
            id=row.id,
            slug=row.slug,
            title=row.title,
            content_markdown=row.content_markdown,
            content_html=row.content_html,
            category=row.category,
            tags=row.tags or [],
            keywords=row.keywords or "",
            last_updated=row.last_updated,
            view_count=row.view_count,
            helpful_count=row.helpful_count,
            not_helpful_count=row.not_helpful_count,
        )

    def _orm_to_article(self, orm_obj: HelpArticleORM) -> HelpArticle:
        """Convert ORM object to HelpArticle model (alias for _row_to_article)."""
        return self._row_to_article(orm_obj)

    def _row_to_glossary_term(self, row: Any) -> GlossaryTerm:
        """Convert database row to GlossaryTerm model."""
        return GlossaryTerm(
            id=row.id,
            term=row.term,
            slug=row.slug,
            short_definition=row.short_definition,
            full_description="",  # Not stored separately
            full_description_html=row.full_description_html,
            wyckoff_phase=row.wyckoff_phase,
            related_terms=row.related_terms or [],
            tags=row.tags or [],
            last_updated=row.last_updated,
        )

    def _orm_to_glossary_term(self, orm_obj: GlossaryTermORM) -> GlossaryTerm:
        """Convert ORM object to GlossaryTerm model (alias for _row_to_glossary_term)."""
        return self._row_to_glossary_term(orm_obj)

    def _row_to_tutorial(self, row: Any) -> Tutorial:
        """Convert database row to Tutorial model (Story 11.8b)."""
        from src.models.help import TutorialStep

        # Convert steps JSON to TutorialStep objects
        steps = [TutorialStep(**step_data) for step_data in row.steps]

        return Tutorial(
            id=row.id,
            slug=row.slug,
            title=row.title,
            description=row.description,
            difficulty=row.difficulty,
            estimated_time_minutes=row.estimated_time_minutes,
            steps=steps,
            tags=row.tags or [],
            last_updated=row.last_updated,
            completion_count=row.completion_count,
        )

    def _orm_to_tutorial(self, orm_obj: TutorialORM) -> Tutorial:
        """Convert ORM object to Tutorial model (Story 11.8b)."""
        return self._row_to_tutorial(orm_obj)
