/**
 * Feedback Types (Story 10.7)
 *
 * TypeScript interfaces for trader feedback on rejection decisions.
 * These types correspond to Pydantic models in backend/src/models/feedback.py
 */

/**
 * Request body for submitting trader feedback on rejection decisions.
 */
export interface FeedbackSubmission {
  /** UUID of rejected signal */
  signal_id: string
  /** Type of feedback */
  feedback_type: 'positive' | 'review_request' | 'question'
  /** Optional explanation (required for review_request) */
  explanation?: string | null
  /** Submission timestamp (UTC ISO 8601) */
  timestamp: string
}

/**
 * API response after feedback submission.
 */
export interface FeedbackResponse {
  /** Unique feedback identifier */
  feedback_id: string
  /** Processing status */
  status: 'received' | 'queued_for_review'
  /** User-friendly confirmation message */
  message: string
}

/**
 * Database model for persisting trader feedback.
 */
export interface Feedback {
  /** Unique feedback identifier */
  id: string
  /** UUID of rejected signal */
  signal_id: string
  /** Type of feedback */
  feedback_type: 'positive' | 'review_request' | 'question'
  /** Optional explanation text */
  explanation?: string | null
  /** Submission timestamp (UTC) */
  timestamp: string
  /** Database record creation timestamp */
  created_at: string
  /** Whether feedback has been reviewed */
  processed: boolean
}
