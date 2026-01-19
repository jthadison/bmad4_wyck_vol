<template>
  <div class="markdown-renderer">
    <!-- eslint-disable-next-line vue/no-v-html -->
    <div class="markdown-content" v-html="sanitizedHtml"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

/**
 * MarkdownRenderer Component (Story 11.8a - Task 14)
 *
 * Renders Markdown content to safe HTML with:
 * - Markdown parsing via marked
 * - XSS sanitization via DOMPurify
 * - Custom [[Term]] link processing
 *
 * Prerequisites:
 * Run: npm install marked dompurify @types/dompurify
 */

// Props
interface Props {
  content: string
  sanitize?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  sanitize: true,
})

// ============================================================================
// Markdown Processing
// ============================================================================

/**
 * Process [[Term]] links before Markdown rendering
 * Converts [[Term]] to glossary links: <a href="/help/glossary/term" class="glossary-link">Term</a>
 */
function processGlossaryLinks(markdown: string): string {
  const pattern = /\[\[([^\]]+)\]\]/g

  return markdown.replace(pattern, (_match, term) => {
    const slug = term.toLowerCase().replace(/\s+/g, '-')
    return `<a href="/help/glossary#term-${slug}" class="glossary-link">${term}</a>`
  })
}

/**
 * Render Markdown to HTML
 */
const renderedHtml = computed(() => {
  // Process glossary links before Markdown rendering
  const processedMarkdown = processGlossaryLinks(props.content)

  // Parse Markdown to HTML
  try {
    return marked.parse(processedMarkdown, {
      breaks: true, // GFM line breaks
      gfm: true, // GitHub Flavored Markdown
    }) as string
  } catch (error) {
    console.error('Markdown parsing error:', error)
    return '<p>Error rendering content</p>'
  }
})

/**
 * Sanitize HTML to prevent XSS attacks
 */
const sanitizedHtml = computed(() => {
  if (!props.sanitize) {
    return renderedHtml.value
  }

  return DOMPurify.sanitize(renderedHtml.value, {
    ALLOWED_TAGS: [
      'p',
      'h1',
      'h2',
      'h3',
      'h4',
      'h5',
      'h6',
      'a',
      'ul',
      'ol',
      'li',
      'strong',
      'em',
      'code',
      'pre',
      'blockquote',
      'br',
      'hr',
      'table',
      'thead',
      'tbody',
      'tr',
      'th',
      'td',
      'img',
      'div',
      'span',
    ],
    ALLOWED_ATTR: ['href', 'class', 'src', 'alt', 'title', 'id'],
    ALLOWED_URI_REGEXP:
      /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|cid|xmpp|#):|[^a-z]|[a-z+.-]+(?:[^a-z+.-:]|$))/i,
  })
})
</script>

<style scoped>
.markdown-renderer {
  width: 100%;
}

.markdown-content {
  line-height: 1.7;
  color: var(--text-color);
}

/* Headings */
.markdown-content :deep(h1) {
  font-size: 2rem;
  margin-top: 2rem;
  margin-bottom: 1rem;
  font-weight: 700;
  color: var(--text-color);
  border-bottom: 2px solid var(--surface-border);
  padding-bottom: 0.5rem;
}

.markdown-content :deep(h2) {
  font-size: 1.75rem;
  margin-top: 1.75rem;
  margin-bottom: 0.875rem;
  font-weight: 600;
  color: var(--text-color);
}

.markdown-content :deep(h3) {
  font-size: 1.5rem;
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
  font-weight: 600;
  color: var(--text-color);
}

.markdown-content :deep(h4) {
  font-size: 1.25rem;
  margin-top: 1.25rem;
  margin-bottom: 0.625rem;
  font-weight: 600;
  color: var(--text-color);
}

.markdown-content :deep(h5),
.markdown-content :deep(h6) {
  font-size: 1.1rem;
  margin-top: 1rem;
  margin-bottom: 0.5rem;
  font-weight: 600;
  color: var(--text-color);
}

/* Paragraphs */
.markdown-content :deep(p) {
  margin-bottom: 1rem;
}

/* Lists */
.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin-bottom: 1rem;
  padding-left: 2rem;
}

.markdown-content :deep(li) {
  margin-bottom: 0.5rem;
}

.markdown-content :deep(ul ul),
.markdown-content :deep(ol ol),
.markdown-content :deep(ul ol),
.markdown-content :deep(ol ul) {
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
}

/* Links */
.markdown-content :deep(a) {
  color: var(--primary-color);
  text-decoration: none;
  transition: color 0.2s;
}

.markdown-content :deep(a:hover) {
  text-decoration: underline;
  color: var(--primary-color-hover);
}

.markdown-content :deep(a.glossary-link) {
  color: var(--blue-500);
  font-weight: 500;
  border-bottom: 1px dotted var(--blue-400);
}

.markdown-content :deep(a.glossary-link:hover) {
  border-bottom-style: solid;
  text-decoration: none;
}

/* Code */
.markdown-content :deep(code) {
  background-color: var(--surface-ground);
  padding: 0.2rem 0.4rem;
  border-radius: 3px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.9em;
  color: var(--text-color);
}

.markdown-content :deep(pre) {
  background-color: var(--surface-ground);
  padding: 1rem;
  border-radius: 6px;
  overflow-x: auto;
  margin-bottom: 1rem;
  border: 1px solid var(--surface-border);
}

.markdown-content :deep(pre code) {
  background-color: transparent;
  padding: 0;
  font-size: 0.875rem;
}

/* Blockquotes */
.markdown-content :deep(blockquote) {
  border-left: 4px solid var(--primary-color);
  padding-left: 1rem;
  margin: 1rem 0;
  font-style: italic;
  color: var(--text-color-secondary);
  background-color: var(--surface-ground);
  padding: 1rem;
  border-radius: 4px;
}

.markdown-content :deep(blockquote p) {
  margin-bottom: 0;
}

/* Horizontal Rule */
.markdown-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--surface-border);
  margin: 2rem 0;
}

/* Tables */
.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1rem;
  border: 1px solid var(--surface-border);
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid var(--surface-border);
  padding: 0.75rem;
  text-align: left;
}

.markdown-content :deep(th) {
  background-color: var(--surface-ground);
  font-weight: 600;
  color: var(--text-color);
}

.markdown-content :deep(tr:nth-child(even)) {
  background-color: var(--surface-ground);
}

/* Images */
.markdown-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  margin: 1rem 0;
}

/* Strong/Bold */
.markdown-content :deep(strong) {
  font-weight: 700;
}

/* Emphasis/Italic */
.markdown-content :deep(em) {
  font-style: italic;
}
</style>
