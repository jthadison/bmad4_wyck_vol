<!--
Tutorial View Component (Story 11.8b - Task 8)

Purpose:
--------
Displays a grid of available tutorials with filtering by difficulty.
Shows tutorial cards with metadata and progress indicators.

Features:
---------
- Difficulty filter (ALL, BEGINNER, INTERMEDIATE, ADVANCED)
- Tutorial cards with title, description, duration, tags
- Progress indicators from localStorage
- Click to launch TutorialWalkthrough
- Responsive grid layout

Integration:
-----------
- Uses useTutorialStore for data and state
- Routes to /tutorials/:slug for walkthrough
- Displays progress from localStorage

Author: Story 11.8b (Task 8)
-->

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  useTutorialStore,
  type Tutorial,
  type TutorialProgress,
} from '@/stores/tutorialStore'
import Card from 'primevue/card'
import Button from 'primevue/button'
import Dropdown from 'primevue/dropdown'
import Tag from 'primevue/tag'
import ProgressBar from 'primevue/progressbar'
import Message from 'primevue/message'

const router = useRouter()
const tutorialStore = useTutorialStore()

// State
const selectedDifficulty = ref<string>('ALL')
const progressMap = ref<Map<string, TutorialProgress>>(new Map())

// Computed
const filteredTutorials = computed(() => {
  return tutorialStore.getTutorialsByDifficulty(selectedDifficulty.value)
})

const difficultyOptions = [
  { label: 'All Tutorials', value: 'ALL' },
  { label: 'Beginner', value: 'BEGINNER' },
  { label: 'Intermediate', value: 'INTERMEDIATE' },
  { label: 'Advanced', value: 'ADVANCED' },
]

// Methods
const getTutorialProgress = (slug: string): TutorialProgress | undefined => {
  return progressMap.value.get(slug)
}

