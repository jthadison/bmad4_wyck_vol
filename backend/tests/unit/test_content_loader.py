"""
Unit tests for HelpContentLoader (Story 11.8a - Task 4)

Tests:
------
- Markdown file loading with frontmatter parsing
- Content caching with mtime checking
- Error handling for missing/invalid files
- Glossary term and article parsing
"""


import pytest

from src.help.content_loader import ContentLoadError, HelpContentLoader


class TestHelpContentLoader:
    """Test suite for HelpContentLoader."""

    def test_init_default_directory(self):
        """Test initialization with default content directory."""
        loader = HelpContentLoader()
        assert loader.content_dir is not None
        assert loader.cache == {}

    def test_init_custom_directory(self, tmp_path):
        """Test initialization with custom directory."""
        custom_dir = tmp_path / "custom_content"
        custom_dir.mkdir()

        loader = HelpContentLoader(custom_dir)
        assert loader.content_dir == custom_dir
        assert loader.cache == {}

    def test_load_single_glossary_file(self, tmp_path):
        """Test loading a single glossary term file."""
        # Create test file
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        test_file = content_dir / "spring.md"
        test_file.write_text(
            """---
title: "Spring Pattern"
category: "GLOSSARY"
short_definition: "A price move below support"
wyckoff_phase: "C"
tags: ["pattern", "phase-c"]
keywords: "spring shakeout"
---

# Spring Pattern

A **Spring** is a downside price move that penetrates below support.
"""
        )

        # Load file
        loader = HelpContentLoader(content_dir)
        parsed = loader._load_single_file(test_file)

        # Verify parsed content
        assert parsed is not None
        assert parsed["slug"] == "spring"
        assert parsed["title"] == "Spring Pattern"
        assert parsed["category"] == "GLOSSARY"
        assert parsed["short_definition"] == "A price move below support"
        assert parsed["wyckoff_phase"] == "C"
        assert "spring shakeout" in parsed["keywords"]
        assert "pattern" in parsed["tags"]
        assert "Spring" in parsed["content_markdown"]

    def test_load_single_faq_file(self, tmp_path):
        """Test loading a FAQ article."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        test_file = content_dir / "what-is-wyckoff.md"
        test_file.write_text(
            """---
title: "What is Wyckoff Method?"
category: "FAQ"
tags: ["basics"]
keywords: "wyckoff method"
---

# What is Wyckoff Method?

The Wyckoff Method is a technical analysis approach...
"""
        )

        loader = HelpContentLoader(content_dir)
        parsed = loader._load_single_file(test_file)

        assert parsed is not None
        assert parsed["slug"] == "what-is-wyckoff"
        assert parsed["category"] == "FAQ"
        assert "wyckoff method" in parsed["keywords"]

    def test_load_file_missing_required_fields(self, tmp_path):
        """Test loading file with missing required fields."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Missing 'category' field
        test_file = content_dir / "invalid.md"
        test_file.write_text(
            """---
title: "Test"
---

Content here
"""
        )

        loader = HelpContentLoader(content_dir)
        parsed = loader._load_single_file(test_file)

        # Should return None for invalid files
        assert parsed is None

    def test_load_all_markdown_files(self, tmp_path):
        """Test loading all markdown files from directory."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create multiple test files
        (content_dir / "spring.md").write_text(
            """---
title: "Spring"
category: "GLOSSARY"
---
Content
"""
        )

        (content_dir / "faq.md").write_text(
            """---
title: "FAQ"
category: "FAQ"
---
Content
"""
        )

        # Create README (should be skipped)
        (content_dir / "README.md").write_text("README content")

        loader = HelpContentLoader(content_dir)
        loaded = loader.load_markdown_files()

        # Should load 2 files (skip README)
        assert len(loaded) == 2
        slugs = [f["slug"] for f in loaded]
        assert "spring" in slugs
        assert "faq" in slugs

    def test_content_caching(self, tmp_path):
        """Test content caching with mtime checking."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        test_file = content_dir / "test.md"
        test_file.write_text(
            """---
title: "Test"
category: "FAQ"
---
Original content
"""
        )

        loader = HelpContentLoader(content_dir)

        # First load
        parsed1 = loader._load_single_file(test_file)
        assert "Original content" in parsed1["content_markdown"]

        # Cache stats
        stats = loader.get_cache_stats()
        assert stats["cached_files"] == 1

        # Second load (should use cache)
        parsed2 = loader._load_single_file(test_file)
        assert parsed2 == parsed1

        # Clear cache
        loader.clear_cache()
        stats = loader.get_cache_stats()
        assert stats["cached_files"] == 0

    def test_parse_glossary_term(self, tmp_path):
        """Test parsing glossary term to GlossaryTerm model."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        test_file = content_dir / "creek.md"
        test_file.write_text(
            """---
title: "Creek Level"
category: "GLOSSARY"
short_definition: "Support boundary"
wyckoff_phase: "B"
tags: ["level"]
related_terms: ["ice", "jump"]
---

# Creek Level

The Creek level marks the support boundary.
"""
        )

        loader = HelpContentLoader(content_dir)
        term = loader.parse_glossary_term(test_file)

        assert term.term == "Creek Level"
        assert term.slug == "creek"
        assert term.short_definition == "Support boundary"
        assert term.wyckoff_phase == "B"
        assert "level" in term.tags
        assert "ice" in term.related_terms

    def test_parse_article(self, tmp_path):
        """Test parsing article to HelpArticle model."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        test_file = content_dir / "tutorial.md"
        test_file.write_text(
            """---
title: "Getting Started"
category: "TUTORIAL"
tags: ["beginner"]
keywords: "tutorial basics"
---

# Getting Started

This tutorial explains...
"""
        )

        loader = HelpContentLoader(content_dir)
        article = loader.parse_article(test_file)

        assert article.title == "Getting Started"
        assert article.slug == "tutorial"
        assert article.category == "TUTORIAL"
        assert "beginner" in article.tags
        assert "tutorial basics" in article.keywords

    def test_load_nonexistent_directory(self):
        """Test loading from non-existent directory."""
        loader = HelpContentLoader("/nonexistent/path")

        with pytest.raises(ContentLoadError, match="Content directory not found"):
            loader.load_markdown_files()

    def test_invalid_markdown_parsing(self, tmp_path):
        """Test handling of invalid Markdown files."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create file with invalid YAML
        test_file = content_dir / "invalid.md"
        test_file.write_text(
            """---
title: "Test
invalid yaml here
---

Content
"""
        )

        loader = HelpContentLoader(content_dir)

        # Should handle error gracefully
        loaded = loader.load_markdown_files()
        # Invalid file should be skipped
        assert len(loaded) == 0
