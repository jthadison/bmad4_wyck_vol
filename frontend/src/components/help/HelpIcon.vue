<template>
  <div class="help-icon-wrapper">
    <!-- Help Icon Button -->
    <Button
      v-tooltip.right="tooltipText || 'Click for help'"
      icon="pi pi-question-circle"
      class="p-button-rounded p-button-text p-button-sm help-icon-btn"
      aria-label="Help"
      @click="openHelpDialog"
    />

    <!-- Help Dialog -->
    <Dialog
      v-model:visible="dialogVisible"
      :header="articleTitle"
      :modal="true"
      :closable="true"
      :dismissable-mask="true"
      :draggable="false"
      class="help-dialog"
      :style="{ width: '50vw' }"
      @hide="onDialogHide"
    >
      <!-- Loading State -->
      <div v-if="helpStore.isLoading" class="dialog-loading">
        <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
        <p>Loading article...</p>
      </div>

      <!-- Error State -->
      <Message v-else-if="helpStore.error" severity="error" :closable="false">
        {{ helpStore.error }}
      </Message>

      <!-- Article Content -->
      <div v-else-if="helpStore.currentArticle" class="dialog-content">
        <!-- Rendered HTML Content -->
        <!-- eslint-disable-next-line vue/no-v-html -->
        <div
          class="article-html"
          v-html="helpStore.currentArticle.content_html"
        ></div>

        <!-- View Full Article Link -->
        <div class="full-article-link">
          <router-link
            :to="`/help/article/${articleSlug}`"
            class="view-full-link"
          >
            <i class="pi pi-external-link"></i>
            View full article
          </router-link>
        </div>
      </div>

      <!-- Dialog Footer: Feedback -->
      <template #footer>
        <div v-if="!feedbackSubmitted" class="feedback-section">
          <span class="feedback-label">Was this helpful?</span>
          <div class="feedback-buttons">
            <Button
              icon="pi pi-thumbs-up"
              label="Yes"
              class="p-button-success p-button-sm"
              :disabled="helpStore.isLoading"
              @click="submitFeedback(true)"
            />
            <Button
              icon="pi pi-thumbs-down"
              label="No"
              class="p-button-danger p-button-sm"
              :disabled="helpStore.isLoading"
              @click="showCommentInput = true"
            />
          </div>

          <!-- Optional Comment Input (shown on thumbs down) -->
          <div v-if="showCommentInput" class="comment-input">
            <Textarea
              v-model="feedbackComment"
              placeholder="How can we improve? (optional)"
              :auto-resize="true"
              rows="3"
              class="w-full"
            />
            <div class="comment-actions">
              <Button
                label="Submit"
                class="p-button-sm"
                :disabled="helpStore.isLoading"
                @click="submitFeedback(false)"
              />
              <Button
                label="Cancel"
                class="p-button-text p-button-sm"
                @click="showCommentInput = false"
              />
            </div>
          </div>
        </div>

        <!-- Thank You Message -->
        <div v-else class="feedback-thank-you">
          <i class="pi pi-check-circle"></i>
          Thanks for your feedback!
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useHelpStore } from '@/stores/helpStore'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Message from 'primevue/message'
import Textarea from 'primevue/textarea'

// Props
interface Props {
  articleSlug: string
  tooltipText?: string
  placement?: 'top' | 'bottom' | 'left' | 'right'
}

const props = withDefaults(defineProps<Props>(), {
  tooltipText: '',
  placement: 'right',
})

// Composables
const helpStore = useHelpStore()

// State
const dialogVisible = ref(false)
const feedbackSubmitted = ref(false)
const showCommentInput = ref(false)
const feedbackComment = ref('')

// Computed
const articleTitle = computed(() => {
  return helpStore.currentArticle?.title || 'Help'
})

// ============================================================================
// Methods
// ============================================================================

/**
 * Open the help dialog and fetch the article
 */
