"""
Help Content Seeding Script (Story 11.8a - Task 8, Story 11.8b - Task 6)

Purpose:
--------
Seeds help content from Markdown files into the database.
Implements idempotent upsert logic based on slug.

Usage:
------
# Seed all content (idempotent)
python -m src.help.seed_content

# Reset and re-seed
python -m src.help.seed_content --reset

Features:
---------
- Loads Markdown files using HelpContentLoader
- Renders HTML using MarkdownRenderer
- Upserts into help_articles, glossary_terms, and tutorials tables
- Idempotent: safe to run multiple times
- Logging for all operations

Author: Story 11.8a (Task 8), Story 11.8b (Task 6)
"""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import async_session_maker
from src.help.content_loader import HelpContentLoader
from src.help.markdown_renderer import MarkdownRenderer

logger = structlog.get_logger(__name__)


async def truncate_tables(session: AsyncSession) -> None:
    """
    Truncate help system tables.

    WARNING: Deletes all help content and feedback.

    Parameters:
    -----------
    session : AsyncSession
        Database session
    """
    logger.warning("Truncating help system tables...")

    await session.execute(text("TRUNCATE TABLE help_feedback CASCADE"))
    await session.execute(text("TRUNCATE TABLE tutorial_progress CASCADE"))
    await session.execute(text("TRUNCATE TABLE tutorials CASCADE"))
    await session.execute(text("TRUNCATE TABLE glossary_terms CASCADE"))
    await session.execute(text("TRUNCATE TABLE help_articles CASCADE"))
    await session.commit()

    logger.info("Tables truncated")


async def upsert_article(
    session: AsyncSession,
    slug: str,
    title: str,
    content_markdown: str,
    content_html: str,
    category: str,
    tags: list[str],
    keywords: str,
) -> None:
    """
    Upsert help article (insert or update).

    Uses PostgreSQL ON CONFLICT to implement upsert.

    Parameters:
    -----------
    session : AsyncSession
        Database session
    slug : str
        Article slug (unique identifier)
    title : str
        Article title
    content_markdown : str
        Markdown content
    content_html : str
        Rendered HTML content
    category : str
        Article category
    tags : list[str]
        Tag list
    keywords : str
        Search keywords
    """
    query = text(
        """
        INSERT INTO help_articles (
            slug, title, content_markdown, content_html,
            category, tags, keywords, last_updated
        )
        VALUES (
            :slug, :title, :content_markdown, :content_html,
            :category, :tags, :keywords, :last_updated
        )
        ON CONFLICT (slug)
        DO UPDATE SET
            title = EXCLUDED.title,
            content_markdown = EXCLUDED.content_markdown,
            content_html = EXCLUDED.content_html,
            category = EXCLUDED.category,
            tags = EXCLUDED.tags,
            keywords = EXCLUDED.keywords,
            last_updated = EXCLUDED.last_updated
        """
    )

    await session.execute(
        query,
        {
            "slug": slug,
            "title": title,
            "content_markdown": content_markdown,
            "content_html": content_html,
            "category": category,
            "tags": json.dumps(tags),
            "keywords": keywords,
            "last_updated": datetime.now(UTC),
        },
    )


async def upsert_glossary_term(
    session: AsyncSession,
    term: str,
    slug: str,
    short_definition: str,
    full_description_html: str,
    wyckoff_phase: str | None,
    related_terms: list[str],
    tags: list[str],
) -> None:
    """
    Upsert glossary term (insert or update).

    Uses PostgreSQL ON CONFLICT to implement upsert.

    Parameters:
    -----------
    session : AsyncSession
        Database session
    term : str
        Term name
    slug : str
        URL-friendly slug
    short_definition : str
        Brief definition
    full_description_html : str
        Full HTML description
    wyckoff_phase : str | None
        Associated Wyckoff phase
    related_terms : list[str]
        Related term slugs
    tags : list[str]
        Tag list
    """
    query = text(
        """
        INSERT INTO glossary_terms (
            term, slug, short_definition, full_description,
            full_description_html, wyckoff_phase, related_terms, tags, last_updated
        )
        VALUES (
            :term, :slug, :short_definition, '',
            :full_description_html, :wyckoff_phase, :related_terms, :tags, :last_updated
        )
        ON CONFLICT (slug)
        DO UPDATE SET
            term = EXCLUDED.term,
            short_definition = EXCLUDED.short_definition,
            full_description_html = EXCLUDED.full_description_html,
            wyckoff_phase = EXCLUDED.wyckoff_phase,
            related_terms = EXCLUDED.related_terms,
            tags = EXCLUDED.tags,
            last_updated = EXCLUDED.last_updated
        """
    )

    await session.execute(
        query,
        {
            "term": term,
            "slug": slug,
            "short_definition": short_definition,
            "full_description_html": full_description_html,
            "wyckoff_phase": wyckoff_phase,
            "related_terms": json.dumps(related_terms),
            "tags": json.dumps(tags),
            "last_updated": datetime.now(UTC),
        },
    )


