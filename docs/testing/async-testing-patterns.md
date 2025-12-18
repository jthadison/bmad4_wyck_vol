# Async Testing Patterns for Vue Components

## Overview
This guide documents best practices for testing asynchronous behavior in Vue 3 components using Vitest.

## Common Async Patterns

### 1. Using flushPromises()
```typescript
import { flushPromises } from '@vue/test-utils'

it('should wait for async data', async () => {
  const wrapper = mount(Component)

  // Trigger async action
  await wrapper.find('button').trigger('click')

  // Wait for all promises to resolve
  await flushPromises()

  // Now assertions will work
  expect(wrapper.text()).toContain('Expected text')
})
```

### 2. Using $nextTick()
```typescript
it('should wait for DOM updates', async () => {
  const wrapper = mount(Component)

  // Update reactive data
  wrapper.vm.someData = 'new value'

  // Wait for Vue to update DOM
  await wrapper.vm.$nextTick()

  expect(wrapper.text()).toContain('new value')
})
```

### 3. Multiple nextTick for Deep Updates
```typescript
it('should wait for nested component updates', async () => {
  const wrapper = mount(ParentComponent)

  // First tick: parent updates
  await wrapper.vm.$nextTick()

  // Second tick: child components update
  await wrapper.vm.$nextTick()

  expect(wrapper.findComponent(ChildComponent).exists()).toBe(true)
})
```

### 4. Testing PrimeVue Components
```typescript
it('should wait for PrimeVue Dialog to mount', async () => {
  const wrapper = mount(ComponentWithDialog)

  // PrimeVue components have async initialization
  await flushPromises()
  await wrapper.vm.$nextTick()

  const dialog = wrapper.findComponent(Dialog)
  expect(dialog.exists()).toBe(true)
})
```

### 5. Testing Store Actions
```typescript
it('should wait for store action to complete', async () => {
  const store = useMyStore()

  // Mock the API call
  vi.spyOn(api, 'fetchData').mockResolvedValue(mockData)

  // Call store action
  await store.fetchData()

  // Wait for reactive updates
  await flushPromises()

  expect(store.data).toEqual(mockData)
})
```

### 6. Custom waitFor Helper
```typescript
async function waitFor(condition: () => boolean, timeout = 1000) {
  const startTime = Date.now()

  while (!condition()) {
    if (Date.now() - startTime > timeout) {
      throw new Error('Timeout waiting for condition')
    }
    await new Promise(resolve => setTimeout(resolve, 50))
  }
}

it('should wait for conditional rendering', async () => {
  const wrapper = mount(Component)

  await waitFor(() => wrapper.find('.dynamic-element').exists())

  expect(wrapper.find('.dynamic-element').text()).toBe('Expected')
})
```

## Story 11.8d Test Fixes

### Issue: Tests failing due to async timing
**Root Cause**: Assertions running before component fully rendered

**Solution**:
1. Add `await flushPromises()` after API mocks
2. Use multiple `await wrapper.vm.$nextTick()` for nested updates
3. Mock store methods to return immediately
4. Wait for PrimeVue component initialization

### Example Fix
```typescript
// Before (FAILING)
it('should display FAQs', () => {
  helpStore.articles = mockFAQs
  const wrapper = mount(FAQView)

  expect(wrapper.findAll('.faq-item')).toHaveLength(3)
})

// After (PASSING)
it('should display FAQs', async () => {
  helpStore.articles = mockFAQs

  const wrapper = mount(FAQView)

  // Wait for component to mount
  await wrapper.vm.$nextTick()

  // Wait for PrimeVue Accordion to render
  await flushPromises()

  expect(wrapper.findAll('.faq-item')).toHaveLength(3)
})
```

## Best Practices

1. **Always await** async operations
2. **Use flushPromises()** after mocking API calls
3. **Use nextTick()** after updating reactive data
4. **Test one async operation at a time** for clarity
5. **Add descriptive comments** explaining why waits are needed
6. **Mock timers** when testing debounce/throttle
7. **Clean up** async operations in afterEach hooks

## References
- [Vue Test Utils Async Guide](https://test-utils.vuejs.org/guide/advanced/async-testing.html)
- [Vitest Async Matchers](https://vitest.dev/api/expect.html#async-matchers)
