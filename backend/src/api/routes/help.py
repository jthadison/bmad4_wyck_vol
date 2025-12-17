"""
Help API Routes (Story 11.8a - Task 7)

Purpose:
--------
FastAPI routes for help system including articles, glossary, search,
and user feedback endpoints.

Endpoints:
----------
- GET /api/v1/help/articles - List help articles with filtering
- GET /api/v1/help/articles/{slug} - Get article by slug
- GET /api/v1/help/search - Full-text search
- GET /api/v1/help/glossary - List glossary terms
- POST /api/v1/help/feedback - Submit article feedback

Integration:
------------
- Uses HelpRepository for database operations
- Implements PostgreSQL full-text search
- Automatically increments view counts

Author: Story 11.8a (Task 7)
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.help import (
    GlossaryResponse,
    HelpArticleListResponse,
    HelpFeedback,
    HelpFeedbackResponse,
    HelpFeedbackSubmission,
    SearchResponse,
)
from src.repositories.help_repository import (
    ArticleNotFoundError,
    HelpRepository,
    SearchQueryError,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/help", tags=["help"])


@router.get(
    "/articles",
    response_model=HelpArticleListResponse,
    summary="Get help articles",
    description="Retrieve help articles with optional category filtering and pagination",
)
async def get_articles(
    category: str = Query(
        "ALL",
        description="Filter by category (GLOSSARY, FAQ, TUTORIAL, REFERENCE, ALL)",
        regex="^(GLOSSARY|FAQ|TUTORIAL|REFERENCE|ALL)$",
    ),
    limit: int = Query(
        50,
        description="Maximum number of articles to return",
        ge=1,
        le=100,
    ),
    offset: int = Query(
        0,
        description="Number of articles to skip for pagination",
        ge=0,
    ),
    session: AsyncSession = Depends(get_db),
) -> HelpArticleListResponse:
    """
    Get help articles with optional category filtering.

    Parameters:
    -----------
    - category: Filter by category (GLOSSARY, FAQ, TUTORIAL, REFERENCE, ALL)
    - limit: Maximum articles to return (1-100, default: 50)
    - offset: Skip N articles for pagination (default: 0)

    Returns:
    --------
    HelpArticleListResponse with articles list and total count

    Example:
    --------
    GET /api/v1/help/articles?category=FAQ&limit=20&offset=0
    """
    try:
        repo = HelpRepository(session)
        articles, total_count = await repo.get_articles(
            category=category,
            limit=limit,
            offset=offset,
        )

        logger.info(
            "GET /api/v1/help/articles",
            category=category,
            limit=limit,
            offset=offset,
            results=len(articles),
            total=total_count,
        )

        return HelpArticleListResponse(
            articles=articles,
            total_count=total_count,
        )

    except Exception as e:
        logger.error(
            "Failed to get articles",
            category=category,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve articles: {str(e)}",
        ) from e


@router.get(
    "/articles/{slug}",
    summary="Get article by slug",
    description="Retrieve a specific help article by its slug. Increments view count.",
)
async def get_article(
    slug: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Get help article by slug.

    Automatically increments the article's view count.

    Parameters:
    -----------
    - slug: Article slug (URL-friendly identifier)

    Returns:
    --------
    HelpArticle model

    Errors:
    -------
    - 404: Article not found

    Example:
    --------
    GET /api/v1/help/articles/spring-pattern
    """
    try:
        repo = HelpRepository(session)

        # Get article
        article = await repo.get_article_by_slug(slug)

        # Increment view count
        await repo.increment_view_count(article.id)

        logger.info(
            "GET /api/v1/help/articles/{slug}",
            slug=slug,
            article_id=str(article.id),
        )

        return article

    except ArticleNotFoundError as e:
        logger.warning("Article not found", slug=slug)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article not found: {slug}",
        ) from e

    except Exception as e:
        logger.error(
            "Failed to get article",
            slug=slug,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve article: {str(e)}",
        ) from e


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Search help articles",
    description="Full-text search across help articles with ranking and snippets",
)
async def search_articles(
    q: str = Query(
        ...,
        description="Search query",
        min_length=1,
        max_length=200,
    ),
    limit: int = Query(
        20,
        description="Maximum number of results",
        ge=1,
        le=50,
    ),
    session: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """
    Full-text search across help articles.

    Uses PostgreSQL full-text search with ranking and highlighted snippets.

    Parameters:
    -----------
    - q: Search query string (required)
    - limit: Maximum results to return (1-50, default: 20)

    Returns:
    --------
    SearchResponse with ranked results and snippets

    Errors:
    -------
    - 400: Invalid search query

    Example:
    --------
    GET /api/v1/help/search?q=spring%20pattern&limit=10
    """
    try:
        repo = HelpRepository(session)

        results, total_count = await repo.search_articles(
            query=q,
            limit=limit,
        )

        logger.info(
            "GET /api/v1/help/search",
            query=q,
            limit=limit,
            results=len(results),
            total=total_count,
        )

        return SearchResponse(
            results=results,
            query=q,
            total_count=total_count,
        )

    except SearchQueryError as e:
        logger.warning("Invalid search query", query=q, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid search query: {str(e)}",
        ) from e

    except Exception as e:
        logger.error(
            "Search failed",
            query=q,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        ) from e


@router.get(
    "/glossary",
    response_model=GlossaryResponse,
    summary="Get glossary terms",
    description="Retrieve glossary terms with optional Wyckoff phase filtering",
)
async def get_glossary(
    wyckoff_phase: str | None = Query(
        None,
        description="Filter by Wyckoff phase (A, B, C, D, E)",
        regex="^[ABCDE]$",
    ),
    session: AsyncSession = Depends(get_db),
) -> GlossaryResponse:
    """
    Get glossary terms with optional phase filtering.

    Parameters:
    -----------
    - wyckoff_phase: Optional filter by Wyckoff phase (A/B/C/D/E)

    Returns:
    --------
    GlossaryResponse with terms list and total count

    Example:
    --------
    GET /api/v1/help/glossary?wyckoff_phase=C
    """
    try:
        repo = HelpRepository(session)

        terms, total_count = await repo.get_glossary_terms(
            wyckoff_phase=wyckoff_phase,
        )

        logger.info(
            "GET /api/v1/help/glossary",
            wyckoff_phase=wyckoff_phase,
            results=len(terms),
            total=total_count,
        )

        return GlossaryResponse(
            terms=terms,
            total_count=total_count,
        )

    except Exception as e:
        logger.error(
            "Failed to get glossary",
            wyckoff_phase=wyckoff_phase,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve glossary: {str(e)}",
        ) from e


@router.post(
    "/feedback",
    response_model=HelpFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit article feedback",
    description="Submit user feedback on help article (helpful/not helpful)",
)
async def submit_feedback(
    submission: HelpFeedbackSubmission,
    session: AsyncSession = Depends(get_db),
) -> HelpFeedbackResponse:
    """
    Submit user feedback on help article.

    Updates the article's helpful/not_helpful count.

    Parameters:
    -----------
    - submission: HelpFeedbackSubmission with article_id, helpful, optional comment

    Returns:
    --------
    HelpFeedbackResponse with feedback_id and confirmation message

    Errors:
    -------
    - 400: Invalid request body
    - 404: Article not found

    Example:
    --------
    POST /api/v1/help/feedback
    {
        "article_id": "550e8400-e29b-41d4-a716-446655440000",
        "helpful": true,
        "user_comment": "Very clear explanation!"
    }
    """
    try:
        repo = HelpRepository(session)

        # Verify article exists
        try:
            await session.execute(
                text("SELECT id FROM help_articles WHERE id = :article_id"),
                {"article_id": submission.article_id},
            )
        except Exception as e:
            raise ArticleNotFoundError(f"Article not found: {submission.article_id}") from e

        # Create feedback record
        feedback = HelpFeedback(
            article_id=submission.article_id,
            helpful=submission.helpful,
            user_comment=submission.user_comment,
        )

        feedback_id = await repo.create_feedback(feedback)

        logger.info(
            "POST /api/v1/help/feedback",
            feedback_id=str(feedback_id),
            article_id=str(submission.article_id),
            helpful=submission.helpful,
        )

        return HelpFeedbackResponse(
            feedback_id=feedback_id,
            message="Thank you for your feedback!",
        )

    except ArticleNotFoundError as e:
        logger.warning(
            "Article not found for feedback",
            article_id=str(submission.article_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article not found: {submission.article_id}",
        ) from e

    except Exception as e:
        logger.error(
            "Failed to submit feedback",
            article_id=str(submission.article_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {str(e)}",
        ) from e