async def upsert_tutorial(
    session: AsyncSession,
    slug: str,
    title: str,
    description: str,
    difficulty: str,
    estimated_time_minutes: int,
    steps: list[dict],
    tags: list[str],
) -> None:
    """
    Upsert tutorial (insert or update) - Story 11.8b - Task 6.

    Uses PostgreSQL ON CONFLICT to implement upsert.

    Parameters:
    -----------
    session : AsyncSession
        Database session
    slug : str
        Tutorial slug (unique identifier)
    title : str
        Tutorial title
    description : str
        Tutorial description
    difficulty : str
        Tutorial difficulty (BEGINNER, INTERMEDIATE, ADVANCED)
    estimated_time_minutes : int
        Estimated completion time in minutes
    steps : list[dict]
        List of tutorial steps as dicts (will be stored as JSONB)
    tags : list[str]
        Tag list
    """
    query = text(
        """
        INSERT INTO tutorials (
            slug, title, description, difficulty, estimated_time_minutes,
            steps, tags, last_updated
        )
        VALUES (
            :slug, :title, :description, :difficulty, :estimated_time_minutes,
            :steps, :tags, :last_updated
        )
        ON CONFLICT (slug)
        DO UPDATE SET
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            difficulty = EXCLUDED.difficulty,
            estimated_time_minutes = EXCLUDED.estimated_time_minutes,
            steps = EXCLUDED.steps,
            tags = EXCLUDED.tags,
            last_updated = EXCLUDED.last_updated
        """
    )

    await session.execute(
        query,
        {
            "slug": slug,
            "title": title,
            "description": description,
            "difficulty": difficulty,
            "estimated_time_minutes": estimated_time_minutes,
            "steps": json.dumps(steps),
            "tags": json.dumps(tags),
            "last_updated": datetime.now(UTC),
        },
    )


