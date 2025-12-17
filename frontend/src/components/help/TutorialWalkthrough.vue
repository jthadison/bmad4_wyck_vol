<!--
Tutorial Walkthrough Component (Story 11.8b - Task 9)

Purpose:
--------
Interactive step-by-step tutorial walkthrough with progress tracking.
Displays tutorial steps with navigation, action prompts, and completion tracking.

Features:
---------
- Step-by-step navigation with progress indicator
- Markdown rendering for step content
- Action prompts and UI highlighting (if applicable)
- Completion tracking with localStorage persistence
- Sidebar with step list and completion checkmarks
- Responsive layout

Integration:
-----------
- Uses useTutorialStore for data and state management
- Receives :slug param from route
- Saves progress to localStorage on each step completion
- Calls backend API on tutorial completion

Author: Story 11.8b (Task 9)
-->

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTutorialStore } from '@/stores/tutorialStore'
import Card from 'primevue/card'
import Button from 'primevue/button'
import Divider from 'primevue/divider'
import ProgressBar from 'primevue/progressbar'
import Checkbox from 'primevue/checkbox'
import Message from 'primevue/message'
import Sidebar from 'primevue/sidebar'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import { useToast } from 'primevue/usetoast'

const route = useRoute()
const router = useRouter()
const tutorialStore = useTutorialStore()
const toast = useToast()

// State
const sidebarVisible = ref(false)
const showCompletionDialog = ref(false)
const highlightedElement = ref<HTMLElement | null>(null)

// Computed
const tutorial = computed(() => tutorialStore.currentTutorial)
const currentStepData = computed(() => tutorialStore.currentStepData)
const currentStepIndex = computed(() => tutorialStore.currentStep)
const progressPercentage = computed(() => tutorialStore.progressPercentage)
const isStepCompleted = computed(() => tutorialStore.isCurrentStepCompleted)
const canAdvance = computed(() => tutorialStore.canAdvance)
const canGoBack = computed(() => tutorialStore.canGoBack)
const isFinalStep = computed(
  () =>
    tutorial.value && currentStepIndex.value === tutorial.value.steps.length - 1
)

// Methods
const toggleStepCompletion = () => {
  if (isStepCompleted.value) {
    tutorialStore.markStepIncomplete(currentStepIndex.value)
  } else {
    tutorialStore.markStepCompleted(currentStepIndex.value)
  }
}

const nextStep = () => {
  if (canAdvance.value) {
    tutorialStore.nextStep()
    scrollToTop()
    applyHighlight()
  }
}

const previousStep = () => {
  if (canGoBack.value) {
    tutorialStore.previousStep()
    scrollToTop()
    applyHighlight()
  }
}

const goToStep = (stepIndex: number) => {
  tutorialStore.goToStep(stepIndex)
  sidebarVisible.value = false
  scrollToTop()
  applyHighlight()
}

const completeTutorial = async () => {
  await tutorialStore.completeTutorial()
  showCompletionDialog.value = true

  toast.add({
    severity: 'success',
    summary: 'Tutorial Completed!',
    detail: `Congratulations on completing "${tutorial.value?.title}"`,
    life: 5000,
  })
}

const resetTutorial = () => {
  tutorialStore.resetTutorial()
  scrollToTop()
  applyHighlight()

  toast.add({
    severity: 'info',
    summary: 'Tutorial Reset',
    detail: 'Progress has been cleared. Start from Step 1.',
    life: 3000,
  })
}

const exitTutorial = () => {
  tutorialStore.clearCurrentTutorial()
  router.push({ name: 'tutorials' })
}

const scrollToTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const applyHighlight = () => {
  // Clear previous highlight
  if (highlightedElement.value) {
    highlightedElement.value.classList.remove('tutorial-highlight')
    highlightedElement.value = null
  }

  // Apply new highlight if ui_highlight is present
  if (currentStepData.value?.ui_highlight) {
    const selector = currentStepData.value.ui_highlight
    try {
      const element = document.querySelector(selector) as HTMLElement
      if (element) {
        element.classList.add('tutorial-highlight')
        highlightedElement.value = element
        element.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    } catch (e) {
      console.warn(`Invalid UI highlight selector: ${selector}`, e)
    }
  }
}

const isStepComplete = (stepIndex: number): boolean => {
  return tutorialStore.completedSteps.has(stepIndex)
}

const getDifficultySeverity = (
  difficulty: string
):
  | 'success'
  | 'info'
  | 'warn'
  | 'danger'
  | 'secondary'
  | 'contrast'
  | undefined => {
  switch (difficulty) {
    case 'BEGINNER':
      return 'success'
    case 'INTERMEDIATE':
      return 'info'
    case 'ADVANCED':
      return 'warn'
    default:
      return 'secondary'
  }
}

// Lifecycle
onMounted(async () => {
  const slug = route.params.slug as string
  if (!slug) {
    router.push({ name: 'tutorials' })
    return
  }

  try {
    await tutorialStore.fetchTutorialBySlug(slug)
    applyHighlight()
  } catch (e) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load tutorial',
      life: 5000,
    })
    router.push({ name: 'tutorials' })
  }
})

