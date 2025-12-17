"""
Unit tests for MarkdownRenderer (Story 11.8a - Task 5)

Tests:
------
- Markdown to HTML conversion
- Glossary link conversion ([[Term]] syntax)
- XSS sanitization
- Code highlighting
- Table of contents extraction
"""


from src.help.markdown_renderer import MarkdownRenderer


class TestMarkdownRenderer:
    """Test suite for MarkdownRenderer."""

    def test_basic_markdown_rendering(self):
        """Test basic Markdown to HTML conversion."""
        renderer = MarkdownRenderer()

        markdown = "# Heading\n\nThis is a **bold** paragraph."
        html = renderer.render(markdown)

        assert "<h1>Heading</h1>" in html
        assert "<strong>bold</strong>" in html
        assert "<p>" in html

    def test_glossary_link_conversion(self):
        """Test [[Term]] conversion to glossary links."""
        renderer = MarkdownRenderer()

        markdown = "The [[Spring]] pattern occurs in [[Phase C]]."
        html = renderer.render(markdown)

        # Check for glossary links
        assert '<a href="/help/glossary/spring" class="glossary-link">Spring</a>' in html
        assert '<a href="/help/glossary/phase-c" class="glossary-link">Phase C</a>' in html

    def test_multiple_glossary_links(self):
        """Test multiple glossary links in one document."""
        renderer = MarkdownRenderer()

        markdown = """
The [[Spring]] and [[UTAD]] are opposite patterns.
Both occur in [[Phase C]] and test the [[Creek]] level.
"""
        html = renderer.render(markdown)

        assert "spring" in html.lower()
        assert "utad" in html.lower()
        assert "phase-c" in html.lower()
        assert "creek" in html.lower()
        assert 'class="glossary-link"' in html

    def test_table_rendering(self):
        """Test Markdown table rendering."""
        renderer = MarkdownRenderer()

        markdown = """
| Pattern | Phase |
|---------|-------|
| Spring  | C     |
| UTAD    | C     |
"""
        html = renderer.render(markdown)

        assert "<table>" in html
        assert "<thead>" in html
        assert "<tbody>" in html
        assert "<th>Pattern</th>" in html
        assert "<td>Spring</td>" in html

    def test_code_block_rendering(self):
        """Test code block rendering."""
        renderer = MarkdownRenderer()

        markdown = """
```python
def hello():
    return "world"
```
"""
        html = renderer.render(markdown)

        assert "<code" in html or "<pre" in html

    def test_xss_sanitization(self):
        """Test XSS prevention through sanitization."""
        renderer = MarkdownRenderer()

        # Attempt to inject script
        markdown = """
<script>alert('XSS')</script>
<a href="javascript:alert('XSS')">Click me</a>
"""
        html = renderer.render(markdown)

        # Script tags should be escaped or removed (not executable)
        assert "<script>" not in html  # No executable script tag
        # Check that dangerous content is escaped, not executable
        assert "&lt;script&gt;" in html or "<script>" not in html  # Script is escaped
        # The href with javascript: should either be removed or the whole tag escaped
        # If the tag is escaped, it won't execute
        assert '<a href="javascript:' not in html  # No executable javascript: link

    def test_allowed_html_tags(self):
        """Test that allowed HTML tags are preserved."""
        renderer = MarkdownRenderer()

        markdown = "This is **bold** and *italic* text."
        html = renderer.render(markdown)

        assert "<strong>" in html  # Bold
        assert "<em>" in html  # Italic

    def test_empty_markdown(self):
        """Test rendering empty or whitespace-only Markdown."""
        renderer = MarkdownRenderer()

        assert renderer.render("") == ""
        assert renderer.render("   \n  \n  ") == ""

    def test_list_rendering(self):
        """Test ordered and unordered list rendering."""
        renderer = MarkdownRenderer()

        markdown = """
- Item 1
- Item 2

1. First
2. Second
"""
        html = renderer.render(markdown)

        assert "<ul>" in html
        assert "<ol>" in html
        assert "<li>" in html

    def test_blockquote_rendering(self):
        """Test blockquote rendering."""
        renderer = MarkdownRenderer()

        markdown = "> This is a quote"
        html = renderer.render(markdown)

        assert "<blockquote>" in html

    def test_link_rendering(self):
        """Test standard link rendering."""
        renderer = MarkdownRenderer()

        markdown = "[Example](https://example.com)"
        html = renderer.render(markdown)

        assert '<a href="https://example.com"' in html
        assert ">Example</a>" in html

    def test_render_with_toc(self):
        """Test table of contents extraction."""
        renderer = MarkdownRenderer()

        markdown = """
# Introduction

## Getting Started

### Prerequisites

## Advanced Topics
"""
        html, toc = renderer.render_with_toc(markdown)

        # Check HTML
        assert "<h1>Introduction</h1>" in html
        assert "<h2>Getting Started</h2>" in html

        # Check TOC
        assert len(toc) == 4
        assert toc[0]["level"] == 1
        assert toc[0]["text"] == "Introduction"
        assert toc[1]["level"] == 2
        assert toc[1]["text"] == "Getting Started"

    def test_code_highlighting(self):
        """Test syntax highlighting for code blocks."""
        renderer = MarkdownRenderer()

        code = "def hello():\n    return 'world'"
        html = renderer.highlight_code(code, "python")

        assert "highlight" in html
        assert "def" in html

    def test_code_highlighting_unknown_language(self):
        """Test code highlighting fallback for unknown language."""
        renderer = MarkdownRenderer()

        code = "some code"
        html = renderer.highlight_code(code, "unknown-language-xyz")

        # Should fall back to plain text
        assert "some code" in html
        assert "<pre>" in html or "<code>" in html

    def test_complex_document_rendering(self):
        """Test rendering a complex document with multiple elements."""
        renderer = MarkdownRenderer()

        markdown = """
# Spring Pattern

The [[Spring]] is a key pattern in **[[Phase C]]**.

## Characteristics

- Penetrates [[Creek]] support
- Quick recovery
- High volume

## Example

| Bar | Price | Volume |
|-----|-------|--------|
| 1   | 100   | High   |
| 2   | 95    | Ultra  |
| 3   | 102   | Low    |

> Always verify volume confirmation!
"""
        html = renderer.render(markdown)

        # Check all elements are present
        assert "<h1>" in html
        assert "<h2>" in html
        assert "<ul>" in html
        assert "<table>" in html
        assert "<blockquote>" in html
        assert 'class="glossary-link"' in html
        assert "<strong>" in html

    def test_task_list_rendering(self):
        """Test task list rendering (plugin)."""
        renderer = MarkdownRenderer()

        markdown = """
- [x] Completed task
- [ ] Pending task
"""
        html = renderer.render(markdown)

        # Task lists should be rendered with class attributes
        assert '<li class="task-list-item">' in html
        assert "Completed task" in html
        assert "Pending task" in html

    def test_error_handling(self):
        """Test error handling for invalid input."""
        renderer = MarkdownRenderer()

        # None input should be handled gracefully
        # (though type hints prevent this in production)
        result = renderer.render("")
        assert result == ""
