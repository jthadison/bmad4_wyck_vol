/**
 * Debounce Utility Unit Tests
 *
 * Test Coverage:
 * - Type safety (parameter types, return type)
 * - Function execution is delayed
 * - Multiple rapid calls only execute once
 * - Last call wins when multiple calls occur
 * - Correct arguments are passed
 */

import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
  afterEach,
  expectTypeOf,
} from 'vitest'
import { debounce } from '@/utils/debounce'

describe('debounce', () => {
  describe('type safety', () => {
    it('preserves parameter types', () => {
      const fn = (a: string, b: number) => a.repeat(b)
      const debounced = debounce(fn, 100)

      // Type-level assertion - verifies the debounced function has correct parameter types
      expectTypeOf(debounced).toBeCallableWith('hello', 3)
    })

    it('returns void for debounced functions', () => {
      const fn = (x: number) => x * 2
      const debounced = debounce(fn, 100)

      expectTypeOf(debounced).returns.toBeVoid()
    })

    it('infers types from async functions', () => {
      const asyncFn = async (query: string) => ({ results: [query] })
      const debounced = debounce(asyncFn, 100)

      expectTypeOf(debounced).toBeCallableWith('search term')
      expectTypeOf(debounced).returns.toBeVoid()
    })
  })

  describe('functionality', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.restoreAllMocks()
    })

    it('delays function execution', () => {
      const fn = vi.fn()
      const debounced = debounce(fn, 500)

      debounced()

      expect(fn).not.toHaveBeenCalled()

      vi.advanceTimersByTime(500)

      expect(fn).toHaveBeenCalledTimes(1)
    })

    it('only executes once for multiple rapid calls', () => {
      const fn = vi.fn()
      const debounced = debounce(fn, 500)

      debounced()
      debounced()
      debounced()
      debounced()

      expect(fn).not.toHaveBeenCalled()

      vi.advanceTimersByTime(500)

      expect(fn).toHaveBeenCalledTimes(1)
    })

    it('uses arguments from the last call', () => {
      const fn = vi.fn()
      const debounced = debounce(fn, 500)

      debounced('first')
      debounced('second')
      debounced('third')

      vi.advanceTimersByTime(500)

      expect(fn).toHaveBeenCalledTimes(1)
      expect(fn).toHaveBeenCalledWith('third')
    })

    it('resets timer on each call', () => {
      const fn = vi.fn()
      const debounced = debounce(fn, 500)

      debounced()
      vi.advanceTimersByTime(300)

      debounced()
      vi.advanceTimersByTime(300)

      expect(fn).not.toHaveBeenCalled()

      vi.advanceTimersByTime(200)

      expect(fn).toHaveBeenCalledTimes(1)
    })

    it('handles multiple arguments', () => {
      const fn = vi.fn()
      const debounced = debounce(fn, 500)

      debounced('arg1', 'arg2', 'arg3')

      vi.advanceTimersByTime(500)

      expect(fn).toHaveBeenCalledWith('arg1', 'arg2', 'arg3')
    })

    it('allows multiple executions after delay expires', () => {
      const fn = vi.fn()
      const debounced = debounce(fn, 500)

      debounced()
      vi.advanceTimersByTime(500)

      expect(fn).toHaveBeenCalledTimes(1)

      debounced()
      vi.advanceTimersByTime(500)

      expect(fn).toHaveBeenCalledTimes(2)
    })

    it('passes arguments correctly with typed function', () => {
      const fn = vi.fn((a: string, b: number) => `${a}-${b}`)
      const debounced = debounce(fn, 100)

      debounced('test', 42)
      vi.advanceTimersByTime(100)

      expect(fn).toHaveBeenCalledWith('test', 42)
    })
  })
})