onBeforeUnmount(() => {
  // Clean up highlight
  if (highlightedElement.value) {
    highlightedElement.value.classList.remove('tutorial-highlight')
  }
})

// Watch for step changes to apply highlights
watch(currentStepIndex, () => {
  applyHighlight()
})
</script>

<template>
  <div v-if="tutorial" class="tutorial-walkthrough">
    <!-- Sidebar with Step List -->
    <Sidebar
      v-model:visible="sidebarVisible"
      position="left"
      class="steps-sidebar"
    >
      <template #header>
        <h3 class="sidebar-title">Tutorial Steps</h3>
      </template>

      <div class="step-list">
        <div
          v-for="(step, index) in tutorial.steps"
          :key="index"
          :class="[
            'step-item',
            {
              active: index === currentStepIndex,
              completed: isStepComplete(index),
            },
          ]"
          @click="goToStep(index)"
        >
          <div class="step-number">
            <i v-if="isStepComplete(index)" class="pi pi-check-circle"></i>
            <span v-else>{{ index + 1 }}</span>
          </div>
          <span class="step-title">{{ step.title }}</span>
        </div>
      </div>
    </Sidebar>

    <!-- Main Content -->
    <div class="walkthrough-content">
      <!-- Header -->
      <div class="walkthrough-header">
        <div class="header-left">
          <Button
            icon="pi pi-arrow-left"
            text
            rounded
            class="back-button"
            aria-label="Back to tutorials"
            @click="exitTutorial"
          />
          <div>
            <h1 class="tutorial-title">{{ tutorial.title }}</h1>
            <div class="tutorial-meta">
              <Tag
                :value="tutorial.difficulty"
                :severity="getDifficultySeverity(tutorial.difficulty)"
              />
              <span class="duration">
                <i class="pi pi-clock"></i>
                {{ tutorial.estimated_time_minutes }} min
              </span>
            </div>
          </div>
        </div>

        <div class="header-actions">
          <Button
            label="Steps"
            icon="pi pi-list"
            outlined
            class="steps-button"
            @click="sidebarVisible = true"
          />
          <Button
            label="Reset"
            icon="pi pi-refresh"
            outlined
            severity="secondary"
            @click="resetTutorial"
          />
        </div>
      </div>

      <!-- Progress Bar -->
      <div class="progress-section">
        <div class="progress-header">
          <span class="progress-label">
            Step {{ currentStepIndex + 1 }} of {{ tutorial.steps.length }}
          </span>
          <span class="progress-value">{{ progressPercentage }}% Complete</span>
        </div>
        <ProgressBar :value="progressPercentage" :show-value="false" />
      </div>

      <!-- Step Content -->
      <Card v-if="currentStepData" class="step-card">
        <template #title>
          <div class="step-header">
            <h2 class="step-title">
              <span class="step-number-badge">{{
                currentStepData.step_number
              }}</span>
              {{ currentStepData.title }}
            </h2>
            <Checkbox
              v-model="tutorialStore.completedSteps"
              :value="currentStepIndex"
              binary
              class="completion-checkbox"
              @update:model-value="toggleStepCompletion"
            />
          </div>
        </template>

        <template #content>
          <!-- Action Required Notice -->
          <Message
            v-if="currentStepData.action_required"
            severity="info"
            :closable="false"
            class="action-message"
          >
            <template #icon>
              <i class="pi pi-hand-point-right"></i>
            </template>
            <strong>Action Required:</strong>
            {{ currentStepData.action_required }}
          </Message>

          <!-- Step Content (HTML) -->
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div class="step-content" v-html="currentStepData.content_html"></div>

          <Divider />

          <!-- Navigation -->
          <div class="step-navigation">
            <Button
              label="Previous"
              icon="pi pi-arrow-left"
              outlined
              :disabled="!canGoBack"
              @click="previousStep"
            />

            <div class="completion-toggle">
              <Checkbox
                v-model="tutorialStore.completedSteps"
                :value="currentStepIndex"
                binary
                input-id="step-complete"
                @update:model-value="toggleStepCompletion"
              />
              <label for="step-complete" class="completion-label"
                >Mark as complete</label
              >
            </div>

            <Button
              v-if="!isFinalStep"
              label="Next"
              icon="pi pi-arrow-right"
              icon-pos="right"
              :disabled="!canAdvance"
              @click="nextStep"
            />

            <Button
              v-else
              label="Complete Tutorial"
              icon="pi pi-check"
              icon-pos="right"
              severity="success"
              :disabled="!tutorialStore.isTutorialCompleted"
              @click="completeTutorial"
            />
          </div>
        </template>
      </Card>

      <!-- Loading State -->
      <div v-else-if="tutorialStore.isLoading" class="loading-state">
        <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
        <p>Loading tutorial...</p>
      </div>

      <!-- Error State -->
      <Message
        v-else-if="tutorialStore.error"
        severity="error"
        :closable="false"
      >
        {{ tutorialStore.error }}
      </Message>
    </div>

    <!-- Completion Dialog -->
    <Dialog
      v-model:visible="showCompletionDialog"
      header="Tutorial Completed!"
      :modal="true"
      :closable="true"
      class="completion-dialog"
    >
      <div class="completion-content">
        <i class="pi pi-check-circle completion-icon"></i>
        <p class="completion-message">
          Congratulations! You've completed <strong>{{ tutorial.title }}</strong
          >.
        </p>
        <p class="completion-description">
          You can now apply what you've learned to improve your trading
          strategy.
        </p>
      </div>

      <template #footer>
        <Button label="View More Tutorials" outlined @click="exitTutorial" />
        <Button
          label="Restart Tutorial"
          severity="secondary"
          @click="resetTutorial"
        />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.tutorial-walkthrough {
  min-height: 100vh;
  background: var(--surface-ground);
}

