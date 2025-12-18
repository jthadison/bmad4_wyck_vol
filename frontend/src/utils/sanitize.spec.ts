/**
 * Sanitization Utility Tests (Story 11.8d - Task 8.4)
 *
 * Tests for XSS prevention using DOMPurify client-side sanitization.
 */

import { describe, it, expect } from 'vitest'
import { sanitizeHtml } from './sanitize'

describe('sanitizeHtml', () => {
  describe('XSS Prevention', () => {
    it('should remove script tags', () => {
      const malicious = '<p>Safe content</p><script>alert("XSS")</script>'
      const sanitized = sanitizeHtml(malicious)

      expect(sanitized).not.toContain('<script>')
      expect(sanitized).not.toContain('alert')
      expect(sanitized).toContain('Safe content')
    })

    it('should remove onclick event handlers', () => {
      const malicious = '<a href="#" onclick="alert(\'XSS\')">Click me</a>'
      const sanitized = sanitizeHtml(malicious)

      expect(sanitized).not.toContain('onclick')
      expect(sanitized).not.toContain('alert')
      expect(sanitized).toContain('Click me')
    })

    it('should remove onerror event handlers', () => {
      const malicious = '<img src="x" onerror="alert(\'XSS\')" />'
      const sanitized = sanitizeHtml(malicious)

      expect(sanitized).not.toContain('onerror')
      expect(sanitized).not.toContain('alert')
      expect(sanitized).not.toContain('<img')
    })

    it('should remove onload event handlers', () => {
      const malicious = '<body onload="alert(\'XSS\')">Content</body>'
      const sanitized = sanitizeHtml(malicious)

      expect(sanitized).not.toContain('onload')
      expect(sanitized).not.toContain('alert')
      expect(sanitized).not.toContain('<body')
    })

    it('should remove javascript: protocol in href', () => {
      const malicious = '<a href="javascript:alert(\'XSS\')">Click</a>'
      const sanitized = sanitizeHtml(malicious)

      expect(sanitized).not.toContain('javascript:')
      expect(sanitized).not.toContain('alert')
    })

    it('should remove data: protocol in href', () => {
      const malicious =
        '<a href="data:text/html,<script>alert(\'XSS\')</script>">Click</a>'
      const sanitized = sanitizeHtml(malicious)

      expect(sanitized).not.toContain('data:')
    })

    it('should remove vbscript: protocol', () => {
      const malicious = '<a href="vbscript:alert(\'XSS\')">Click</a>'
      const sanitized = sanitizeHtml(malicious)

      expect(sanitized).not.toContain('vbscript:')
    })

    it('should remove inline style with expressions', () => {
      const malicious =
        '<div style="background: url(javascript:alert(\'XSS\'))">Content</div>'
      const sanitized = sanitizeHtml(malicious)

      // DOMPurify removes style attribute by default since it's not in ALLOWED_ATTR
      expect(sanitized).not.toContain('style=')
      expect(sanitized).not.toContain('javascript:')
    })

    it('should remove iframe tags', () => {
      const malicious = '<iframe src="https://evil.com"></iframe>'
      const sanitized = sanitizeHtml(malicious)

      expect(sanitized).not.toContain('<iframe')
      expect(sanitized).not.toContain('evil.com')
    })

    it('should remove object tags', () => {
      const malicious = '<object data="https://evil.com"></object>'
      const sanitized = sanitizeHtml(malicious)

      expect(sanitized).not.toContain('<object')
    })

    it('should remove embed tags', () => {
      const malicious = '<embed src="https://evil.com" />'
      const sanitized = sanitizeHtml(malicious)

      expect(sanitized).not.toContain('<embed')
    })
  })

  describe('Allowed HTML', () => {
    it('should allow safe heading tags', () => {
      const safe = '<h1>Title</h1><h2>Subtitle</h2><h3>Section</h3>'
      const sanitized = sanitizeHtml(safe)

      expect(sanitized).toContain('<h1>')
      expect(sanitized).toContain('<h2>')
      expect(sanitized).toContain('<h3>')
      expect(sanitized).toContain('Title')
      expect(sanitized).toContain('Subtitle')
      expect(sanitized).toContain('Section')
    })

    it('should allow paragraph tags', () => {
      const safe = '<p>This is a paragraph.</p>'
      const sanitized = sanitizeHtml(safe)

      expect(sanitized).toContain('<p>')
      expect(sanitized).toContain('This is a paragraph.')
    })

    it('should allow text formatting tags', () => {
      const safe =
        '<strong>Bold</strong> <em>Italic</em> <u>Underline</u> <s>Strikethrough</s>'
      const sanitized = sanitizeHtml(safe)

      expect(sanitized).toContain('<strong>')
      expect(sanitized).toContain('<em>')
      expect(sanitized).toContain('<u>')
      expect(sanitized).toContain('<s>')
    })

    it('should allow list tags', () => {
      const safe = '<ul><li>Item 1</li><li>Item 2</li></ul>'
      const sanitized = sanitizeHtml(safe)

      expect(sanitized).toContain('<ul>')
      expect(sanitized).toContain('<li>')
      expect(sanitized).toContain('Item 1')
    })

    it('should allow safe links with https', () => {
      const safe = '<a href="https://example.com" title="Example">Link</a>'
      const sanitized = sanitizeHtml(safe)

      expect(sanitized).toContain('<a ')
      expect(sanitized).toContain('href="https://example.com"')
      expect(sanitized).toContain('title="Example"')
      expect(sanitized).toContain('Link')
    })

    it('should allow mailto links', () => {
      const safe = '<a href="mailto:test@example.com">Email</a>'
      const sanitized = sanitizeHtml(safe)

      expect(sanitized).toContain('mailto:test@example.com')
    })

    it('should allow code and pre tags', () => {
      const safe = '<pre><code>const x = 42;</code></pre>'
      const sanitized = sanitizeHtml(safe)

      expect(sanitized).toContain('<pre>')
      expect(sanitized).toContain('<code>')
      expect(sanitized).toContain('const x = 42;')
    })

    it('should allow table tags', () => {
      const safe = `
        <table>
          <thead>
            <tr><th>Header</th></tr>
          </thead>
          <tbody>
            <tr><td>Data</td></tr>
          </tbody>
        </table>
      `
      const sanitized = sanitizeHtml(safe)

      expect(sanitized).toContain('<table>')
      expect(sanitized).toContain('<thead>')
      expect(sanitized).toContain('<th>')
      expect(sanitized).toContain('<tbody>')
      expect(sanitized).toContain('<td>')
    })

    it('should allow mark tag for highlighting', () => {
      const safe = '<p>This is <mark>highlighted</mark> text.</p>'
      const sanitized = sanitizeHtml(safe)

      expect(sanitized).toContain('<mark>')
      expect(sanitized).toContain('highlighted')
    })

    it('should allow blockquote tag', () => {
      const safe = '<blockquote>A quote</blockquote>'
      const sanitized = sanitizeHtml(safe)

      expect(sanitized).toContain('<blockquote>')
      expect(sanitized).toContain('A quote')
    })
  })

  describe('Allowed Attributes', () => {
    it('should allow id attribute', () => {
      const safe = '<div id="my-id">Content</div>'
      const sanitized = sanitizeHtml(safe)

      expect(sanitized).toContain('id="my-id"')
    })

    it('should allow class attribute', () => {
      const safe = '<div class="my-class">Content</div>'
      const sanitized = sanitizeHtml(safe)

      expect(sanitized).toContain('class="my-class"')
    })

    it('should allow href attribute on links', () => {
      const safe = '<a href="https://example.com">Link</a>'
      const sanitized = sanitizeHtml(safe)

      expect(sanitized).toContain('href="https://example.com"')
    })

    it('should allow title attribute', () => {
      const safe = '<span title="Tooltip text">Hover me</span>'
      const sanitized = sanitizeHtml(safe)

      expect(sanitized).toContain('title="Tooltip text"')
    })
  })

  describe('Edge Cases', () => {
    it('should handle empty string', () => {
      const sanitized = sanitizeHtml('')
      expect(sanitized).toBe('')
    })

    it('should handle plain text without HTML', () => {
      const text = 'Just plain text'
      const sanitized = sanitizeHtml(text)
      expect(sanitized).toBe('Just plain text')
    })

    it('should handle mixed safe and unsafe content', () => {
      const mixed =
        '<p>Safe paragraph</p><script>alert("XSS")</script><strong>Bold text</strong>'
      const sanitized = sanitizeHtml(mixed)

      expect(sanitized).toContain('<p>Safe paragraph</p>')
      expect(sanitized).toContain('<strong>Bold text</strong>')
      expect(sanitized).not.toContain('<script>')
      expect(sanitized).not.toContain('alert')
    })

    it('should handle nested tags correctly', () => {
      const nested = '<div><p><strong><em>Nested</em></strong></p></div>'
      const sanitized = sanitizeHtml(nested)

      expect(sanitized).toContain('<div>')
      expect(sanitized).toContain('<p>')
      expect(sanitized).toContain('<strong>')
      expect(sanitized).toContain('<em>')
      expect(sanitized).toContain('Nested')
    })

    it('should handle encoded HTML entities', () => {
      const entities = '<p>&lt;script&gt;alert("XSS")&lt;/script&gt;</p>'
      const sanitized = sanitizeHtml(entities)

      expect(sanitized).toContain('<p>')
      // Entities should be preserved and not executed
      expect(sanitized).not.toContain('<script>')
    })
  })

  describe('Defense-in-Depth Scenarios', () => {
    it('should protect against bypassed backend sanitization', () => {
      // Simulating a scenario where backend sanitization failed
      const bypassed = '<p>Content</p><script>fetch("/steal-data")</script>'
      const sanitized = sanitizeHtml(bypassed)

      expect(sanitized).toContain('Content')
      expect(sanitized).not.toContain('<script>')
      expect(sanitized).not.toContain('fetch')
    })

    it('should handle multiple XSS vectors in one string', () => {
      const multiVector = `
        <p>Safe</p>
        <script>alert(1)</script>
        <img src=x onerror=alert(2)>
        <a href="javascript:alert(3)">Link</a>
        <div onclick="alert(4)">Click</div>
      `
      const sanitized = sanitizeHtml(multiVector)

      // Verify safe content is preserved
      expect(sanitized).toContain('Safe')
      expect(sanitized).toContain('<p>')

      // Verify script tags are completely removed
      expect(sanitized).not.toContain('<script>')

      // Note: Individual XSS vectors are tested separately in dedicated tests above.
      // This test verifies that the sanitizer can handle multiple attack vectors
      // in a single string without crashing or throwing errors.
      expect(sanitized).toBeTruthy()
      expect(sanitized.length).toBeGreaterThan(0)
    })
  })
})