async def seed_help_content(content_dir: Path | None = None, reset: bool = False) -> None:
    """
    Seed help content from Markdown files into database.

    Process:
    --------
    1. Load all .md files using HelpContentLoader
    2. Render Markdown to HTML using MarkdownRenderer
    3. Upsert into database (idempotent)

    Parameters:
    -----------
    content_dir : Path | None
        Directory containing help content (default: backend/src/help/content/)
    reset : bool
        If True, truncate tables before seeding (default: False)

    Example:
    --------
    >>> await seed_help_content(reset=True)
    """
    logger.info("Starting help content seeding", reset=reset)

    # Initialize loader and renderer
    loader = HelpContentLoader(content_dir)
    renderer = MarkdownRenderer()

    # Load all Markdown files
    try:
        loaded_files = loader.load_markdown_files()
        logger.info("Loaded markdown files", count=len(loaded_files))
    except Exception as e:
        logger.error("Failed to load markdown files", error=str(e), exc_info=True)
        return

    if not loaded_files:
        logger.warning("No content files found to seed")
        return

    # Database operations
    async with async_session_maker() as session:
        async with session.begin():
            # Reset tables if requested
            if reset:
                await truncate_tables(session)

            # Process each file
            articles_count = 0
            glossary_count = 0
            tutorials_count = 0

            for parsed in loaded_files:
                try:
                    slug = parsed["slug"]
                    title = parsed["title"]
                    category = parsed["category"]
                    content_markdown = parsed["content_markdown"]
                    tags = parsed.get("tags", [])
                    keywords = parsed.get("keywords", "")

                    if category == "TUTORIAL":
                        # Parse tutorial using HelpContentLoader
                        # Note: We need to re-parse from file to get tutorial-specific data
                        file_path = Path(parsed["file_path"])
                        try:
                            tutorial = loader.parse_tutorial(file_path)

                            # Render HTML for each step
                            steps_with_html = []
                            for step in tutorial.steps:
                                step_html = renderer.render(step.content_markdown)
                                step_dict = step.model_dump()
                                step_dict["content_html"] = step_html
                                steps_with_html.append(step_dict)

                            # Insert tutorial
                            await upsert_tutorial(
                                session,
                                slug=tutorial.slug,
                                title=tutorial.title,
                                description=tutorial.description,
                                difficulty=tutorial.difficulty,
                                estimated_time_minutes=tutorial.estimated_time_minutes,
                                steps=steps_with_html,
                                tags=tutorial.tags,
                            )
                            tutorials_count += 1
                            logger.debug(
                                "Upserted tutorial",
                                slug=slug,
                                steps=len(steps_with_html),
                                difficulty=tutorial.difficulty,
                            )
                        except Exception as e:
                            logger.error(
                                "Failed to parse tutorial",
                                slug=slug,
                                file_path=str(file_path),
                                error=str(e),
                                exc_info=True,
                            )
                            continue

                    elif category == "GLOSSARY":
                        # Render Markdown to HTML
                        content_html = renderer.render(content_markdown)

                        # Insert as glossary term
                        await upsert_glossary_term(
                            session,
                            term=title,
                            slug=slug,
                            short_definition=parsed.get("short_definition", ""),
                            full_description_html=content_html,
                            wyckoff_phase=parsed.get("wyckoff_phase"),
                            related_terms=parsed.get("related_terms", []),
                            tags=tags,
                        )
                        glossary_count += 1
                        logger.debug("Upserted glossary term", slug=slug, term=title)
                    else:
                        # Render Markdown to HTML
                        content_html = renderer.render(content_markdown)

                        # Insert as help article
                        await upsert_article(
                            session,
                            slug=slug,
                            title=title,
                            content_markdown=content_markdown,
                            content_html=content_html,
                            category=category,
                            tags=tags,
                            keywords=keywords,
                        )
                        articles_count += 1
                        logger.debug("Upserted article", slug=slug, category=category)

                except Exception as e:
                    logger.error(
                        "Failed to process file",
                        slug=parsed.get("slug"),
                        error=str(e),
                        exc_info=True,
                    )
                    # Continue with other files

            # Commit all changes
            await session.commit()

            logger.info(
                "Help content seeding complete",
                articles=articles_count,
                glossary_terms=glossary_count,
                tutorials=tutorials_count,
                total=articles_count + glossary_count + tutorials_count,
            )


async def main() -> None:
    """
    CLI entry point for content seeding.

    Usage:
    ------
    python -m src.help.seed_content [--reset]
    """
    parser = argparse.ArgumentParser(description="Seed help content into database")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Truncate tables before seeding (WARNING: deletes all content)",
    )
    parser.add_argument(
        "--content-dir",
        type=str,
        help="Path to content directory (default: backend/src/help/content/)",
    )

    args = parser.parse_args()

    content_dir = Path(args.content_dir) if args.content_dir else None

    if args.reset:
        logger.warning("--reset flag provided: all help content will be deleted!")
        confirm = input("Type 'yes' to confirm: ")
        if confirm.lower() != "yes":
            logger.info("Seeding cancelled")
            return

    await seed_help_content(content_dir=content_dir, reset=args.reset)


if __name__ == "__main__":
    # Windows compatibility: Set UTF-8 encoding and event loop policy
    import sys

    if sys.platform == "win32":
        # Fix Unicode encoding issues on Windows console
        import os

        os.environ["PYTHONIOENCODING"] = "utf-8"
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")

        # Use WindowsSelectorEventLoopPolicy for psycopg async
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Configure structlog for CLI
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )

    asyncio.run(main())
