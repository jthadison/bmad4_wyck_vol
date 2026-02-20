/**
 * Journal Service - API client for Trade Journal endpoints
 *
 * Feature P2-8 (Trade Journal)
 */

import { apiClient } from './api'

export interface WyckoffChecklist {
  phase_confirmed: boolean
  volume_confirmed: boolean
  creek_identified: boolean
  pattern_confirmed: boolean
}

export interface JournalEntryCreate {
  symbol: string
  entry_type: 'pre_trade' | 'post_trade' | 'observation'
  notes?: string | null
  campaign_id?: string | null
  signal_id?: string | null
  emotional_state?:
    | 'confident'
    | 'uncertain'
    | 'fomo'
    | 'disciplined'
    | 'neutral'
    | null
  wyckoff_checklist?: WyckoffChecklist | null
}

export interface JournalEntryUpdate {
  symbol?: string
  entry_type?: 'pre_trade' | 'post_trade' | 'observation'
  notes?: string | null
  emotional_state?:
    | 'confident'
    | 'uncertain'
    | 'fomo'
    | 'disciplined'
    | 'neutral'
    | null
  wyckoff_checklist?: WyckoffChecklist | null
}

export interface JournalEntry {
  id: string
  user_id: string
  campaign_id: string | null
  signal_id: string | null
  symbol: string
  entry_type: 'pre_trade' | 'post_trade' | 'observation'
  notes: string | null
  emotional_state: string | null
  wyckoff_checklist: WyckoffChecklist | null
  checklist_score: number
  created_at: string
  updated_at: string
}

export interface JournalListResponse {
  data: JournalEntry[]
  pagination: {
    returned_count: number
    total_count: number
    limit: number
    offset: number
    has_more: boolean
  }
}

export interface JournalListParams {
  symbol?: string
  entry_type?: string
  limit?: number
  offset?: number
}

const journalService = {
  async createEntry(payload: JournalEntryCreate): Promise<JournalEntry> {
    return apiClient.post<JournalEntry>('/journal', payload)
  },

  async listEntries(
    params: JournalListParams = {}
  ): Promise<JournalListResponse> {
    return apiClient.get<JournalListResponse>(
      '/journal',
      params as Record<string, unknown>
    )
  },

  async getEntry(id: string): Promise<JournalEntry> {
    return apiClient.get<JournalEntry>(`/journal/${id}`)
  },

  async updateEntry(
    id: string,
    payload: JournalEntryUpdate
  ): Promise<JournalEntry> {
    return apiClient.put<JournalEntry>(`/journal/${id}`, payload)
  },

  async deleteEntry(id: string): Promise<void> {
    return apiClient.delete<void>(`/journal/${id}`)
  },

  async getEntriesForCampaign(campaignId: string): Promise<JournalEntry[]> {
    return apiClient.get<JournalEntry[]>(`/journal/campaign/${campaignId}`)
  },
}

export default journalService
