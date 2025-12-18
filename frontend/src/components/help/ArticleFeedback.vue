<!--
Article Feedback Component (Story 11.8c - Task 2)

Purpose:
--------
Collects user feedback on help articles with thumbs up/down buttons.
Prevents duplicate submissions using localStorage tracking.

Features:
---------
- Thumbs up/down buttons (PrimeVue Button)
- Comment textarea for negative feedback (optional)
- localStorage duplicate prevention (feedback_${articleSlug})
- Thank you message after submission (PrimeVue Message)
- Disabled state after feedback submitted
- Submit comment button for thumbs down
- Character limit on comments (1000 chars)

Integration:
-----------
- Uses helpStore.submitFeedback(articleId, helpful, comment)
- Props: articleId (UUID), articleSlug (string)
- localStorage key pattern: feedback_${articleSlug}

Author: Story 11.8c (Task 2)
-->

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useHelpStore } from '@/stores/helpStore'
import Button from 'primevue/button'
import Textarea from 'primevue/textarea'
import Message from 'primevue/message'

interface Props {
  articleId: string
  articleSlug: string
}

const props = defineProps<Props>()

const helpStore = useHelpStore()

// State
const feedbackSubmitted = ref(false)
const showCommentBox = ref(false)
const comment = ref('')
const submitting = ref(false)
const showThankYou = ref(false)

// LocalStorage key
const feedbackKey = `feedback_${props.articleSlug}`

// Methods
const checkExistingFeedback = () => {
  try {
    const stored = localStorage.getItem(feedbackKey)
    if (stored) {
      const data = JSON.parse(stored)
      feedbackSubmitted.value = data.submitted === true
      showThankYou.value = feedbackSubmitted.value
    }
  } catch (error) {
    console.error('Error reading feedback from localStorage:', error)
  }
}

const saveFeedbackToLocalStorage = (helpful: boolean) => {
  try {
    const data = {
      submitted: true,
      helpful,
      timestamp: new Date().toISOString(),
      articleId: props.articleId,
    }
    localStorage.setItem(feedbackKey, JSON.stringify(data))
  } catch (error) {
    console.error('Error saving feedback to localStorage:', error)
  }
}

const handleThumbsUp = async () => {
  if (feedbackSubmitted.value || submitting.value) return

  submitting.value = true

  try {
    const success = await helpStore.submitFeedback(props.articleId, true)

    if (success) {
      feedbackSubmitted.value = true
      showThankYou.value = true
      saveFeedbackToLocalStorage(true)
    }
  } catch (error) {
    console.error('Error submitting positive feedback:', error)
  } finally {
    submitting.value = false
  }
}

const handleThumbsDown = () => {
  if (feedbackSubmitted.value || submitting.value) return
  showCommentBox.value = true
}

const submitNegativeFeedback = async () => {
  if (feedbackSubmitted.value || submitting.value) return

  submitting.value = true

  try {
    const commentText = comment.value.trim() || undefined
    const success = await helpStore.submitFeedback(
      props.articleId,
      false,
      commentText
    )

    if (success) {
      feedbackSubmitted.value = true
      showThankYou.value = true
      showCommentBox.value = false
      saveFeedbackToLocalStorage(false)
    }
  } catch (error) {
    console.error('Error submitting negative feedback:', error)
  } finally {
    submitting.value = false
  }
}

const cancelComment = () => {
  showCommentBox.value = false
  comment.value = ''
}

// Lifecycle
onMounted(() => {
  checkExistingFeedback()
})
</script>

<template>
  <div class="article-feedback">
    <!-- Thank You Message (after submission) -->
    <Message
      v-if="showThankYou"
      severity="success"
      :closable="false"
      class="thank-you-message"
    >
      <div class="thank-you-content">
        <i class="pi pi-check-circle"></i>
        <span>Thanks for your feedback!</span>
      </div>
    </Message>

    <!-- Already Submitted Notice -->
    <div v-else-if="feedbackSubmitted" class="already-submitted">
      <i class="pi pi-info-circle"></i>
      <span>You've already provided feedback for this article</span>
    </div>

    <!-- Feedback Buttons -->
    <div v-else class="feedback-controls">
      <span class="feedback-label">Was this helpful?</span>

      <div class="button-group">
        <Button
          icon="pi pi-thumbs-up"
          label="Yes"
          severity="success"
          outlined
          size="small"
          :disabled="submitting"
          :loading="submitting"
          class="thumbs-up-btn"
          @click="handleThumbsUp"
        />

        <Button
          icon="pi pi-thumbs-down"
          label="No"
          severity="danger"
          outlined
          size="small"
          :disabled="submitting"
          class="thumbs-down-btn"
          @click="handleThumbsDown"
        />
      </div>
    </div>

    <!-- Comment Box (shown after thumbs down) -->
    <div v-if="showCommentBox && !feedbackSubmitted" class="comment-section">
      <label for="feedback-comment" class="comment-label">
        How can we improve this article? (optional)
      </label>
      <Textarea
        id="feedback-comment"
        v-model="comment"
        rows="4"
        placeholder="Share your thoughts to help us improve..."
        :maxlength="1000"
        class="comment-textarea"
      />
      <div class="comment-actions">
        <span class="char-count">{{ comment.length }} / 1000</span>
        <div class="action-buttons">
          <Button
            label="Cancel"
            severity="secondary"
            outlined
            size="small"
            :disabled="submitting"
            @click="cancelComment"
          />
          <Button
            label="Submit Feedback"
            severity="primary"
            size="small"
            :disabled="submitting"
            :loading="submitting"
            @click="submitNegativeFeedback"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.article-feedback {
  padding: 1rem;
  background-color: var(--surface-ground);
  border-radius: 6px;
  border: 1px solid var(--surface-border);
}

.thank-you-message {
  margin: 0;
}

.thank-you-content {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-weight: 500;
}

.thank-you-content i {
  font-size: 1.25rem;
}

.already-submitted {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--text-color-secondary);
  font-size: 0.95rem;
}

.already-submitted i {
  font-size: 1.125rem;
}

.feedback-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.feedback-label {
  font-weight: 500;
  font-size: 1rem;
  color: var(--text-color);
}

.button-group {
  display: flex;
  gap: 0.75rem;
}

.thumbs-up-btn,
.thumbs-down-btn {
  min-width: 90px;
}

.comment-section {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--surface-border);
}

.comment-label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  font-size: 0.95rem;
  color: var(--text-color);
}

.comment-textarea {
  width: 100%;
  margin-bottom: 0.5rem;
  font-family: inherit;
  resize: vertical;
}

.comment-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.char-count {
  font-size: 0.85rem;
  color: var(--text-color-secondary);
}

.action-buttons {
  display: flex;
  gap: 0.5rem;
}

/* Responsive */
@media (max-width: 768px) {
  .feedback-controls {
    flex-direction: column;
    align-items: flex-start;
  }

  .button-group {
    width: 100%;
  }

  .thumbs-up-btn,
  .thumbs-down-btn {
    flex: 1;
  }

  .comment-actions {
    flex-direction: column;
    align-items: flex-start;
  }

  .action-buttons {
    width: 100%;
  }

  .action-buttons button {
    flex: 1;
  }
}
</style>
