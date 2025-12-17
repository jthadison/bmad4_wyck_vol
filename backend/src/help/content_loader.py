"""
Help Content Loader (Story 11.8a - Task 4, Story 11.8b - Task 2)

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

Author: Story 11.8a (Task 4), Story 11.8b (Task 2)
"""

import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import frontmatter
import structlog

from src.models.help import GlossaryTerm, HelpArticle, Tutorial, TutorialStep

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

    def parse_tutorial(self, file_path: Path) -> Tutorial:
        """
        Parse a tutorial from Markdown file (Story 11.8b - Task 2).

        Tutorial Format:
        ----------------
        Frontmatter:
        - title, description, difficulty, estimated_time_minutes, tags

        Content:
        - Step boundaries marked by headings: ## Step N: Title
        - Step content between headers
        - Optional metadata in HTML comments:
          <!-- action: Click Configuration button -->
          <!-- highlight: #config-button -->

        Parameters:
        -----------
        file_path : Path
            Path to tutorial Markdown file

        Returns:
        --------
        Tutorial
            Parsed tutorial model with steps

        Raises:
        -------
        ContentLoadError
            If file doesn't exist or parsing fails
        """
        parsed = self._load_single_file(file_path)

        if not parsed:
            raise ContentLoadError(f"Failed to load tutorial: {file_path}")

        if parsed["category"] != "TUTORIAL":
            raise ContentLoadError(
                f"File is not a tutorial (category={parsed['category']}): {file_path}"
            )

        # Load frontmatter again to get tutorial-specific fields
        with open(file_path, encoding="utf-8") as f:
            post = frontmatter.load(f)

        metadata = post.metadata
        content = post.content

        # Validate required tutorial fields
        if "difficulty" not in metadata:
            raise ContentLoadError(f"Tutorial missing 'difficulty' field: {file_path}")

        if "estimated_time_minutes" not in metadata:
            raise ContentLoadError(f"Tutorial missing 'estimated_time_minutes' field: {file_path}")

        difficulty = metadata["difficulty"]
        if difficulty not in ["BEGINNER", "INTERMEDIATE", "ADVANCED"]:
            raise ContentLoadError(
                f"Invalid difficulty '{difficulty}' in tutorial: {file_path}. "
                "Must be BEGINNER, INTERMEDIATE, or ADVANCED"
            )

        # Extract tutorial steps from content
        steps = self._extract_tutorial_steps(content)

        if not steps:
            raise ContentLoadError(f"No tutorial steps found in: {file_path}")

        # Build Tutorial model
        # Note: HTML rendering for each step happens in MarkdownRenderer
        return Tutorial(
            slug=parsed["slug"],
            title=parsed["title"],
            description=metadata.get("description", ""),
            difficulty=difficulty,
            estimated_time_minutes=metadata["estimated_time_minutes"],
            steps=steps,
            tags=parsed.get("tags", []),
            last_updated=datetime.now(UTC),
            completion_count=0,
        )

    def _extract_tutorial_steps(self, content: str) -> list[TutorialStep]:
        """
        Extract tutorial steps from Markdown content.

        Steps are identified by headings: ## Step N: Title

        Parameters:
        -----------
        content : str
            Markdown content

        Returns:
        --------
        list[TutorialStep]
            List of parsed tutorial steps (without HTML rendering)
        """
        # Regex to match step headers: ## Step N: Title
        step_header_pattern = re.compile(r"^## Step (\d+):\s*(.+)$", re.MULTILINE)

        # Find all step headers
        step_matches = list(step_header_pattern.finditer(content))

        if not step_matches:
            return []

        steps: list[TutorialStep] = []

        for i, match in enumerate(step_matches):
            step_number = int(match.group(1))
            step_title = match.group(2).strip()

            # Extract step content (from this header to next header or end)
            start_pos = match.end()
            if i + 1 < len(step_matches):
                end_pos = step_matches[i + 1].start()
            else:
                end_pos = len(content)

            step_content = content[start_pos:end_pos].strip()

            # Extract metadata from HTML comments
            action_required = self._extract_html_comment(step_content, "action")
            ui_highlight = self._extract_html_comment(step_content, "highlight")

            # Create TutorialStep
            # Note: content_html will be set by MarkdownRenderer during seeding
            step = TutorialStep(
                step_number=step_number,
                title=step_title,
                content_markdown=step_content,
                content_html="",  # Will be set by renderer
                action_required=action_required,
                ui_highlight=ui_highlight,
            )

            steps.append(step)

        # Validate step numbering is sequential
        for i, step in enumerate(steps, start=1):
            if step.step_number != i:
                logger.warning(
                    "Step numbering not sequential",
                    expected=i,
                    actual=step.step_number,
                    title=step.title,
                )

        return steps

    def _extract_html_comment(self, content: str, comment_key: str) -> str | None:
        """
        Extract value from HTML comment metadata.

        Looks for comments like: <!-- action: Click here -->

        Parameters:
        -----------
        content : str
            Markdown content
        comment_key : str
            Comment key to extract (e.g., "action", "highlight")

        Returns:
        --------
        str | None
            Comment value if found, None otherwise
        """
        pattern = re.compile(rf"<!--\s*{comment_key}:\s*(.+?)\s*-->", re.IGNORECASE)
        match = pattern.search(content)

        if match:
            return match.group(1).strip()

        return None

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