const getProgressPercentage = (tutorial: Tutorial): number => {
  const progress = getTutorialProgress(tutorial.slug)
  if (!progress) return 0
  return Math.round(
    (progress.completedSteps.length / tutorial.steps.length) * 100
  )
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

const startTutorial = (tutorial: Tutorial) => {
  router.push({ name: 'tutorial-walkthrough', params: { slug: tutorial.slug } })
}

const formatDuration = (minutes: number): string => {
  if (minutes < 60) {
    return `${minutes} min`
  }
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`
}

// Lifecycle
onMounted(async () => {
  await tutorialStore.fetchTutorials()
  progressMap.value = tutorialStore.getAllProgress()
})
</script>

<template>
  <div class="tutorial-view">
    <!-- Header -->
    <div class="tutorial-header">
      <div>
        <h1 class="tutorial-title">Interactive Tutorials</h1>
        <p class="tutorial-subtitle">
          Step-by-step guides to master Wyckoff trading
        </p>
      </div>

      <!-- Difficulty Filter -->
      <div class="filter-section">
        <label for="difficulty-filter" class="filter-label"
          >Filter by Difficulty:</label
        >
        <Dropdown
          id="difficulty-filter"
          v-model="selectedDifficulty"
          :options="difficultyOptions"
          option-label="label"
          option-value="value"
          placeholder="Select Difficulty"
          class="difficulty-dropdown"
        />
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="tutorialStore.isLoading" class="loading-state">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
      <p>Loading tutorials...</p>
    </div>

    <!-- Error State -->
    <Message v-else-if="tutorialStore.error" severity="error" :closable="false">
      {{ tutorialStore.error }}
    </Message>

    <!-- Empty State -->
    <Message
      v-else-if="filteredTutorials.length === 0"
      severity="info"
      :closable="false"
      class="empty-state"
    >
      No tutorials found for the selected difficulty level.
    </Message>

    <!-- Tutorial Grid -->
    <div v-else class="tutorial-grid">
      <Card
        v-for="tutorial in filteredTutorials"
        :key="tutorial.id"
        class="tutorial-card"
      >
        <template #header>
          <div class="card-header">
            <Tag
              :value="tutorial.difficulty"
              :severity="getDifficultySeverity(tutorial.difficulty)"
              class="difficulty-tag"
            />
            <span class="duration">
              <i class="pi pi-clock"></i>
              {{ formatDuration(tutorial.estimated_time_minutes) }}
            </span>
          </div>
        </template>

        <template #title>
          <h3 class="card-title">{{ tutorial.title }}</h3>
        </template>

        <template #content>
          <p class="card-description">{{ tutorial.description }}</p>

          <!-- Tags -->
          <div v-if="tutorial.tags.length > 0" class="tags-section">
            <Tag
              v-for="tag in tutorial.tags.slice(0, 3)"
              :key="tag"
              :value="tag"
              severity="secondary"
              class="tag"
            />
            <span v-if="tutorial.tags.length > 3" class="more-tags">
              +{{ tutorial.tags.length - 3 }} more
            </span>
          </div>

          <!-- Progress -->
          <div
            v-if="getProgressPercentage(tutorial) > 0"
            class="progress-section"
          >
            <div class="progress-header">
              <span class="progress-label">Progress</span>
              <span class="progress-value"
                >{{ getProgressPercentage(tutorial) }}%</span
              >
            </div>
            <ProgressBar
              :value="getProgressPercentage(tutorial)"
              :show-value="false"
            />
          </div>

          <!-- Steps Info -->
          <div class="steps-info">
            <i class="pi pi-list"></i>
            <span>{{ tutorial.steps.length }} steps</span>
          </div>
        </template>

        <template #footer>
          <Button
            :label="
              getProgressPercentage(tutorial) > 0
                ? 'Continue Tutorial'
                : 'Start Tutorial'
            "
            :icon="
              getProgressPercentage(tutorial) > 0
                ? 'pi pi-play'
                : 'pi pi-arrow-right'
            "
            class="start-button"
            @click="startTutorial(tutorial)"
          />
        </template>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.tutorial-view {
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
}

.tutorial-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 2rem;
  flex-wrap: wrap;
  gap: 1.5rem;
}

.tutorial-title {
  font-size: 2rem;
  font-weight: 600;
  margin: 0 0 0.5rem 0;
  color: var(--primary-color);
}

.tutorial-subtitle {
  font-size: 1.1rem;
  color: var(--text-color-secondary);
  margin: 0;
}

.filter-section {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.filter-label {
  font-weight: 500;
  color: var(--text-color);
}

.difficulty-dropdown {
  min-width: 200px;
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

.empty-state {
  margin-top: 2rem;
}

.tutorial-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1.5rem;
  margin-top: 2rem;
}

.tutorial-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  transition:
    transform 0.2s,
    box-shadow 0.2s;
}

.tutorial-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: var(--surface-ground);
}

.difficulty-tag {
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.75rem;
}

.duration {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-color-secondary);
  font-size: 0.9rem;
}

.card-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0 0 1rem 0;
  color: var(--text-color);
}

.card-description {
  color: var(--text-color-secondary);
  line-height: 1.6;
  margin-bottom: 1rem;
  min-height: 3rem;
}

.tags-section {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
  align-items: center;
}

.tag {
  font-size: 0.75rem;
}

.more-tags {
  font-size: 0.75rem;
  color: var(--text-color-secondary);
  font-style: italic;
}

.progress-section {
  margin-bottom: 1rem;
  padding: 0.75rem;
  background: var(--surface-ground);
  border-radius: 6px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.progress-label {
  font-weight: 500;
  font-size: 0.9rem;
  color: var(--text-color-secondary);
}

.progress-value {
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--primary-color);
}

.steps-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-color-secondary);
  font-size: 0.9rem;
  margin-top: 1rem;
}

.start-button {
  width: 100%;
}

/* Responsive */
@media (max-width: 768px) {
  .tutorial-view {
    padding: 1rem;
  }

  .tutorial-header {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-section {
    flex-direction: column;
    align-items: stretch;
  }

  .difficulty-dropdown {
    width: 100%;
  }

  .tutorial-grid {
    grid-template-columns: 1fr;
  }
}
</style>
