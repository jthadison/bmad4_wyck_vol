# Component Testing Best Practices

## Setup and Teardown

### Proper beforeEach/afterEach
```typescript
import { setActivePinia, createPinia } from 'pinia'

describe('MyComponent', () => {
  let pinia: any

  beforeEach(() => {
    // Create fresh Pinia instance for each test
    pinia = createPinia()
    setActivePinia(pinia)

    // Reset mocks
    vi.clearAllMocks()
  })

  afterEach(() => {
    // Clean up any pending timers
    vi.clearAllTimers()
  })
})
```

## Mocking Stores

### Pattern 1: Direct State Manipulation
```typescript
const helpStore = useHelpStore()
helpStore.articles = mockArticles
helpStore.isLoading = false
```

### Pattern 2: Mock Actions
```typescript
const helpStore = useHelpStore()
vi.spyOn(helpStore, 'fetchArticles').mockImplementation(async () => {
  helpStore.articles = mockArticles
  helpStore.isLoading = false
})
```

## Testing v-html Content

```typescript
it('should render HTML content', () => {
  const wrapper = mount(Component)

  // Check raw HTML
  expect(wrapper.html()).toContain('<strong>Bold</strong>')

  // Check text content
  expect(wrapper.text()).toContain('Bold')
})
```

## Testing Keyboard Events

```typescript
it('should handle keyboard shortcuts', async () => {
  const wrapper = mount(Component)

  // Dispatch keyboard event
  await wrapper.find('input').trigger('keydown', { key: 'Enter' })

  await wrapper.vm.$nextTick()

  expect(wrapper.emitted('submit')).toBeTruthy()
})
```

## Testing PrimeVue Components

### Mocking PrimeVue
```typescript
vi.mock('primevue/dialog', () => ({
  default: {
    name: 'Dialog',
    template: '<div class="p-dialog"><slot /></div>',
    props: ['visible'],
  },
}))
```

### Testing PrimeVue Events
```typescript
it('should handle Dialog close', async () => {
  const wrapper = mount(ComponentWithDialog)

  // Find PrimeVue component
  const dialog = wrapper.findComponent({ name: 'Dialog' })

  // Emit event
  dialog.vm.$emit('update:visible', false)

  await wrapper.vm.$nextTick()

  expect(wrapper.vm.dialogVisible).toBe(false)
})
```

## Common Pitfalls

### ❌ Not Waiting for Async
```typescript
// BAD
it('renders data', () => {
  helpStore.fetchArticles()
  expect(wrapper.text()).toContain('Article')
})
```

### ✅ Properly Waiting
```typescript
// GOOD
it('renders data', async () => {
  await helpStore.fetchArticles()
  await flushPromises()
  expect(wrapper.text()).toContain('Article')
})
```

### ❌ Not Resetting Stores
```typescript
// BAD - tests can affect each other
describe('Tests', () => {
  const store = useMyStore()

  it('test 1', () => {
    store.data = 'test1'
  })

  it('test 2', () => {
    // Fails because store.data is still 'test1'
    expect(store.data).toBeUndefined()
  })
})
```

### ✅ Proper Store Reset
```typescript
// GOOD
describe('Tests', () => {
  beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)
  })

  it('test 1', () => {
    const store = useMyStore()
    store.data = 'test1'
  })

  it('test 2', () => {
    const store = useMyStore()
    expect(store.data).toBeUndefined()
  })
})
```

## Test Organization

```typescript
describe('ComponentName', () => {
  describe('Rendering', () => {
    it('should render basic structure', () => {})
    it('should render with props', () => {})
  })

  describe('User Interactions', () => {
    it('should handle click events', () => {})
    it('should handle form submission', () => {})
  })

  describe('Data Loading', () => {
    it('should show loading state', () => {})
    it('should display data when loaded', () => {})
    it('should handle errors', () => {})
  })

  describe('Edge Cases', () => {
    it('should handle empty data', () => {})
    it('should handle malformed input', () => {})
  })
})
```
