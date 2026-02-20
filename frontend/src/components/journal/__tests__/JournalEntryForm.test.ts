/**
 * JournalEntryForm Component Unit Tests
 *
 * Feature P2-8 (Trade Journal)
 *
 * Test Coverage:
 * - Form renders with empty state for new entry
 * - Form pre-fills when editing existing entry
 * - Wyckoff checklist renders all 4 criteria
 * - Checklist score computes correctly
 * - Emotional state selection works
 * - Save emits correct payload
 * - Cancel emits cancel event
 * - Save disabled when symbol is empty
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import JournalEntryForm from '@/components/journal/JournalEntryForm.vue'
import type { JournalEntry } from '@/services/journalService'

const mockEntry: JournalEntry = {
  id: 'test-id-1',
  user_id: 'user-id-1',
  campaign_id: null,
  signal_id: null,
  symbol: 'AAPL',
  entry_type: 'pre_trade',
  notes: 'Spring formed below creek on low volume.',
  emotional_state: 'disciplined',
  wyckoff_checklist: {
    phase_confirmed: true,
    volume_confirmed: true,
    creek_identified: false,
    pattern_confirmed: false,
  },
  checklist_score: 2,
  created_at: '2026-02-20T10:00:00Z',
  updated_at: '2026-02-20T10:00:00Z',
}

describe('JournalEntryForm', () => {
  it('renders empty form for new entry', () => {
    const wrapper = mount(JournalEntryForm)
    const symbolInput = wrapper.find('[data-testid="journal-symbol"]')
    expect(symbolInput.exists()).toBe(true)
    expect((symbolInput.element as HTMLInputElement).value).toBe('')
  })

  it('pre-fills form when editing existing entry', () => {
    const wrapper = mount(JournalEntryForm, {
      props: { entry: mockEntry },
    })
    const symbolInput = wrapper.find('[data-testid="journal-symbol"]')
    expect((symbolInput.element as HTMLInputElement).value).toBe('AAPL')

    const notesArea = wrapper.find('[data-testid="journal-notes"]')
    expect((notesArea.element as HTMLTextAreaElement).value).toBe(
      'Spring formed below creek on low volume.'
    )
  })

  it('renders all 4 Wyckoff checklist items', () => {
    const wrapper = mount(JournalEntryForm)
    expect(wrapper.find('[data-testid="check-phase"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="check-volume"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="check-creek"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="check-pattern"]').exists()).toBe(true)
  })

  it('shows 0/4 score when no checklist items are checked', () => {
    const wrapper = mount(JournalEntryForm)
    const score = wrapper.find('[data-testid="checklist-score"]')
    expect(score.text()).toContain('0/4')
  })

  it('shows correct score from existing entry', () => {
    const wrapper = mount(JournalEntryForm, {
      props: { entry: mockEntry },
    })
    const score = wrapper.find('[data-testid="checklist-score"]')
    expect(score.text()).toContain('2/4')
  })

  it('renders emotional state options', () => {
    const wrapper = mount(JournalEntryForm)
    const emotionContainer = wrapper.find(
      '[data-testid="journal-emotional-state"]'
    )
    expect(emotionContainer.exists()).toBe(true)
    // Should have 5 options (disciplined, confident, neutral, uncertain, fomo)
    const buttons = emotionContainer.findAll('button')
    expect(buttons.length).toBe(5)
  })

  it('emits save with correct payload when form is submitted', async () => {
    const wrapper = mount(JournalEntryForm)

    // Fill in symbol
    const symbolInput = wrapper.find('[data-testid="journal-symbol"]')
    await symbolInput.setValue('SPY')

    // Fill in notes
    const notesArea = wrapper.find('[data-testid="journal-notes"]')
    await notesArea.setValue('Test note text')

    // Trigger form submit directly
    await wrapper.find('form').trigger('submit')

    // Check emitted event
    const emitted = wrapper.emitted('save')
    expect(emitted).toBeTruthy()
    expect(emitted!.length).toBe(1)

    const payload = emitted![0][0] as Record<string, unknown>
    expect(payload.symbol).toBe('SPY')
    expect(payload.notes).toBe('Test note text')
  })

  it('emits cancel when cancel button is clicked', async () => {
    const wrapper = mount(JournalEntryForm)
    // The cancel button is the first button with type="button" in the actions div
    const cancelBtn = wrapper
      .findAll('button[type="button"]')
      .find((b) => b.text().includes('Cancel'))
    expect(cancelBtn).toBeTruthy()
    await cancelBtn!.trigger('click')
    expect(wrapper.emitted('cancel')).toBeTruthy()
  })

  it('save button is disabled when symbol is empty', () => {
    const wrapper = mount(JournalEntryForm)
    const saveBtn = wrapper.find('[data-testid="journal-save-btn"]')
    expect((saveBtn.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('save button is enabled when symbol is filled', async () => {
    const wrapper = mount(JournalEntryForm)
    const symbolInput = wrapper.find('[data-testid="journal-symbol"]')
    await symbolInput.setValue('MSFT')
    const saveBtn = wrapper.find('[data-testid="journal-save-btn"]')
    expect((saveBtn.element as HTMLButtonElement).disabled).toBe(false)
  })

  it('shows saving state when saving prop is true', () => {
    const wrapper = mount(JournalEntryForm, {
      props: { saving: true },
    })
    const saveBtn = wrapper.find('[data-testid="journal-save-btn"]')
    expect(saveBtn.text()).toContain('Saving...')
    expect((saveBtn.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('updates checklist score when checkboxes are clicked', async () => {
    const wrapper = mount(JournalEntryForm)

    // Check phase_confirmed checkbox
    const phaseCheckbox = wrapper
      .find('[data-testid="check-phase"]')
      .find('input[type="checkbox"]')
    await phaseCheckbox.setValue(true)

    const score = wrapper.find('[data-testid="checklist-score"]')
    expect(score.text()).toContain('1/4')
  })
})
