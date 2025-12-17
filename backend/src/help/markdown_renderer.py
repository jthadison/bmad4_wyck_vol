"""
Markdown Renderer (Story 11.8a - Task 5)

Purpose:
--------
Renders Markdown to sanitized HTML with custom Wyckoff term linking.
Provides XSS protection via bleach sanitization and supports code highlighting.

Classes:
--------
- MarkdownRenderer: Converts Markdown to safe HTML

Integration:
------------
- Used by content_loader.py and seed_content.py
- Converts [[Term]] syntax to glossary links
- Sanitizes all HTML output to prevent XSS attacks

Author: Story 11.8a (Task 5)
"""

import re
from typing import Any

import bleach
import structlog
from markdown_it import MarkdownIt
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

logger = structlog.get_logger(__name__)


class MarkdownRenderer:
    """
    Renders Markdown to sanitized HTML with custom extensions.

    Features:
    ---------
    - Converts Markdown to HTML using markdown-it-py
    - Converts [[Term]] to glossary links
    - Sanitizes HTML with bleach to prevent XSS
    - Supports code syntax highlighting with Pygments
    - Enables tables, task lists, and other extensions

    Example:
    --------
    >>> renderer = MarkdownRenderer()
    >>> html = renderer.render("The [[Spring]] pattern occurs in [[Phase C]]")
    >>> # Returns: The <a href="/help/glossary/spring">Spring</a> pattern...
    """

    # Allowed HTML tags for sanitization
    ALLOWED_TAGS = [
        "p",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "a",
        "ul",
        "ol",
        "li",
        "strong",
        "em",
        "code",
        "pre",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "blockquote",
        "br",
        "hr",
        "div",
        "span",
    ]

    # Allowed HTML attributes for sanitization
    ALLOWED_ATTRIBUTES = {
        "*": ["class", "id"],
        "a": ["href", "title", "class"],
        "code": ["class"],
        "pre": ["class"],
        "div": ["class"],
        "span": ["class"],
    }

    # Allowed URL schemes
    ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

    def __init__(self):
        """Initialize Markdown renderer with plugins."""
        # Create markdown-it instance with tables enabled
        self.md = MarkdownIt("default", {"html": False, "linkify": False, "typographer": True})

        # Enable table support
        self.md.enable("table")

        # Enable task list plugin
        self.md.use(tasklists_plugin)

        logger.debug("MarkdownRenderer initialized")

    def render(self, markdown: str) -> str:
        """
        Render Markdown to sanitized HTML.

        Process:
        --------
        1. Convert [[Term]] syntax to temporary markers
        2. Render Markdown to HTML
        3. Convert markers to glossary links
        4. Sanitize HTML with bleach

        Parameters:
        -----------
        markdown : str
            Markdown content to render

        Returns:
        --------
        str
            Sanitized HTML content

        Example:
        --------
        >>> renderer.render("# Spring\\n\\nThe [[Spring]] pattern...")
        '<h1>Spring</h1><p>The <a href="/help/glossary/spring">Spring</a>...</p>'
        """
        if not markdown or not markdown.strip():
            return ""

        try:
            # Step 1: Replace [[Term]] with placeholder to prevent Markdown interference
            # Use a placeholder format that won't trigger markdown parsing
            placeholders = {}
            placeholder_count = [0]  # Use list for closure mutability

            def create_placeholder(match: re.Match[str]) -> str:
                """Create a unique placeholder for each [[Term]]."""
                term = match.group(1)
                placeholder = f"GLOSSARYLINK{placeholder_count[0]}PLACEHOLDER"
                placeholders[placeholder] = term
                placeholder_count[0] += 1
                return placeholder

            processed = re.sub(r"\[\[([^\]]+)\]\]", create_placeholder, markdown)

            # Step 2: Render Markdown to HTML
            html = self.md.render(processed)

            # Step 3: Convert placeholders to glossary links
            for placeholder, term in placeholders.items():
                slug = term.lower().replace(" ", "-")
                link = f'<a href="/help/glossary/{slug}" class="glossary-link">{term}</a>'
                html = html.replace(placeholder, link)

            # Step 4: Sanitize HTML
            sanitized = self._sanitize_html(html)

            return sanitized

        except Exception as e:
            logger.error("Failed to render markdown", error=str(e), exc_info=True)
            # Return empty string on error to prevent displaying broken content
            return f"<p>Error rendering content: {str(e)}</p>"

    def _process_glossary_links(self, markdown: str) -> str:
        """
        Convert [[Term]] syntax to HTML links.

        Pattern: [[Term Name]] → <a href="/help/glossary/term-name" class="glossary-link">Term Name</a>

        Parameters:
        -----------
        markdown : str
            Markdown content with [[Term]] syntax

        Returns:
        --------
        str
            Markdown with [[Term]] converted to HTML links
        """
        # Pattern to match [[Term]] or [[Term Name]]
        pattern = r"\[\[([^\]]+)\]\]"

        def replace_link(match: re.Match[str]) -> str:
            """Replace match with HTML link."""
            term = match.group(1)
            # Convert term to slug: lowercase, replace spaces with hyphens
            slug = term.lower().replace(" ", "-")
            # Return HTML link
            return f'<a href="/help/glossary/{slug}" class="glossary-link">{term}</a>'

        return re.sub(pattern, replace_link, markdown)

    def _sanitize_html(self, html: str) -> str:
        """
        Sanitize HTML to prevent XSS attacks.

        Uses bleach to strip dangerous tags and attributes while
        preserving formatting and links.

        Parameters:
        -----------
        html : str
            HTML content to sanitize

        Returns:
        --------
        str
            Sanitized HTML content
        """
        return bleach.clean(
            html,
            tags=self.ALLOWED_TAGS,
            attributes=self.ALLOWED_ATTRIBUTES,
            protocols=self.ALLOWED_PROTOCOLS,
            strip=True,  # Strip disallowed tags instead of escaping
        )

    def highlight_code(self, code: str, language: str = "python") -> str:
        """
        Syntax highlight code block using Pygments.

        Parameters:
        -----------
        code : str
            Code to highlight
        language : str
            Programming language (default: python)

        Returns:
        --------
        str
            HTML with syntax highlighting

        Example:
        --------
        >>> renderer.highlight_code("def hello():\\n    pass", "python")
        '<div class="highlight">...</div>'
        """
        try:
            lexer = get_lexer_by_name(language, stripall=True)
            formatter = HtmlFormatter(
                cssclass="highlight",
                style="default",
                noclasses=False,
            )
            return highlight(code, lexer, formatter)
        except ClassNotFound:
            # Fallback to plain text if language not found
            logger.warning("Lexer not found for language", language=language)
            return f"<pre><code>{bleach.clean(code)}</code></pre>"

    def render_with_toc(self, markdown: str) -> tuple[str, list[dict[str, Any]]]:
        """
        Render Markdown with table of contents extraction.

        Extracts headers (h1-h6) to build a table of contents
        alongside the rendered HTML.

        Parameters:
        -----------
        markdown : str
            Markdown content

        Returns:
        --------
        tuple[str, list[dict]]
            Tuple of (rendered HTML, TOC items)
            TOC items: [{"level": 1, "text": "Header", "id": "header"}, ...]

        Example:
        --------
        >>> html, toc = renderer.render_with_toc("# Intro\\n## Details")
        >>> toc
        [{"level": 1, "text": "Intro", "id": "intro"},
         {"level": 2, "text": "Details", "id": "details"}]
        """
        # Render HTML
        html = self.render(markdown)

        # Extract TOC from headers
        toc: list[dict[str, Any]] = []
        header_pattern = r"<h([1-6])>(.*?)</h\1>"

        for match in re.finditer(header_pattern, html):
            level = int(match.group(1))
            text = bleach.clean(match.group(2), tags=[], strip=True)
            header_id = text.lower().replace(" ", "-")

            toc.append({"level": level, "text": text, "id": header_id})

        return html, toc
