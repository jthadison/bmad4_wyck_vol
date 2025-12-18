/**
 * HTML Sanitization Utility (Story 11.8d - Task 8)
 *
 * Purpose:
 * --------
 * Provides defense-in-depth XSS protection by sanitizing HTML on the client side
 * using DOMPurify, in addition to server-side sanitization.
 *
 * Strategy:
 * ---------
 * Backend (Python Bleach) → Frontend (DOMPurify) → DOM Rendering
 *
 * This dual-layer approach ensures that even if backend sanitization is bypassed
 * or fails, the client-side sanitization will still prevent XSS attacks.
 *
 * Configuration:
 * --------------
 * - Allows safe formatting tags (h1-h6, p, strong, em, etc.)
 * - Allows safe structure tags (ul, ol, li, table, etc.)
 * - Allows safe attributes (href, title, id, class)
 * - Blocks all script tags, event handlers, and unsafe protocols
 *
 * Usage:
 * ------
 * import { sanitizeHtml } from '@/utils/sanitize'
 *
 * const safeHtml = sanitizeHtml(untrustedHtml)
 * // Use with v-html: <div v-html="safeHtml"></div>
 *
 * Author: Story 11.8d (Task 8)
 */

import DOMPurify from 'dompurify'

/**
 * Sanitizes HTML content to prevent XSS attacks
 *
 * @param html - The HTML string to sanitize
 * @returns Sanitized HTML string safe for rendering with v-html
 *
 * @example
 * const userInput = '<p>Safe content</p><script>alert("XSS")</script>'
 * const safe = sanitizeHtml(userInput)
 * // Result: '<p>Safe content</p>' (script tag removed)
 */
export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    // Allowed HTML tags for help content
    ALLOWED_TAGS: [
      // Headings
      'h1',
      'h2',
      'h3',
      'h4',
      'h5',
      'h6',
      // Paragraphs and breaks
      'p',
      'br',
      'hr',
      // Text formatting
      'strong',
      'em',
      'u',
      's',
      'mark',
      'span',
      'div',
      // Lists
      'ul',
      'ol',
      'li',
      // Links
      'a',
      // Code
      'code',
      'pre',
      // Quotes
      'blockquote',
      // Tables
      'table',
      'thead',
      'tbody',
      'tr',
      'th',
      'td',
    ],
    // Allowed HTML attributes
    ALLOWED_ATTR: [
      'href', // Links
      'title', // Tooltips
      'id', // Element identification
      'class', // CSS styling
    ],
    // Allowed URL protocols (blocks javascript:, data:, etc.)
    ALLOWED_URI_REGEXP:
      /^(?:(?:https?|mailto):|[^a-z]|[a-z+.-]+(?:[^a-z+.\-:]|$))/i,
    // Force strict tag filtering
    FORBID_TAGS: ['img', 'iframe', 'object', 'embed', 'script'],
  })
}
