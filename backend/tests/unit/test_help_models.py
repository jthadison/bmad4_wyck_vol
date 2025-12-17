"""
Unit tests for Help Models (Story 11.8a - Task 1.8)

Tests Pydantic validation for HelpArticle, GlossaryTerm, KeyboardShortcut, and HelpFeedback models.
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.models.help import (
    GlossaryResponse,
    GlossaryTerm,
    HelpArticle,
    HelpArticleListResponse,
    HelpFeedback,
    HelpFeedbackResponse,
    HelpFeedbackSubmission,
    HelpSearchResult,
    KeyboardShortcut,
    SearchResponse,
)


class TestHelpArticle:
    """Tests for HelpArticle model."""

    def test_help_article_valid(self):
        """Test valid HelpArticle creation."""
        article = HelpArticle(
            slug="spring-pattern",
            title="Spring Pattern",
            content_markdown="# Spring\n\nA spring is...",
            content_html="<h1>Spring</h1><p>A spring is...</p>",
            category="GLOSSARY",
            tags=["pattern", "wyckoff"],
            keywords="spring shakeout",
        )

        assert article.slug == "spring-pattern"
        assert article.title == "Spring Pattern"
        assert article.category == "GLOSSARY"
        assert len(article.tags) == 2
        assert article.view_count == 0
        assert article.helpful_count == 0

    def test_help_article_auto_fields(self):
        """Test auto-generated fields (id, last_updated)."""
        article = HelpArticle(
            slug="test",
            title="Test",
            content_markdown="Test",
            content_html="<p>Test</p>",
            category="FAQ",
        )

        assert isinstance(article.id, UUID)
        assert isinstance(article.last_updated, datetime)
        assert article.last_updated.tzinfo is not None  # UTC timezone

    def test_help_article_invalid_category(self):
        """Test invalid category raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            HelpArticle(
                slug="test",
                title="Test",
                content_markdown="Test",
                content_html="<p>Test</p>",
                category="INVALID",  # Invalid category
            )

        errors = exc_info.value.errors()
        assert any("category" in str(error) for error in errors)

    def test_help_article_negative_counts(self):
        """Test negative counts raise ValidationError."""
        with pytest.raises(ValidationError):
            HelpArticle(
                slug="test",
                title="Test",
                content_markdown="Test",
                content_html="<p>Test</p>",
                category="FAQ",
                view_count=-1,  # Invalid
            )

    def test_help_article_utc_timestamp(self):
        """Test UTC timestamp normalization."""
        # Naive datetime should be converted to UTC
        naive_dt = datetime(2024, 3, 15, 14, 30, 0)
        article = HelpArticle(
            slug="test",
            title="Test",
            content_markdown="Test",
            content_html="<p>Test</p>",
            category="FAQ",
            last_updated=naive_dt,
        )

        assert article.last_updated.tzinfo is not None
        assert article.last_updated.tzinfo.tzname(None) == "UTC"

    def test_help_article_string_timestamp(self):
        """Test ISO string timestamp parsing."""
        article = HelpArticle(
            slug="test",
            title="Test",
            content_markdown="Test",
            content_html="<p>Test</p>",
            category="FAQ",
            last_updated="2024-03-15T14:30:00Z",
        )

        assert isinstance(article.last_updated, datetime)
        assert article.last_updated.year == 2024


class TestGlossaryTerm:
    """Tests for GlossaryTerm model."""

    def test_glossary_term_valid(self):
        """Test valid GlossaryTerm creation."""
        term = GlossaryTerm(
            term="Spring",
            slug="spring",
            short_definition="A price move below support that reverses",
            full_description="# Spring\n\nDetailed description...",
            full_description_html="<h1>Spring</h1><p>Detailed...</p>",
            wyckoff_phase="C",
            related_terms=["creek", "ice"],
            tags=["pattern", "phase-c"],
        )

        assert term.term == "Spring"
        assert term.slug == "spring"
        assert term.wyckoff_phase == "C"
        assert len(term.related_terms) == 2
        assert len(term.tags) == 2

    def test_glossary_term_no_phase(self):
        """Test glossary term without Wyckoff phase."""
        term = GlossaryTerm(
            term="Trading Range",
            slug="trading-range",
            short_definition="Horizontal consolidation",
            full_description="# Trading Range\n\n...",
            full_description_html="<h1>Trading Range</h1>...",
            wyckoff_phase=None,  # No phase association
        )

        assert term.wyckoff_phase is None

    def test_glossary_term_invalid_phase(self):
        """Test invalid Wyckoff phase raises ValidationError."""
        with pytest.raises(ValidationError):
            GlossaryTerm(
                term="Test",
                slug="test",
                short_definition="Test",
                full_description="Test",
                full_description_html="<p>Test</p>",
                wyckoff_phase="F",  # Invalid phase
            )

    def test_glossary_term_definition_too_long(self):
        """Test short_definition exceeding 500 chars raises error."""
        with pytest.raises(ValidationError):
            GlossaryTerm(
                term="Test",
                slug="test",
                short_definition="x" * 501,  # Too long
                full_description="Test",
                full_description_html="<p>Test</p>",
            )