async function openHelpDialog() {
  dialogVisible.value = true
  feedbackSubmitted.value = false
  showCommentInput.value = false
  feedbackComment.value = ''

  // Fetch the article
  await helpStore.fetchArticle(props.articleSlug)
}

/**
 * Submit feedback for the article
 */
async function submitFeedback(helpful: boolean) {
  if (!helpStore.currentArticle) return

  const comment = feedbackComment.value.trim() || undefined

  const success = await helpStore.submitFeedback(
    helpStore.currentArticle.id,
    helpful,
    comment
  )

  if (success) {
    feedbackSubmitted.value = true
    showCommentInput.value = false
    feedbackComment.value = ''
  }
}

/**
 * Handle dialog hide event
 */
function onDialogHide() {
  // Reset feedback state when dialog is closed
  feedbackSubmitted.value = false
  showCommentInput.value = false
  feedbackComment.value = ''
}
</script>

<style scoped>
.help-icon-wrapper {
  display: inline-block;
}

.help-icon-btn {
  color: var(--primary-color);
}

.help-icon-btn:hover {
  color: var(--primary-color-hover);
}

/* Dialog Content */
.dialog-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  color: var(--text-color-secondary);
}

.dialog-content {
  max-height: 60vh;
  overflow-y: auto;
}

.article-html {
  line-height: 1.7;
  color: var(--text-color);
}

.article-html :deep(h1),
.article-html :deep(h2),
.article-html :deep(h3) {
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
  color: var(--text-color);
}

.article-html :deep(h1) {
  font-size: 1.75rem;
}

.article-html :deep(h2) {
  font-size: 1.5rem;
}

.article-html :deep(h3) {
  font-size: 1.25rem;
}

.article-html :deep(p) {
  margin-bottom: 1rem;
}

.article-html :deep(ul),
.article-html :deep(ol) {
  margin-bottom: 1rem;
  padding-left: 1.5rem;
}

.article-html :deep(li) {
  margin-bottom: 0.5rem;
}

.article-html :deep(code) {
  background-color: var(--surface-ground);
  padding: 0.125rem 0.25rem;
  border-radius: 3px;
  font-family: monospace;
  font-size: 0.9em;
}

.article-html :deep(pre) {
  background-color: var(--surface-ground);
  padding: 1rem;
  border-radius: 6px;
  overflow-x: auto;
  margin-bottom: 1rem;
}

.article-html :deep(pre code) {
  background-color: transparent;
  padding: 0;
}

.article-html :deep(a) {
  color: var(--primary-color);
  text-decoration: none;
}

.article-html :deep(a:hover) {
  text-decoration: underline;
}

.article-html :deep(blockquote) {
  border-left: 4px solid var(--primary-color);
  padding-left: 1rem;
  margin: 1rem 0;
  font-style: italic;
  color: var(--text-color-secondary);
}

.article-html :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1rem;
}

.article-html :deep(th),
.article-html :deep(td) {
  border: 1px solid var(--surface-border);
  padding: 0.75rem;
  text-align: left;
}

.article-html :deep(th) {
  background-color: var(--surface-ground);
  font-weight: 600;
}

/* Full Article Link */
.full-article-link {
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--surface-border);
}

.view-full-link {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--primary-color);
  text-decoration: none;
  font-weight: 500;
}

.view-full-link:hover {
  text-decoration: underline;
}

/* Feedback Section */
.feedback-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.feedback-label {
  font-weight: 600;
  color: var(--text-color);
}

.feedback-buttons {
  display: flex;
  gap: 0.75rem;
}

.comment-input {
  margin-top: 1rem;
}

.comment-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.feedback-thank-you {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--green-500);
  font-weight: 600;
}

.feedback-thank-you i {
  font-size: 1.5rem;
}

/* Responsive */
@media (max-width: 768px) {
  .help-dialog {
    width: 95vw !important;
  }

  .dialog-content {
    max-height: 50vh;
  }
}
</style>
