/**
 * MarkdownRenderer Component Tests (Story 11.8a - Task 14)
 *
 * Tests for Markdown rendering, XSS sanitization, and [[Term]] link processing.
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MarkdownRenderer from '@/components/help/MarkdownRenderer.vue'

describe('MarkdownRenderer', () => {
  it('should render Markdown to HTML', () => {
    const markdown = '# Hello World\n\nThis is a **test**.'

    const wrapper = mount(MarkdownRenderer, {
      props: {
        content: markdown,
      },
    })

    const html = wrapper.find('.markdown-content').html()

    expect(html).toContain('<h1')
    expect(html).toContain('Hello World')
    expect(html).toContain('<strong>test</strong>')
  })

  it('should render lists correctly', () => {
    const markdown = `
- Item 1
- Item 2
- Item 3
    `

    const wrapper = mount(MarkdownRenderer, {
      props: {
        content: markdown,
      },
    })

    const html = wrapper.find('.markdown-content').html()

    expect(html).toContain('<ul')
    expect(html).toContain('<li')
    expect(html).toContain('Item 1')
  })

  it('should render code blocks', () => {
    const markdown = '```javascript\nconst x = 10;\n```'

    const wrapper = mount(MarkdownRenderer, {
      props: {
        content: markdown,
      },
    })

    const html = wrapper.find('.markdown-content').html()

    expect(html).toContain('<pre')
    expect(html).toContain('<code')
    expect(html).toContain('const x = 10;')
  })

  it('should render inline code', () => {
    const markdown = 'Use `console.log()` for debugging.'

    const wrapper = mount(MarkdownRenderer, {
      props: {
        content: markdown,
      },
    })

    const html = wrapper.find('.markdown-content').html()

    expect(html).toContain('<code>console.log()</code>')
  })

  it('should render blockquotes', () => {
    const markdown = '> This is a quote'

    const wrapper = mount(MarkdownRenderer, {
      props: {
        content: markdown,
      },
    })

    const html = wrapper.find('.markdown-content').html()

    expect(html).toContain('<blockquote')
    expect(html).toContain('This is a quote')
  })

  it('should render tables', () => {
    const markdown = `
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
    `

    const wrapper = mount(MarkdownRenderer, {
      props: {
        content: markdown,
      },
    })

    const html = wrapper.find('.markdown-content').html()

    expect(html).toContain('<table')
    expect(html).toContain('<thead')
    expect(html).toContain('<tbody')
    expect(html).toContain('Header 1')
    expect(html).toContain('Cell 1')
  })

  it('should convert [[Term]] to glossary links', () => {
    const markdown = 'The [[Spring]] pattern is detected when...'

    const wrapper = mount(MarkdownRenderer, {
      props: {
        content: markdown,
      },
    })

    const html = wrapper.find('.markdown-content').html()

    expect(html).toContain('href="/help/glossary#term-spring"')
    expect(html).toContain('class="glossary-link"')
    expect(html).toContain('>Spring</a>')
  })

  it('should handle multiple [[Term]] links', () => {
    const markdown = 'Both [[Spring]] and [[UTAD]] are Phase C patterns.'

    const wrapper = mount(MarkdownRenderer, {
      props: {
        content: markdown,
      },
    })

    const html = wrapper.find('.markdown-content').html()

    expect(html).toContain('href="/help/glossary#term-spring"')
    expect(html).toContain('href="/help/glossary#term-utad"')
    expect(html).toContain('>Spring</a>')
    expect(html).toContain('>UTAD</a>')
  })

  it('should sanitize XSS attempts', () => {
    const markdown = '<script>alert("XSS")</script>\n\nSafe content'

    const wrapper = mount(MarkdownRenderer, {
      props: {
        content: markdown,
        sanitize: true,
      },
    })

    const html = wrapper.find('.markdown-content').html()

    expect(html).not.toContain('<script')
    expect(html).not.toContain('alert("XSS")')
    expect(html).toContain('Safe content')
  })

  it('should sanitize dangerous HTML attributes', () => {
    const markdown = '<a href="javascript:alert(\'XSS\')">Click me</a>'

    const wrapper = mount(MarkdownRenderer, {
      props: {
        content: markdown,
        sanitize: true,
      },
    })

    const html = wrapper.find('.markdown-content').html()

    expect(html).not.toContain('javascript:')
  })

  it('should allow safe HTML when sanitize is true', () => {
    const markdown = '<strong>Bold</strong> and <em>italic</em>'

    const wrapper = mount(MarkdownRenderer, {
      props: {
        content: markdown,
        sanitize: true,
      },
    })

    const html = wrapper.find('.markdown-content').html()

    expect(html).toContain('<strong>Bold</strong>')
    expect(html).toContain('<em>italic</em>')
  })

  it('should skip sanitization when sanitize is false', () => {
    const markdown = '<div class="custom">Custom HTML</div>'

    const wrapper = mount(MarkdownRenderer, {
      props: {
        content: markdown,
        sanitize: false,
      },
    })

    const html = wrapper.find('.markdown-content').html()

    expect(html).toContain('<div class="custom">')
  })

  it('should handle empty content', () => {
    const wrapper = mount(MarkdownRenderer, {
      props: {
        content: '',
      },
    })

    expect(wrapper.find('.markdown-content').exists()).toBe(true)
  })

  it('should handle malformed Markdown gracefully', () => {
    const markdown = '# Unclosed header\n\n**Unclosed bold'

    const wrapper = mount(MarkdownRenderer, {
      props: {
        content: markdown,
      },
    })

    // Should not throw error
    expect(wrapper.find('.markdown-content').exists()).toBe(true)
  })

  it('should render links correctly', () => {
    const markdown = '[Link text](https://example.com)'

    const wrapper = mount(MarkdownRenderer, {
      props: {
        content: markdown,
      },
    })

    const html = wrapper.find('.markdown-content').html()

    expect(html).toContain('<a href="https://example.com"')
    expect(html).toContain('>Link text</a>')
  })

  it('should handle horizontal rules', () => {
    const markdown = 'Content above\n\n---\n\nContent below'

    const wrapper = mount(MarkdownRenderer, {
      props: {
        content: markdown,
      },
    })

    const html = wrapper.find('.markdown-content').html()

    expect(html).toContain('<hr')
  })
})
