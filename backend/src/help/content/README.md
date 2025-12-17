# Help Content Directory Structure

This directory contains Markdown-based help content for the BMAD Wyckoff system.

## Directory Structure

```
content/
├── glossary/           # Wyckoff terminology definitions
│   ├── phases/         # Wyckoff phase definitions (A, B, C, D, E)
│   ├── patterns/       # Pattern definitions (Spring, UTAD, SOS, LPS, etc.)
│   ├── concepts/       # Core Wyckoff concepts
│   ├── levels/         # Creek, Ice, Jump level definitions
│   └── signal/         # Signal-related terminology
├── faq/                # Frequently asked questions
└── reference/          # Reference documentation

## Markdown File Format

All content files must use YAML frontmatter for metadata:

```markdown
---
title: "Spring Pattern"
category: "GLOSSARY"
wyckoff_phase: "C"
tags: ["pattern", "wyckoff", "phase-c"]
keywords: "spring, shakeout, accumulation"
---

# Spring Pattern

A **Spring** is a price move below the support level (Creek)...
```

### Frontmatter Fields

#### Required Fields
- `title`: Article title (max 300 chars)
- `category`: One of `GLOSSARY`, `FAQ`, `TUTORIAL`, `REFERENCE`

#### Optional Fields
- `wyckoff_phase`: Associated Wyckoff phase (`A`, `B`, `C`, `D`, `E`) - only for glossary terms
- `tags`: Array of searchable tags
- `keywords`: Space-separated keywords for full-text search
- `short_definition`: Brief definition (max 500 chars) - for glossary terms

### Glossary Term Files

Glossary terms should include:
1. **Short definition** in frontmatter
2. **Full description** in Markdown body
3. **Related terms** using `[[TermName]]` syntax
4. **Phase context** explaining where this term appears in Wyckoff cycle

Example:
```markdown
---
title: "Spring"
category: "GLOSSARY"
short_definition: "A price move below support that reverses quickly"
wyckoff_phase: "C"
tags: ["pattern", "phase-c", "accumulation"]
keywords: "spring shakeout test creek"
---

# Spring

A **Spring** is a downside price move that penetrates below the [[Creek]] level during **[[Phase C]]**...

## Characteristics

- Occurs in **Phase C** during the test
- Penetrates [[Creek]] support level
- Reverses quickly (high [[Recovery]] speed)
- Often shows [[Stopping Volume]]

## Related Patterns

- [[UTAD]] - The distribution equivalent
- [[Creek]] - The support level being tested
- [[Test]] - The broader concept of testing support/resistance
```

### Custom Link Syntax

Use double brackets `[[TermName]]` to link to other glossary terms. These will be automatically converted to proper links:

- `[[Spring]]` → `/help/glossary/spring`
- `[[Phase C]]` → `/help/glossary/phase-c`

### FAQ Files

FAQ files should be structured as question-answer pairs:

```markdown
---
title: "What is Wyckoff Method?"
category: "FAQ"
tags: ["basics", "methodology"]
keywords: "wyckoff method accumulation distribution"
---

# What is Wyckoff Method?

The Wyckoff Method is a technical analysis approach developed by Richard Wyckoff...
```

## Content Loading

Content is loaded by `backend/src/help/content_loader.py`:

1. Scans all `.md` files in content directory
2. Parses YAML frontmatter using `python-frontmatter`
3. Renders Markdown to HTML using `markdown-it-py`
4. Sanitizes HTML with `bleach` to prevent XSS
5. Caches parsed content in memory

## Seeding Database

Use the seeding script to populate the database:

```bash
# Seed all content (idempotent)
python -m src.help.seed_content

# Reset and re-seed
python -m src.help.seed_content --reset
```

## Full-Text Search

All content is indexed for full-text search using PostgreSQL's `tsvector`:

- Searches across: title, content, keywords
- Supports ranking with `ts_rank`
- Returns highlighted snippets with `ts_headline`

## Content Guidelines

1. **Be concise** - Short, scannable paragraphs
2. **Use examples** - Show pattern examples when possible
3. **Cross-link** - Use `[[Term]]` syntax liberally
4. **Phase context** - Always mention which Wyckoff phase applies
5. **Visual aids** - Describe chart characteristics clearly
6. **Actionable** - Explain what traders should look for

## File Naming

- Use kebab-case: `spring-pattern.md`, `phase-c.md`
- Match the slug used in frontmatter
- Keep names descriptive but concise
