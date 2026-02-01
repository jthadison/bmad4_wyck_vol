/**
 * Debounce Utility
 *
 * Creates a debounced function that delays execution until after a specified
 * wait time has elapsed since the last invocation.
 */

/**
 * Creates a debounced version of the provided function that delays
 * invocation until after `wait` milliseconds have elapsed since the
 * last call.
 *
 * @typeParam T - The function type being debounced
 * @param fn - The function to debounce
 * @param delay - Delay in milliseconds
 * @returns A debounced version of the function
 *
 * @example
 * ```typescript
 * const search = (query: string) => api.search(query);
 * const debouncedSearch = debounce(search, 300);
 *
 * // TypeScript knows debouncedSearch accepts (query: string)
 * debouncedSearch('hello'); // OK
 * debouncedSearch(123);     // TypeScript error
 * ```
 *
 * @remarks
 * The debounced function does not return a value since invocation
 * is deferred. If you need the return value, consider using a
 * promise-based debounce implementation.
 */
export function debounce<T extends (...args: Parameters<T>) => ReturnType<T>>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null

  return function (this: ThisParameterType<T>, ...args: Parameters<T>): void {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }

    timeoutId = setTimeout(() => {
      fn.apply(this, args)
      timeoutId = null
    }, delay)
  }
}
