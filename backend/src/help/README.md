# Help System Backend (Story 11.8a)

This directory contains the backend implementation for the help documentation system.

## Directory Structure

```
help/
├── __init__.py              # Module initialization
├── content_loader.py        # Loads Markdown files with frontmatter
├── markdown_renderer.py     # Renders Markdown to sanitized HTML
├── seed_content.py          # Seeds database from Markdown files
├── content/                 # Markdown help content
│   ├── README.md           # Content structure documentation
│   ├── glossary/           # Wyckoff terminology
│   ├── faq/                # Frequently asked questions
│   └── reference/          # Reference documentation
└── README.md               # This file
```

## Components

### HelpContentLoader (`content_loader.py`)

Loads and caches Markdown files with YAML frontmatter parsing.

**Features:**
- Recursive directory scanning for `.md` files
- YAML frontmatter parsing with `python-frontmatter`
- Content caching with mtime checking
- Glossary term and article parsing

**Usage:**
```python
from pathlib import Path
from src.help.content_loader import HelpContentLoader

loader = HelpContentLoader(Path("backend/src/help/content"))
loaded_files = loader.load_markdown_files()

for parsed in loaded_files:
    print(f"{parsed['slug']}: {parsed['title']}")
```

### MarkdownRenderer (`markdown_renderer.py`)

Renders Markdown to sanitized HTML with custom extensions.

**Features:**
- Markdown to HTML conversion with `markdown-it-py`
- Custom `[[Term]]` → glossary link conversion
- XSS sanitization with `bleach`
- Code syntax highlighting with `pygments`
- Table of contents extraction

**Usage:**
```python
from src.help.markdown_renderer import MarkdownRenderer

renderer = MarkdownRenderer()
html = renderer.render("The [[Spring]] pattern occurs in [[Phase C]].")
# Returns: The <a href="/help/glossary/spring">Spring</a> pattern...
```

### Content Seeding Script (`seed_content.py`)

Seeds database from Markdown files with idempotent upsert logic.

**Usage:**
```bash
# Seed all content (idempotent - safe to run multiple times)
python -m src.help.seed_content

# Reset and re-seed (WARNING: deletes all content)
python -m src.help.seed_content --reset

# Specify custom content directory
python -m src.help.seed_content --content-dir /path/to/content
```

**Process:**
1. Loads all `.md` files using `HelpContentLoader`
2. Renders Markdown to HTML using `MarkdownRenderer`
3. Upserts into `help_articles` and `glossary_terms` tables
4. Uses `ON CONFLICT` for idempotent updates

## Database Schema

### help_articles

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| slug | VARCHAR(200) | URL-friendly identifier (unique) |
| title | VARCHAR(300) | Article title |
| content_markdown | TEXT | Original Markdown content |
| content_html | TEXT | Rendered HTML content |
| category | VARCHAR(50) | GLOSSARY, FAQ, TUTORIAL, REFERENCE |
| tags | JSON | Tag array |
| keywords | TEXT | Search keywords |
| view_count | INTEGER | Number of views |
| helpful_count | INTEGER | Number of helpful votes |
| not_helpful_count | INTEGER | Number of not helpful votes |
| last_updated | TIMESTAMP | Last modification time |
| created_at | TIMESTAMP | Creation time |
| search_vector | TSVECTOR | Full-text search index (generated) |

### glossary_terms

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| term | VARCHAR(100) | Term name |
| slug | VARCHAR(200) | URL-friendly identifier (unique) |
| short_definition | VARCHAR(500) | Brief definition |
| full_description | TEXT | Complete Markdown description |
| full_description_html | TEXT | Rendered HTML description |
| wyckoff_phase | VARCHAR(1) | A/B/C/D/E (nullable) |
| related_terms | JSON | Related term slugs |
| tags | JSON | Tag array |
| last_updated | TIMESTAMP | Last modification time |
| created_at | TIMESTAMP | Creation time |

### help_feedback

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| article_id | UUID | Foreign key to help_articles |
| helpful | BOOLEAN | Whether article was helpful |
| user_comment | TEXT | Optional comment (nullable) |
| created_at | TIMESTAMP | Submission time |

## API Endpoints

### GET /api/v1/help/articles

Get help articles with optional filtering.

**Query Parameters:**
- `category`: GLOSSARY, FAQ, TUTORIAL, REFERENCE, ALL (default: ALL)
- `limit`: Max articles to return (1-100, default: 50)
- `offset`: Skip N articles for pagination (default: 0)

**Response:**
```json
{
  "articles": [
    {
      "id": "uuid",
      "slug": "spring-pattern",
      "title": "Spring Pattern",
      "content_markdown": "...",
      "content_html": "<p>...</p>",
      "category": "GLOSSARY",
      "tags": ["pattern", "wyckoff"],
      "keywords": "spring shakeout",
      "view_count": 42,
      "helpful_count": 15,
      "not_helpful_count": 2,
      "last_updated": "2024-03-15T14:30:00Z"
    }
  ],
  "total_count": 25
}
```

### GET /api/v1/help/articles/{slug}

Get specific article by slug. Increments view count.

**Response:** HelpArticle model

### GET /api/v1/help/search

Full-text search across articles.

