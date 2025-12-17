<template>
  <div class="article-view">
    <!-- Loading State -->
    <div v-if="helpStore.isLoading" class="loading-state">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
      <p>Loading article...</p>
    </div>

    <!-- Error State -->
    <Message v-else-if="helpStore.error" severity="error" :closable="false">
      {{ helpStore.error }}
    </Message>

    <!-- Article Content -->
    <div v-else-if="helpStore.currentArticle" class="article-content">
      <h1 class="article-title">{{ helpStore.currentArticle.title }}</h1>

      <div class="article-meta">
        <Tag :value="helpStore.currentArticle.category" severity="info" />
        <span class="article-date">
          Last updated: {{ formatDate(helpStore.currentArticle.last_updated) }}
        </span>
      </div>

      <!-- Rendered HTML Content -->
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div
        class="article-body"
        v-html="helpStore.currentArticle.content_html"
      ></div>

      <!-- Article Tags -->
      <div v-if="helpStore.currentArticle.tags.length > 0" class="article-tags">
        <h4>Tags:</h4>
        <Tag
          v-for="tag in helpStore.currentArticle.tags"
          :key="tag"
          :value="tag"
          severity="secondary"
          class="tag-item"
        />
      </div>

      <!-- Feedback Section -->
      <div class="article-feedback">
        <Divider />
        <div v-if="!feedbackSubmitted" class="feedback-prompt">
          <h3>Was this article helpful?</h3>
          <div class="feedback-buttons">
            <Button
              icon="pi pi-thumbs-up"
              label="Yes"
              class="p-button-success"
              @click="submitFeedback(true)"
            />
            <Button
              icon="pi pi-thumbs-down"
              label="No"
              class="p-button-danger"
              @click="showCommentInput = true"
            />
          </div>

          <!-- Comment Input -->
          <div v-if="showCommentInput" class="comment-section">
            <Textarea
              v-model="feedbackComment"
              placeholder="How can we improve this article? (optional)"
              :auto-resize="true"
              rows="3"
              class="w-full"
            />
            <div class="comment-actions">
              <Button label="Submit" @click="submitFeedback(false)" />
              <Button
                label="Cancel"
                class="p-button-text"
                @click="showCommentInput = false"
              />
            </div>
          </div>
        </div>

        <!-- Thank You Message -->
        <div v-else class="feedback-thanks">
          <i class="pi pi-check-circle"></i>
          <span>Thank you for your feedback!</span>
        </div>
      </div>
    </div>

    <!-- Not Found -->
    <Message v-else severity="warn" :closable="false">
      Article not found.
    </Message>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useHelpStore } from '@/stores/helpStore'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import Textarea from 'primevue/textarea'
import Divider from 'primevue/divider'

/**
 * ArticleView Component (Story 11.8a - Task 15)
 *
 * Stub component for displaying full help articles.
 * Will be expanded in Story 11.8c.
 */

// Composables
const route = useRoute()
const helpStore = useHelpStore()

// State
const feedbackSubmitted = ref(false)
const showCommentInput = ref(false)
const feedbackComment = ref('')

// Methods
function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

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

// Lifecycle
onMounted(async () => {
  const slug = route.params.slug as string
  await helpStore.fetchArticle(slug)
})
</script>

<style scoped>
.article-view {
  max-width: 900px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  color: var(--text-color-secondary);
}

.article-content {
  padding: 2rem 0;
}

.article-title {
  margin-top: 0;
  margin-bottom: 1rem;
  color: var(--primary-color);
}

.article-meta {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 2rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--surface-border);
}

.article-date {
  color: var(--text-color-secondary);
  font-size: 0.875rem;
}

.article-body {
  line-height: 1.7;
  margin-bottom: 2rem;
}

.article-tags {
  margin-top: 2rem;
}

.article-tags h4 {
  margin-bottom: 0.75rem;
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-color-secondary);
}

.tag-item {
  margin-right: 0.5rem;
  margin-bottom: 0.5rem;
}

.article-feedback {
  margin-top: 3rem;
}

.feedback-prompt h3 {
  margin-bottom: 1rem;
}

.feedback-buttons {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
}

.comment-section {
  margin-top: 1rem;
}

.comment-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.feedback-thanks {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--green-500);
  font-weight: 600;
  font-size: 1.1rem;
}

.feedback-thanks i {
  font-size: 1.5rem;
}
</style>
