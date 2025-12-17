"""
Help Content Loader (Story 11.8a - Task 4)

Purpose:
--------
Loads and parses Markdown help content files with YAML frontmatter.
Caches parsed content in memory and reloads only when files change.

Classes:
--------
- HelpContentLoader: Loads and caches help content from filesystem

Integration:
------------
- Used by seed_content.py to populate database
- Monitors file modification times for cache invalidation
- Supports glossary terms, FAQ, tutorials, and reference docs

Author: Story 11.8a (Task 4)
"""

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import frontmatter
import structlog

from src.models.help import GlossaryTerm, HelpArticle

logger = structlog.get_logger(__name__)


class ContentLoadError(Exception):
    """Raised when content loading fails."""

    pass


class HelpContentLoader:
    """
    Loads and caches Markdown help content from filesystem.

    This class scans the content directory for Markdown files,
    parses YAML frontmatter, and caches parsed content with mtime checking.

    Attributes:
    -----------
    content_dir : Path
        Root directory for help content
    cache : dict
        Cached content with metadata
    """

    def __init__(self, content_dir: Path | str | None = None):
        """
        Initialize content loader.

        Parameters:
        -----------
        content_dir : Path | str | None
            Directory containing help content.
            Defaults to backend/src/help/content/
        """
        if content_dir is None:
            # Default to content directory relative to this file
            content_dir = Path(__file__).parent / "content"
        elif isinstance(content_dir, str):
            content_dir = Path(content_dir)

        self.content_dir = content_dir
        self.cache: dict[str, dict[str, Any]] = {}

        logger.info(
            "HelpContentLoader initialized",
            content_dir=str(self.content_dir),
            exists=self.content_dir.exists(),
        )

        if not self.content_dir.exists():
            logger.warning("Content directory does not exist", content_dir=str(self.content_dir))

    def load_markdown_files(self) -> list[dict[str, Any]]:
        """
        Load all Markdown files from content directory.

        Returns:
        --------
        list[dict]
            List of parsed content dictionaries with metadata and content

        Raises:
        -------
        ContentLoadError
            If content directory doesn't exist or parsing fails
        """
        if not self.content_dir.exists():
            raise ContentLoadError(f"Content directory not found: {self.content_dir}")

        loaded_files: list[dict[str, Any]] = []

        # Recursively find all .md files
        for md_file in self.content_dir.rglob("*.md"):
            # Skip README files
            if md_file.name.upper() == "README.MD":
                continue

            try:
                parsed = self._load_single_file(md_file)
                if parsed:
                    loaded_files.append(parsed)
            except Exception as e:
                logger.error(
                    "Failed to load content file",
                    file_path=str(md_file),
                    error=str(e),
                    exc_info=True,
                )
                # Continue loading other files even if one fails
                continue

        logger.info(
            "Loaded markdown files",
            total_files=len(loaded_files),
            content_dir=str(self.content_dir),
        )

        return loaded_files

    def _load_single_file(self, file_path: Path) -> dict[str, Any] | None:
        """
        Load and parse a single Markdown file with caching.

        Parameters:
        -----------
        file_path : Path
            Path to Markdown file

        Returns:
        --------
        dict | None
            Parsed content with metadata, or None if cached and unchanged
        """
        # Get file modification time
        mtime = os.path.getmtime(file_path)
        file_key = str(file_path)

        # Check cache
        if file_key in self.cache:
            cached_mtime = self.cache[file_key].get("_mtime")
            if cached_mtime == mtime:
                logger.debug("Using cached content", file_path=file_key)
                return self.cache[file_key]

        # Load and parse file
        try:
            with open(file_path, encoding="utf-8") as f:
                post = frontmatter.load(f)

            # Extract metadata
            metadata = post.metadata
            content = post.content

            # Validate required fields
            if "title" not in metadata:
                logger.warning("Missing required field 'title'", file_path=str(file_path))
                return None

            if "category" not in metadata:
                logger.warning("Missing required field 'category'", file_path=str(file_path))
                return None

            # Determine slug from filename
            slug = file_path.stem  # filename without extension

            # Build parsed content
            parsed = {
                "file_path": str(file_path),
                "slug": slug,
                "title": metadata["title"],
                "category": metadata["category"],
                "content_markdown": content,
                "tags": metadata.get("tags", []),
                "keywords": metadata.get("keywords", ""),
                "_mtime": mtime,
            }

            # Add category-specific fields
            if metadata["category"] == "GLOSSARY":
                parsed["short_definition"] = metadata.get("short_definition", "")
                parsed["wyckoff_phase"] = metadata.get("wyckoff_phase")
                parsed["related_terms"] = metadata.get("related_terms", [])

            # Cache the result
            self.cache[file_key] = parsed

            logger.debug(
                "Loaded content file",
                file_path=str(file_path),
                slug=slug,
                category=metadata["category"],
            )

            return parsed

        except Exception as e:
            logger.error(
                "Failed to parse content file",
                file_path=str(file_path),
                error=str(e),
                exc_info=True,
            )
            raise ContentLoadError(f"Failed to parse {file_path}: {e}") from e

    def parse_glossary_term(self, file_path: Path) -> GlossaryTerm:
        """
        Parse a glossary term from Markdown file.

        Parameters:
        -----------
        file_path : Path
            Path to glossary term Markdown file

        Returns:
        --------
        GlossaryTerm
            Parsed glossary term model

        Raises:
        -------
        ContentLoadError
            If file doesn't exist or parsing fails
        """
        parsed = self._load_single_file(file_path)

        if not parsed:
            raise ContentLoadError(f"Failed to load glossary term: {file_path}")

        if parsed["category"] != "GLOSSARY":
            raise ContentLoadError(
                f"File is not a glossary term (category={parsed['category']}): {file_path}"
            )

        # Note: HTML rendering happens in MarkdownRenderer
        # Here we just prepare the model data
        return GlossaryTerm(
            term=parsed["title"],
            slug=parsed["slug"],
            short_definition=parsed.get("short_definition", ""),
            full_description=parsed["content_markdown"],
            full_description_html="",  # Will be set by renderer
            wyckoff_phase=parsed.get("wyckoff_phase"),
            related_terms=parsed.get("related_terms", []),
            tags=parsed.get("tags", []),
            last_updated=datetime.now(UTC),
        )

    def parse_article(self, file_path: Path) -> HelpArticle:
        """
        Parse a help article from Markdown file.

        Parameters:
        -----------
        file_path : Path
            Path to article Markdown file

        Returns:
        --------
        HelpArticle
            Parsed help article model

        Raises:
        -------
        ContentLoadError
            If file doesn't exist or parsing fails
        """
        parsed = self._load_single_file(file_path)

        if not parsed:
            raise ContentLoadError(f"Failed to load article: {file_path}")

        # Note: HTML rendering happens in MarkdownRenderer
        # Here we just prepare the model data
        return HelpArticle(
            slug=parsed["slug"],
            title=parsed["title"],
            content_markdown=parsed["content_markdown"],
            content_html="",  # Will be set by renderer
            category=parsed["category"],
            tags=parsed.get("tags", []),
            keywords=parsed.get("keywords", ""),
            last_updated=datetime.now(UTC),
        )

    def clear_cache(self) -> None:
        """Clear the content cache."""
        self.cache.clear()
        logger.info("Content cache cleared")

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
        --------
        dict
            Cache statistics including size and files
        """
        return {
            "cached_files": len(self.cache),
            "files": list(self.cache.keys()),
        }