**Query Parameters:**
- `q`: Search query (required, 1-200 chars)
- `limit`: Max results (1-50, default: 20)

**Response:**
```json
{
  "results": [
    {
      "id": "uuid",
      "slug": "spring-pattern",
      "title": "Spring Pattern",
      "category": "GLOSSARY",
      "snippet": "A <mark>spring</mark> is a price move...",
      "rank": 0.85
    }
  ],
  "query": "spring",
  "total_count": 3
}
```

### GET /api/v1/help/glossary

Get glossary terms with optional phase filtering.

**Query Parameters:**
- `wyckoff_phase`: A/B/C/D/E (optional)

**Response:**
```json
{
  "terms": [
    {
      "id": "uuid",
      "term": "Spring",
      "slug": "spring",
      "short_definition": "A price move below support",
      "full_description_html": "<p>...</p>",
      "wyckoff_phase": "C",
      "related_terms": ["creek", "ice"],
      "tags": ["pattern"],
      "last_updated": "2024-03-15T14:30:00Z"
    }
  ],
  "total_count": 15
}
```

### POST /api/v1/help/feedback

Submit user feedback on article.

**Request:**
```json
{
  "article_id": "uuid",
  "helpful": true,
  "user_comment": "Very helpful explanation!"
}
```

**Response:**
```json
{
  "feedback_id": "uuid",
  "message": "Thank you for your feedback!"
}
```

## TypeScript Type Generation

The help system models are compatible with TypeScript type generation.

### Manual Process (if pydantic-to-typescript is not set up)

1. Export OpenAPI schema:
```bash
cd backend
python -c "from src.api.main import app; import json; print(json.dumps(app.openapi()))" > openapi.json
```

2. Use OpenAPI to TypeScript converter or manually create types:

```typescript
// frontend/src/types/help.ts

export interface HelpArticle {
  id: string;
  slug: string;
  title: string;
  content_markdown: string;
  content_html: string;
  category: 'GLOSSARY' | 'FAQ' | 'TUTORIAL' | 'REFERENCE';
  tags: string[];
  keywords: string;
  view_count: number;
  helpful_count: number;
  not_helpful_count: number;
  last_updated: string;
}

export interface GlossaryTerm {
  id: string;
  term: string;
  slug: string;
  short_definition: string;
  full_description_html: string;
  wyckoff_phase?: 'A' | 'B' | 'C' | 'D' | 'E';
  related_terms: string[];
  tags: string[];
  last_updated: string;
}

export interface HelpSearchResult {
  id: string;
  slug: string;
  title: string;
  category: 'GLOSSARY' | 'FAQ' | 'TUTORIAL' | 'REFERENCE';
  snippet: string;
  rank: number;
}

export interface HelpFeedbackSubmission {
  article_id: string;
  helpful: boolean;
  user_comment?: string;
}

export interface HelpArticleListResponse {
  articles: HelpArticle[];
  total_count: number;
}

export interface GlossaryResponse {
  terms: GlossaryTerm[];
  total_count: number;
}

export interface SearchResponse {
  results: HelpSearchResult[];
  query: string;
  total_count: number;
}
```

## Testing

### Unit Tests

```bash
# Test content loader
pytest backend/tests/unit/test_content_loader.py -v

# Test Markdown renderer
pytest backend/tests/unit/test_markdown_renderer.py -v
```

### Integration Tests

```bash
# Test help repository
pytest backend/tests/integration/test_help_repository.py -v

# Test help API
pytest backend/tests/integration/test_help_api.py -v
```

## Content Management

See `content/README.md` for detailed documentation on:
- Markdown file format
- Frontmatter fields
- Glossary term linking with `[[Term]]` syntax
- Content organization best practices

## Dependencies

```toml
python-frontmatter = "^1.1.0"  # YAML frontmatter parsing
markdown-it-py = "^3.0.0"      # Markdown rendering
mdit-py-plugins = "^0.4.0"     # Markdown plugins (tables, tasks)
bleach = "^6.1.0"              # HTML sanitization
pygments = "^2.17.0"           # Code syntax highlighting
```

## Logging

All components use `structlog` for structured logging:

```python
import structlog
logger = structlog.get_logger(__name__)

logger.info("Content loaded", count=len(files), category="GLOSSARY")
logger.error("Failed to parse", file_path=path, error=str(e), exc_info=True)
```

## Security

- **XSS Prevention**: All HTML is sanitized with `bleach.clean()`
- **Allowed Tags**: Only safe HTML tags permitted (p, h1-h6, a, ul, ol, etc.)
- **URL Schemes**: Only http, https, mailto allowed
- **SQL Injection**: Parameterized queries with SQLAlchemy
- **Input Validation**: Pydantic models validate all input

## Performance

- **Content Caching**: Parsed Markdown cached in memory
- **Database Indexing**: GIN index on `search_vector` for fast full-text search
- **Query Limits**: Maximum 100 articles, 50 search results per request
- **View Count**: Async increment to avoid blocking

## Future Enhancements (Story 11.8b, 11.8c)

- Tutorial system with step-by-step walkthroughs
- Keyboard shortcuts reference
- Advanced FAQ with accordion UI
- Performance benchmarking
- Content audit tools
