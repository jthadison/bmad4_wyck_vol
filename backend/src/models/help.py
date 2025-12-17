"""
Help System Models (Story 11.8a)

Purpose:
--------
Pydantic models for the help documentation system, including articles,
glossary terms, keyboard shortcuts, and user feedback.

Data Models:
------------
- HelpArticle: Help article with Markdown content
- GlossaryTerm: Wyckoff terminology with phase association
- KeyboardShortcut: Application keyboard shortcuts
- HelpFeedback: User feedback on help articles
- Response models: HelpSearchResult, HelpArticleListResponse, etc.

Integration:
------------
- Story 11.8a: Core Help Infrastructure
- GET /api/v1/help/articles, /help/search, /help/glossary endpoints
- POST /api/v1/help/feedback endpoint

Author: Story 11.8a (Task 1)
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class HelpArticle(BaseModel):
    """
    Help article with Markdown content and metadata.

    Fields:
    -------
    - id: Unique article identifier
    - slug: URL-friendly identifier (unique)
    - title: Article title
    - content_markdown: Original Markdown content
    - content_html: Rendered HTML content (sanitized)
    - category: Article category (GLOSSARY, FAQ, TUTORIAL, REFERENCE)
    - tags: Searchable tags
    - keywords: Additional search keywords
    - last_updated: Last modification timestamp
    - view_count: Number of times article viewed
    - helpful_count: Number of "helpful" votes
    - not_helpful_count: Number of "not helpful" votes

    Example:
    --------
    >>> article = HelpArticle(
    ...     id=uuid4(),
    ...     slug="spring-pattern",
    ...     title="Spring Pattern",
    ...     content_markdown="# Spring\\n\\nA spring is...",
    ...     content_html="<h1>Spring</h1><p>A spring is...</p>",
    ...     category="GLOSSARY",
    ...     tags=["pattern", "wyckoff", "phase-c"],
    ...     keywords="spring shakeout accumulation",
    ...     last_updated=datetime.now(UTC),
    ...     view_count=0,
    ...     helpful_count=0,
    ...     not_helpful_count=0
    ... )
    """

    id: UUID = Field(default_factory=uuid4, description="Unique article identifier")
    slug: str = Field(..., min_length=1, max_length=200, description="URL-friendly identifier")
    title: str = Field(..., min_length=1, max_length=300, description="Article title")
    content_markdown: str = Field(..., description="Original Markdown content")
    content_html: str = Field(..., description="Rendered HTML content (sanitized)")
    category: Literal["GLOSSARY", "FAQ", "TUTORIAL", "REFERENCE"] = Field(
        ..., description="Article category"
    )
    tags: list[str] = Field(default_factory=list, description="Searchable tags")
    keywords: str = Field(default="", description="Additional search keywords")
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Last modification timestamp"
    )
    view_count: int = Field(default=0, ge=0, description="Number of views")
    helpful_count: int = Field(default=0, ge=0, description="Number of helpful votes")
    not_helpful_count: int = Field(default=0, ge=0, description="Number of not helpful votes")

    @field_validator("last_updated", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str) -> datetime:
        """Enforce UTC timezone on timestamps."""
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "slug": "spring-pattern",
                    "title": "Spring Pattern",
                    "content_markdown": "# Spring\n\nA spring is a price move...",
                    "content_html": "<h1>Spring</h1><p>A spring is...</p>",
                    "category": "GLOSSARY",
                    "tags": ["pattern", "wyckoff", "phase-c"],
                    "keywords": "spring shakeout accumulation test",
                    "last_updated": "2024-03-15T14:30:00Z",
                    "view_count": 42,
                    "helpful_count": 15,
                    "not_helpful_count": 2,
                }
            ]
        },
        "json_encoders": {datetime: lambda v: v.isoformat()},
    }


class GlossaryTerm(BaseModel):
    """
    Wyckoff terminology with phase association.

    Fields:
    -------
    - id: Unique term identifier
    - term: Term name (e.g., "Spring")
    - slug: URL-friendly identifier (unique)
    - short_definition: Brief definition (<=500 chars)
    - full_description: Complete Markdown description
    - full_description_html: Rendered HTML description
    - wyckoff_phase: Associated Wyckoff phase (A/B/C/D/E, optional)
    - related_terms: List of related term slugs
    - tags: Searchable tags
    - last_updated: Last modification timestamp

    Example:
    --------
    >>> term = GlossaryTerm(
    ...     id=uuid4(),
    ...     term="Spring",
    ...     slug="spring",
    ...     short_definition="A price move below support that reverses quickly",
    ...     full_description="# Spring\\n\\nA spring is...",
    ...     full_description_html="<h1>Spring</h1><p>A spring is...</p>",
    ...     wyckoff_phase="C",
    ...     related_terms=["creek", "ice", "trading-range"],
    ...     tags=["pattern", "phase-c"],
    ...     last_updated=datetime.now(UTC)
    ... )
    """

    id: UUID = Field(default_factory=uuid4, description="Unique term identifier")
    term: str = Field(..., min_length=1, max_length=100, description="Term name")
    slug: str = Field(..., min_length=1, max_length=200, description="URL-friendly identifier")
    short_definition: str = Field(..., min_length=1, max_length=500, description="Brief definition")
    full_description: str = Field(..., description="Complete Markdown description")
    full_description_html: str = Field(..., description="Rendered HTML description")
    wyckoff_phase: Literal["A", "B", "C", "D", "E"] | None = Field(
        None, description="Associated Wyckoff phase"
    )
    related_terms: list[str] = Field(default_factory=list, description="Related term slugs")
    tags: list[str] = Field(default_factory=list, description="Searchable tags")
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Last modification timestamp"
    )

    @field_validator("last_updated", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str) -> datetime:
        """Enforce UTC timezone on timestamps."""
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "660e8400-e29b-41d4-a716-446655440001",
                    "term": "Spring",
                    "slug": "spring",
                    "short_definition": "A price move below support that reverses quickly",
                    "full_description": "# Spring\n\nA spring is a downside...",
                    "full_description_html": "<h1>Spring</h1><p>A spring is...</p>",
                    "wyckoff_phase": "C",
                    "related_terms": ["creek", "ice", "trading-range"],
                    "tags": ["pattern", "phase-c", "accumulation"],
                    "last_updated": "2024-03-15T14:30:00Z",
                }
            ]
        },
        "json_encoders": {datetime: lambda v: v.isoformat()},
    }


class KeyboardShortcut(BaseModel):
    """
    Application keyboard shortcut.

    Fields:
    -------
    - id: Unique shortcut identifier
    - key_combination: Key combo (e.g., "Ctrl+K", "?")
    - action_description: What the shortcut does
    - context: Where the shortcut works (GLOBAL, CHART, SIGNALS, SETTINGS)

    Example:
    --------
    >>> shortcut = KeyboardShortcut(
    ...     id=uuid4(),
    ...     key_combination="?",
    ...     action_description="Open help center",
    ...     context="GLOBAL"
    ... )
    """

    id: UUID = Field(default_factory=uuid4, description="Unique shortcut identifier")
    key_combination: str = Field(..., min_length=1, max_length=50, description="Key combination")
    action_description: str = Field(
        ..., min_length=1, max_length=200, description="Action description"
    )
    context: Literal["GLOBAL", "CHART", "SIGNALS", "SETTINGS"] = Field(
        ..., description="Context where shortcut works"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "770e8400-e29b-41d4-a716-446655440002",
                    "key_combination": "?",
                    "action_description": "Open help center",
                    "context": "GLOBAL",
                }
            ]
        }
    }


class HelpFeedback(BaseModel):
    """
    User feedback on help article.

    Fields:
    -------
    - id: Unique feedback identifier
    - article_id: UUID of the help article
    - helpful: Whether article was helpful (true/false)
    - user_comment: Optional comment text
    - created_at: Feedback submission timestamp

    Example:
    --------
    >>> feedback = HelpFeedback(
    ...     id=uuid4(),
    ...     article_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
    ...     helpful=True,
    ...     user_comment="Very clear explanation!",
    ...     created_at=datetime.now(UTC)
    ... )
    """

    id: UUID = Field(default_factory=uuid4, description="Unique feedback identifier")
    article_id: UUID = Field(..., description="UUID of the help article")
    helpful: bool = Field(..., description="Whether article was helpful")
    user_comment: str | None = Field(None, max_length=1000, description="Optional comment text")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Feedback submission timestamp"
    )

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str) -> datetime:
        """Enforce UTC timezone on timestamps."""
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "880e8400-e29b-41d4-a716-446655440003",
                    "article_id": "550e8400-e29b-41d4-a716-446655440000",
                    "helpful": True,
                    "user_comment": "Very clear explanation of the Spring pattern!",
                    "created_at": "2024-03-15T14:30:00Z",
                }
            ]
        },
        "json_encoders": {datetime: lambda v: v.isoformat()},
    }


# Response Models


class HelpSearchResult(BaseModel):
    """
    Search result item.

    Fields:
    -------
    - id: Article ID
    - slug: Article slug
    - title: Article title
    - category: Article category
    - snippet: Search result snippet with highlighting
    - rank: Search relevance rank
    """

    id: UUID = Field(..., description="Article ID")
    slug: str = Field(..., description="Article slug")
    title: str = Field(..., description="Article title")
    category: Literal["GLOSSARY", "FAQ", "TUTORIAL", "REFERENCE"] = Field(
        ..., description="Article category"
    )
    snippet: str = Field(..., description="Search result snippet")
    rank: float = Field(..., description="Search relevance rank")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "slug": "spring-pattern",
                    "title": "Spring Pattern",
                    "category": "GLOSSARY",
                    "snippet": "A <mark>spring</mark> is a price move below support...",
                    "rank": 0.85,
                }
            ]
        }
    }


class HelpArticleListResponse(BaseModel):
    """
    Response for article listing.

    Fields:
    -------
    - articles: List of articles
    - total_count: Total number of articles (before pagination)
    """

    articles: list[HelpArticle] = Field(..., description="List of articles")
    total_count: int = Field(..., ge=0, description="Total count")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "articles": [],
                    "total_count": 15,
                }
            ]
        }
    }


class GlossaryResponse(BaseModel):
    """
    Response for glossary listing.

    Fields:
    -------
    - terms: List of glossary terms
    - total_count: Total number of terms (before filtering)
    """

    terms: list[GlossaryTerm] = Field(..., description="List of glossary terms")
    total_count: int = Field(..., ge=0, description="Total count")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "terms": [],
                    "total_count": 25,
                }
            ]
        }
    }


class SearchResponse(BaseModel):
    """
    Response for search query.

    Fields:
    -------
    - results: List of search results
    - query: Original search query
    - total_count: Total number of results
    """

    results: list[HelpSearchResult] = Field(..., description="Search results")
    query: str = Field(..., description="Search query")
    total_count: int = Field(..., ge=0, description="Total result count")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "results": [],
                    "query": "spring pattern",
                    "total_count": 5,
                }
            ]
        }
    }


class HelpFeedbackSubmission(BaseModel):
    """
    Request body for submitting help feedback.

    Fields:
    -------
    - article_id: UUID of the help article
    - helpful: Whether article was helpful
    - user_comment: Optional comment
    """

    article_id: UUID = Field(..., description="UUID of the help article")
    helpful: bool = Field(..., description="Whether article was helpful")
    user_comment: str | None = Field(None, max_length=1000, description="Optional comment text")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "article_id": "550e8400-e29b-41d4-a716-446655440000",
                    "helpful": True,
                    "user_comment": "Very helpful!",
                }
            ]
        }
    }


class HelpFeedbackResponse(BaseModel):
    """
    Response after feedback submission.

    Fields:
    -------
    - feedback_id: Unique identifier for the feedback
    - message: Confirmation message
    """

    feedback_id: UUID = Field(..., description="Feedback identifier")
    message: str = Field(..., description="Confirmation message")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "feedback_id": "880e8400-e29b-41d4-a716-446655440003",
                    "message": "Thank you for your feedback!",
                }
            ]
        }
    }
