# Help System Quick Start Guide

## Installation

1. **Install Dependencies:**
```bash
cd backend
poetry install
# Or: pip install python-frontmatter markdown-it-py mdit-py-plugins bleach pygments
```

2. **Run Database Migration:**
```bash
# Migration 017_add_help_system_tables.py should already exist
alembic upgrade head
```

## Basic Usage

### 1. Create Content

Create a Markdown file in `backend/src/help/content/`:

```markdown
---
title: "Spring Pattern"
category: "GLOSSARY"
short_definition: "A price move below support that reverses quickly"
wyckoff_phase: "C"
tags: ["pattern", "phase-c", "accumulation"]
keywords: "spring shakeout test creek"
---

# Spring Pattern

A **Spring** is a downside price move that penetrates below the [[Creek]]
support level during **[[Phase C]]**.

## Characteristics

- Occurs in Phase C during the test
- Penetrates Creek support level
- Reverses quickly (high Recovery speed)
- Often shows Stopping Volume

## Related Patterns

- [[UTAD]] - The distribution equivalent
- [[Creek]] - The support level being tested
```

### 2. Seed Database

```bash
cd backend
python -m src.help.seed_content
```

### 3. Start API Server

```bash
uvicorn src.api.main:app --reload
```

### 4. Test Endpoints

```bash
# List all articles
curl http://localhost:8000/api/v1/help/articles?category=ALL

# Get specific article
curl http://localhost:8000/api/v1/help/articles/spring-pattern

# Search
curl "http://localhost:8000/api/v1/help/search?q=spring"

# Get glossary
curl http://localhost:8000/api/v1/help/glossary

# Filter by phase
curl "http://localhost:8000/api/v1/help/glossary?wyckoff_phase=C"
```

## Programmatic Usage

### Load and Render Content

```python
from pathlib import Path
from src.help.content_loader import HelpContentLoader
from src.help.markdown_renderer import MarkdownRenderer

# Load content
loader = HelpContentLoader(Path("backend/src/help/content"))
files = loader.load_markdown_files()

# Render to HTML
renderer = MarkdownRenderer()
for file in files:
    html = renderer.render(file["content_markdown"])
    print(f"{file['slug']}: {len(html)} chars")
```

### Access Repository

```python
from src.database import async_session_maker
from src.repositories.help_repository import HelpRepository

async with async_session_maker() as session:
    repo = HelpRepository(session)

    # Get articles
    articles, total = await repo.get_articles(category="GLOSSARY", limit=10)

    # Search
    results, count = await repo.search_articles(query="spring pattern")

    # Get glossary
    terms, total = await repo.get_glossary_terms(wyckoff_phase="C")
```

## Content Organization

```
content/
├── glossary/
│   ├── phases/         # Phase-A.md, Phase-B.md, etc.
│   ├── patterns/       # Spring.md, UTAD.md, SOS.md, etc.
│   ├── concepts/       # Composite-Operator.md, etc.
│   ├── levels/         # Creek.md, Ice.md, Jump.md
│   └── signal/         # Signal-Confidence.md
├── faq/                # What-is-Wyckoff.md, etc.
└── reference/          # Reference docs
```

## Frontmatter Fields

### Required
- `title`: Article title
- `category`: GLOSSARY, FAQ, TUTORIAL, or REFERENCE

### Optional
- `short_definition`: Brief definition (glossary only)
- `wyckoff_phase`: A, B, C, D, or E (glossary only)
- `tags`: Array of tags
- `keywords`: Space-separated keywords
- `related_terms`: Array of related term slugs (glossary only)

## Custom Syntax

### Glossary Links

Use `[[Term]]` or `[[Term Name]]` to link to glossary entries:

```markdown
The [[Spring]] occurs in [[Phase C]].
```

Renders as:
```html
The <a href="/help/glossary/spring" class="glossary-link">Spring</a>
occurs in <a href="/help/glossary/phase-c" class="glossary-link">Phase C</a>.
```

## Testing

```bash
# Run all tests
pytest backend/tests/unit/test_content_loader.py -v
pytest backend/tests/unit/test_markdown_renderer.py -v
pytest backend/tests/integration/test_help_repository.py -v
pytest backend/tests/integration/test_help_api.py -v

# Run specific test
pytest backend/tests/unit/test_content_loader.py::TestHelpContentLoader::test_load_single_glossary_file -v
```

## Troubleshooting

### Content Not Loading

1. Check file has `.md` extension
2. Verify frontmatter YAML is valid
3. Check required fields (`title`, `category`) are present
4. Review logs for parsing errors

### Search Not Working

1. Verify migration 017 has been applied
2. Check `search_vector` column exists with GIN index
3. Test with simple single-word queries first
4. Review PostgreSQL logs

### XSS Concerns

All HTML is sanitized with bleach. Only whitelisted tags are allowed:
- Headings: h1-h6
- Text: p, strong, em
- Lists: ul, ol, li
- Links: a (with href validation)
- Code: code, pre
- Tables: table, thead, tbody, tr, th, td
- Other: blockquote, br, hr, div, span

Dangerous tags (script, iframe, etc.) are stripped.

## API Examples

### Get All FAQ Articles

```python
import requests

response = requests.get(
    "http://localhost:8000/api/v1/help/articles",
    params={"category": "FAQ", "limit": 20, "offset": 0}
)

data = response.json()
for article in data["articles"]:
    print(f"{article['title']}: {article['view_count']} views")
```

### Search with Highlighting

```python
response = requests.get(
    "http://localhost:8000/api/v1/help/search",
    params={"q": "spring pattern", "limit": 10}
)

data = response.json()
for result in data["results"]:
    print(f"{result['title']} (rank: {result['rank']})")
    print(f"  {result['snippet']}")
```

### Submit Feedback

```python
response = requests.post(
    "http://localhost:8000/api/v1/help/feedback",
    json={
        "article_id": "550e8400-e29b-41d4-a716-446655440000",
        "helpful": True,
        "user_comment": "Very helpful explanation!"
    }
)

print(response.json()["message"])  # "Thank you for your feedback!"
```

## Performance Tips

1. **Content Caching**: Loader caches parsed files with mtime checking
2. **Search Limits**: Keep search limit ≤ 50 for best performance
3. **Database Indexing**: GIN index on search_vector enables fast search
4. **View Tracking**: View count increments are async and non-blocking

## Next Steps

1. Create initial content files (see content/README.md)
2. Run seed script to populate database
3. Test API endpoints
4. Integrate with frontend (Story 11.8a frontend tasks)
5. Add tutorials (Story 11.8b)
6. Expand content library (Story 11.8c)

## Resources

- Full Documentation: `backend/src/help/README.md`
- Content Guidelines: `backend/src/help/content/README.md`
- API Reference: http://localhost:8000/docs (OpenAPI)
- Database Schema: `backend/alembic/versions/017_add_help_system_tables.py`