.walkthrough-content {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem;
}

.walkthrough-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 2rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.header-left {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
}

.back-button {
  margin-top: 0.25rem;
}

.tutorial-title {
  font-size: 1.75rem;
  font-weight: 600;
  margin: 0 0 0.5rem 0;
  color: var(--text-color);
}

.tutorial-meta {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.duration {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-color-secondary);
}

.header-actions {
  display: flex;
  gap: 0.75rem;
}

.progress-section {
  margin-bottom: 2rem;
  padding: 1rem;
  background: var(--surface-card);
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.progress-label {
  font-weight: 500;
  color: var(--text-color);
}

.progress-value {
  font-weight: 600;
  color: var(--primary-color);
}

.step-card {
  margin-bottom: 2rem;
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.step-title {
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.step-number-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  background: var(--primary-color);
  color: white;
  border-radius: 50%;
  font-size: 1rem;
  font-weight: 700;
}

.action-message {
  margin-bottom: 1.5rem;
}

.step-content {
  line-height: 1.8;
  color: var(--text-color);
}

.step-content :deep(h1),
.step-content :deep(h2),
.step-content :deep(h3) {
  margin-top: 1.5rem;
  margin-bottom: 1rem;
  font-weight: 600;
}

.step-content :deep(p) {
  margin-bottom: 1rem;
}

.step-content :deep(ul),
.step-content :deep(ol) {
  margin-bottom: 1rem;
  padding-left: 1.5rem;
}

.step-content :deep(code) {
  background: var(--surface-ground);
  padding: 0.125rem 0.375rem;
  border-radius: 4px;
  font-family: monospace;
}

.step-content :deep(pre) {
  background: var(--surface-ground);
  padding: 1rem;
  border-radius: 6px;
  overflow-x: auto;
}

.step-navigation {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-top: 2rem;
}

.completion-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.completion-label {
  cursor: pointer;
  user-select: none;
  font-weight: 500;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  gap: 1rem;
  color: var(--text-color-secondary);
}

/* Sidebar */
.steps-sidebar {
  width: 320px;
}

.sidebar-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
}

.step-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.step-item:hover {
  background: var(--surface-hover);
}

.step-item.active {
  background: var(--primary-color);
  color: white;
}

.step-item.completed .step-number {
  color: var(--green-500);
}

.step-number {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  font-weight: 600;
  flex-shrink: 0;
}

.step-item.active .step-number {
  color: white;
}

.step-title {
  font-size: 0.9rem;
  line-height: 1.4;
}

/* Completion Dialog */
.completion-dialog {
  max-width: 500px;
}

.completion-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 2rem 1rem;
}

.completion-icon {
  font-size: 4rem;
  color: var(--green-500);
  margin-bottom: 1rem;
}

.completion-message {
  font-size: 1.1rem;
  margin-bottom: 0.75rem;
}

.completion-description {
  color: var(--text-color-secondary);
  margin-bottom: 0;
}

/* UI Highlight (applied dynamically via JS) */
:global(.tutorial-highlight) {
  outline: 3px solid var(--primary-color);
  outline-offset: 4px;
  border-radius: 4px;
  animation: pulse-highlight 2s infinite;
}

@keyframes pulse-highlight {
  0%,
  100% {
    outline-color: var(--primary-color);
  }
  50% {
    outline-color: var(--primary-color-hover);
  }
}

/* Responsive */
@media (max-width: 768px) {
  .walkthrough-content {
    padding: 1rem;
  }

  .walkthrough-header {
    flex-direction: column;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .tutorial-title {
    font-size: 1.5rem;
  }

  .step-navigation {
    flex-wrap: wrap;
  }

  .steps-sidebar {
    width: 280px;
  }
}
</style>