class TestKeyboardShortcut:
    """Tests for KeyboardShortcut model."""

    def test_keyboard_shortcut_valid(self):
        """Test valid KeyboardShortcut creation."""
        shortcut = KeyboardShortcut(
            key_combination="?",
            action_description="Open help center",
            context="GLOBAL",
        )

        assert shortcut.key_combination == "?"
        assert shortcut.action_description == "Open help center"
        assert shortcut.context == "GLOBAL"
        assert isinstance(shortcut.id, UUID)

    def test_keyboard_shortcut_invalid_context(self):
        """Test invalid context raises ValidationError."""
        with pytest.raises(ValidationError):
            KeyboardShortcut(
                key_combination="Ctrl+K",
                action_description="Test",
                context="INVALID",  # Invalid context
            )


class TestHelpFeedback:
    """Tests for HelpFeedback model."""

    def test_help_feedback_valid(self):
        """Test valid HelpFeedback creation."""
        article_id = uuid4()
        feedback = HelpFeedback(
            article_id=article_id,
            helpful=True,
            user_comment="Very helpful!",
        )

        assert feedback.article_id == article_id
        assert feedback.helpful is True
        assert feedback.user_comment == "Very helpful!"
        assert isinstance(feedback.id, UUID)
        assert isinstance(feedback.created_at, datetime)

    def test_help_feedback_no_comment(self):
        """Test feedback without comment."""
        feedback = HelpFeedback(
            article_id=uuid4(),
            helpful=False,
            user_comment=None,
        )

        assert feedback.user_comment is None

    def test_help_feedback_comment_too_long(self):
        """Test comment exceeding 1000 chars raises error."""
        with pytest.raises(ValidationError):
            HelpFeedback(
                article_id=uuid4(),
                helpful=True,
                user_comment="x" * 1001,  # Too long
            )


class TestResponseModels:
    """Tests for response models."""

    def test_help_search_result(self):
        """Test HelpSearchResult model."""
        result = HelpSearchResult(
            id=uuid4(),
            slug="spring",
            title="Spring Pattern",
            category="GLOSSARY",
            snippet="A <mark>spring</mark> is...",
            rank=0.85,
        )

        assert result.category == "GLOSSARY"
        assert result.rank == 0.85

    def test_help_article_list_response(self):
        """Test HelpArticleListResponse model."""
        article = HelpArticle(
            slug="test",
            title="Test",
            content_markdown="Test",
            content_html="<p>Test</p>",
            category="FAQ",
        )

        response = HelpArticleListResponse(
            articles=[article],
            total_count=1,
        )

        assert len(response.articles) == 1
        assert response.total_count == 1

    def test_glossary_response(self):
        """Test GlossaryResponse model."""
        term = GlossaryTerm(
            term="Test",
            slug="test",
            short_definition="Test",
            full_description="Test",
            full_description_html="<p>Test</p>",
        )

        response = GlossaryResponse(
            terms=[term],
            total_count=1,
        )

        assert len(response.terms) == 1
        assert response.total_count == 1

    def test_search_response(self):
        """Test SearchResponse model."""
        result = HelpSearchResult(
            id=uuid4(),
            slug="test",
            title="Test",
            category="FAQ",
            snippet="Test snippet",
            rank=0.5,
        )

        response = SearchResponse(
            results=[result],
            query="spring",
            total_count=1,
        )

        assert response.query == "spring"
        assert len(response.results) == 1

    def test_help_feedback_submission(self):
        """Test HelpFeedbackSubmission model."""
        article_id = uuid4()
        submission = HelpFeedbackSubmission(
            article_id=article_id,
            helpful=True,
            user_comment="Great!",
        )

        assert submission.article_id == article_id
        assert submission.helpful is True

    def test_help_feedback_response(self):
        """Test HelpFeedbackResponse model."""
        feedback_id = uuid4()
        response = HelpFeedbackResponse(
            feedback_id=feedback_id,
            message="Thank you!",
        )

        assert response.feedback_id == feedback_id
        assert response.message == "Thank you!"
