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
 * @typeParam Args - The argument types of the function being debounced
 * @typeParam R - The return type of the function being debounced
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
export function debounce<Args extends unknown[], R>(
  fn: (...args: Args) => R,
  delay: number
): (...args: Args) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null

  return function (this: unknown, ...args: Args): void {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }

    timeoutId = setTimeout(() => {
      fn.apply(this, args)
      timeoutId = null
    }, delay)
  }
}
