# XSS Prevention Strategy

## Overview
This document describes the defense-in-depth Cross-Site Scripting (XSS) prevention strategy implemented in the help documentation system.

## Architecture: Two-Layer Protection

### Layer 1: Backend Sanitization (Python Bleach)
**Location**: `backend/src/help/markdown_renderer.py`

**Configuration**:
```python
import bleach

ALLOWED_TAGS = [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'br', 'hr', 'strong', 'em', 'u', 's',
    'ul', 'ol', 'li', 'a', 'code', 'pre',
    'blockquote', 'table', 'thead', 'tbody', 'tr', 'th', 'td'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    '*': ['id', 'class']
}

def sanitize_html(html: str) -> str:
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True
    )
```

**Purpose**:
- Primary defense against XSS
- Sanitizes markdown-generated HTML before storing in database
- Prevents malicious content from being persisted

### Layer 2: Frontend Sanitization (DOMPurify)
**Location**: `frontend/src/utils/sanitize.ts` (Story 11.8d)

**Configuration**:
```typescript
import DOMPurify from 'dompurify'

export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'p', 'br', 'hr', 'strong', 'em', 'u', 's', 'mark', 'span', 'div',
      'ul', 'ol', 'li', 'a', 'code', 'pre', 'blockquote',
      'table', 'thead', 'tbody', 'tr', 'th', 'td'
    ],
    ALLOWED_ATTR: ['href', 'title', 'id', 'class'],
    ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto):|[^a-z]|[a-z+.-]+(?:[^a-z+.\-:]|$))/i,
  })
}
```

**Purpose**:
- Defense-in-depth protection
- Protects against backend sanitization bypass
- Client-side last line of defense before DOM rendering

## Why Two Layers?

### Defense-in-Depth Principle
Never rely on a single security control. If backend sanitization fails (bug, bypass, database compromise), frontend sanitization provides backup protection.

### Threat Scenarios Protected Against

1. **Backend Bypass**: Attacker finds vulnerability in Bleach configuration
   - **Mitigation**: DOMPurify still sanitizes before rendering

2. **Database Injection**: Malicious content inserted directly into database
   - **Mitigation**: DOMPurify sanitizes on read

3. **API Response Tampering**: Man-in-the-middle modifies API response
   - **Mitigation**: DOMPurify sanitizes before rendering

4. **Zero-Day in Backend Library**: Bleach has undiscovered vulnerability
   - **Mitigation**: DOMPurify provides independent protection

## Usage in Components

### Example: FAQView.vue
```typescript
import { sanitizeHtml } from '@/utils/sanitize'

// For search highlighting
const highlightSearchTerm = (text: string): string => {
  const query = searchQuery.value.trim()
  if (!query) return text

  const regex = new RegExp(`(${query})`, 'gi')
  const highlighted = text.replace(regex, '<mark>$1</mark>')

  // Sanitize to prevent XSS in user-generated search queries
  return sanitizeHtml(highlighted)
}

// For article content
const sanitizedContent = (article: HelpArticle): string => {
  return sanitizeHtml(article.content_html)
}
```

```vue
<template>
  <!-- Safe: Double-sanitized content -->
  <div v-html="sanitizedContent(article)"></div>

  <!-- Safe: Sanitized search highlighting -->
  <span v-html="highlightSearchTerm(article.title)"></span>
</template>
```

## What Gets Blocked?

### Script Tags
```html
<!-- Input -->
<p>Safe</p><script>alert('XSS')</script>

<!-- Output -->
<p>Safe</p>
```

### Event Handlers
```html
<!-- Input -->
<a href="#" onclick="alert('XSS')">Click</a>

<!-- Output -->
<a href="#">Click</a>
```

### JavaScript Protocols
```html
<!-- Input -->
<a href="javascript:alert('XSS')">Link</a>

<!-- Output -->
<a>Link</a>
```

### Data URLs
```html
<!-- Input -->
<a href="data:text/html,<script>alert('XSS')</script>">Link</a>

<!-- Output -->
<a>Link</a>
```

## What's Allowed?

### Safe HTML
```html
<h1>Heading</h1>
<p>Paragraph with <strong>bold</strong> and <em>italic</em></p>
<ul>
  <li>List item</li>
</ul>
<a href="https://example.com" title="Safe link">Link</a>
<code>const x = 42;</code>
<pre><code>function example() {}</code></pre>
```

### Safe Attributes
- `href` (on `<a>` tags, validated URLs only)
- `title` (tooltip text)
- `id` (element identification)
- `class` (CSS styling)

### Safe Protocols
- `https://` - Secure HTTP
- `http://` - HTTP (allowed but HTTPS preferred)
- `mailto:` - Email links
- Relative URLs (`/path/to/page`)

## Testing XSS Protection

### Unit Tests
Location: `frontend/src/utils/sanitize.spec.ts`

30+ test cases covering:
- Script tag removal
- Event handler removal
- Protocol validation
- Allowed HTML passthrough
- Edge cases and encoded entities

### Component Tests
Location: `frontend/tests/components/*.spec.ts`

XSS tests added to:
- `FAQView.spec.ts` - Tests FAQ content sanitization
- `ArticleView.spec.ts` - Tests article content sanitization

Example test:
```typescript
it('should sanitize malicious HTML', async () => {
  const malicious = {
    content_html: '<p>Safe</p><script>alert("XSS")</script>'
  }

  const wrapper = mount(Component, { props: { article: malicious } })
  await flushPromises()

  expect(wrapper.html()).not.toContain('<script>')
  expect(wrapper.html()).toContain('Safe')
})
```

## Maintenance Guidelines

### When to Update Allowed Tags
1. Review security implications
2. Update both backend AND frontend configurations
3. Add test cases for new tags
4. Document the change

### When Adding New v-html Usage
1. **ALWAYS** sanitize with `sanitizeHtml()`
2. Add ESLint disable comment with explanation
3. Add XSS test for the component
4. Document in component header

### Regular Audits
- Review all v-html usage quarterly
- Update DOMPurify to latest version
- Monitor security advisories for Bleach and DOMPurify
- Run penetration tests on help system

## References
- [OWASP XSS Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [DOMPurify Documentation](https://github.com/cure53/DOMPurify)
- [Bleach Documentation](https://bleach.readthedocs.io/)
- Story 11.8a: Backend sanitization implementation
- Story 11.8d: Frontend sanitization implementation

## Contact
For security concerns, contact: Security Team

Last Updated: 2025-12-18 (Story 11.8d)
