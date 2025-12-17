/**
 * Tutorial Store (Story 11.8b - Task 7)
 *
 * Purpose:
 * --------
 * Manages tutorial data, progress tracking, and state for the tutorial system.
 * Uses localStorage for progress persistence (MVP approach).
 *
 * State Management:
 * ----------------
 * - tutorials: List of all available tutorials
 * - currentTutorial: Currently active tutorial with steps
 * - currentStep: Index of current step in walkthrough
 * - completedSteps: Set of completed step indices
 * - progress: localStorage-backed progress tracking
 *
 * Integration:
 * -----------
 * - Used by TutorialView and TutorialWalkthrough components
 * - Persists progress to localStorage (key: tutorial-progress-{slug})
 * - Calls backend /tutorials API endpoints
 *
 * Author: Story 11.8b (Task 7)
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@/services/api'

export interface TutorialStep {
  step_number: number
  title: string
  content_markdown: string
  content_html: string
  action_required: string | null
  ui_highlight: string | null
}

export interface Tutorial {
  id: string
  slug: string
  title: string
  description: string
  difficulty: 'BEGINNER' | 'INTERMEDIATE' | 'ADVANCED'
  estimated_time_minutes: number
  steps: TutorialStep[]
  tags: string[]
  last_updated: string
  completion_count: number
}

export interface TutorialListResponse {
  tutorials: Tutorial[]
  total_count: number
}

export interface TutorialProgress {
  slug: string
  currentStep: number
  completedSteps: number[]
  completed: boolean
  lastAccessed: string
}

export const useTutorialStore = defineStore('tutorial', () => {
  // State
  const tutorials = ref<Tutorial[]>([])
  const currentTutorial = ref<Tutorial | null>(null)
  const currentStep = ref(0)
  const completedSteps = ref<Set<number>>(new Set())
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Cache timestamps
  const lastFetched = ref<number | null>(null)
  const CACHE_DURATION_MS = 24 * 60 * 60 * 1000 // 24 hours (tutorials are relatively static)

  // Computed
  const getTutorialsByDifficulty = computed(
    () => (difficulty: string | null) => {
      if (!difficulty || difficulty === 'ALL') {
        return tutorials.value
      }
      return tutorials.value.filter((t) => t.difficulty === difficulty)
    }
  )

  const currentStepData = computed(() => {
    if (
      !currentTutorial.value ||
      currentStep.value >= currentTutorial.value.steps.length
    ) {
      return null
    }
    return currentTutorial.value.steps[currentStep.value]
  })

  const isCurrentStepCompleted = computed(() => {
    return completedSteps.value.has(currentStep.value)
  })

  const canAdvance = computed(() => {
    return (
      currentTutorial.value &&
      currentStep.value < currentTutorial.value.steps.length - 1 &&
      isCurrentStepCompleted.value
    )
  })

  const canGoBack = computed(() => {
    return currentStep.value > 0
  })

  const isTutorialCompleted = computed(() => {
    if (!currentTutorial.value) return false
    return completedSteps.value.size === currentTutorial.value.steps.length
  })

  const progressPercentage = computed(() => {
    if (!currentTutorial.value) return 0
    return Math.round(
      (completedSteps.value.size / currentTutorial.value.steps.length) * 100
    )
  })

  // Actions
  const fetchTutorials = async (
    difficulty: string | null = null,
    limit = 50,
    offset = 0
  ) => {
    // Use cache if available and fresh
    const now = Date.now()
    if (
      lastFetched.value &&
      now - lastFetched.value < CACHE_DURATION_MS &&
      tutorials.value.length > 0
    ) {
      return
    }

    isLoading.value = true
    error.value = null

    try {
      const params: Record<string, unknown> = { limit, offset }
      if (difficulty && difficulty !== 'ALL') {
        params.difficulty = difficulty
      }

      const response = await apiClient.get<TutorialListResponse>(
        '/help/tutorials',
        params
      )
      tutorials.value = response.tutorials
      lastFetched.value = now
    } catch (e) {
      const errorMessage =
        e instanceof Error ? e.message : 'Failed to fetch tutorials'
      error.value = errorMessage
      console.error('Error fetching tutorials:', e)
    } finally {
      isLoading.value = false
    }
  }

  const fetchTutorialBySlug = async (slug: string) => {
    isLoading.value = true
    error.value = null

    try {
      const response = await apiClient.get<Tutorial>(`/help/tutorials/${slug}`)
      currentTutorial.value = response
      loadProgress(slug)
      return response
    } catch (e) {
      const errorMessage =
        e instanceof Error ? e.message : 'Failed to fetch tutorial'
      error.value = errorMessage
      console.error('Error fetching tutorial:', e)
      throw e
    } finally {
      isLoading.value = false
    }
  }

  const markStepCompleted = (stepIndex: number) => {
    completedSteps.value.add(stepIndex)
    if (currentTutorial.value) {
      saveProgress(currentTutorial.value.slug)
    }
  }

  const markStepIncomplete = (stepIndex: number) => {
    completedSteps.value.delete(stepIndex)
    if (currentTutorial.value) {
      saveProgress(currentTutorial.value.slug)
    }
  }

  const nextStep = () => {
    if (canAdvance.value) {
      currentStep.value++
      if (currentTutorial.value) {
        saveProgress(currentTutorial.value.slug)
      }
    }
  }

  const previousStep = () => {
    if (canGoBack.value) {
      currentStep.value--
      if (currentTutorial.value) {
        saveProgress(currentTutorial.value.slug)
      }
    }
  }

  const goToStep = (stepIndex: number) => {
    if (
      currentTutorial.value &&
      stepIndex >= 0 &&
      stepIndex < currentTutorial.value.steps.length
    ) {
      currentStep.value = stepIndex
      saveProgress(currentTutorial.value.slug)
    }
  }

  const completeTutorial = async () => {
    if (!currentTutorial.value) return

    // Mark all steps as completed
    currentTutorial.value.steps.forEach((_, index) => {
      completedSteps.value.add(index)
    })

    saveProgress(currentTutorial.value.slug)

    // Notify backend to increment completion count
    try {
      await apiClient.post(
        `/help/tutorials/${currentTutorial.value.slug}/complete`
      )
    } catch (e) {
      console.error('Error marking tutorial as complete:', e)
      // Don't throw - this is analytics, not critical
    }
  }

  const resetTutorial = () => {
    currentStep.value = 0
    completedSteps.value.clear()
    if (currentTutorial.value) {
      saveProgress(currentTutorial.value.slug)
    }
  }

  const clearCurrentTutorial = () => {
    currentTutorial.value = null
    currentStep.value = 0
    completedSteps.value.clear()
  }

  // localStorage Persistence
  const saveProgress = (slug: string) => {
    const progress: TutorialProgress = {
      slug,
      currentStep: currentStep.value,
      completedSteps: Array.from(completedSteps.value),
      completed: isTutorialCompleted.value,
      lastAccessed: new Date().toISOString(),
    }

    try {
      localStorage.setItem(
        `tutorial-progress-${slug}`,
        JSON.stringify(progress)
      )
    } catch (e) {
      console.error('Failed to save tutorial progress to localStorage:', e)
    }
  }

  const loadProgress = (slug: string) => {
    try {
      const stored = localStorage.getItem(`tutorial-progress-${slug}`)
      if (stored) {
        const progress: TutorialProgress = JSON.parse(stored)
        currentStep.value = progress.currentStep
        completedSteps.value = new Set(progress.completedSteps)
      } else {
        // No saved progress - start fresh
        currentStep.value = 0
        completedSteps.value.clear()
      }
    } catch (e) {
      console.error('Failed to load tutorial progress from localStorage:', e)
      currentStep.value = 0
      completedSteps.value.clear()
    }
  }

  const clearProgress = (slug: string) => {
    try {
      localStorage.removeItem(`tutorial-progress-${slug}`)
      currentStep.value = 0
      completedSteps.value.clear()
    } catch (e) {
      console.error('Failed to clear tutorial progress:', e)
    }
  }

  const getAllProgress = (): Map<string, TutorialProgress> => {
    const progressMap = new Map<string, TutorialProgress>()

    try {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key?.startsWith('tutorial-progress-')) {
          const value = localStorage.getItem(key)
          if (value) {
            const progress: TutorialProgress = JSON.parse(value)
            progressMap.set(progress.slug, progress)
          }
        }
      }
    } catch (e) {
      console.error('Failed to retrieve all progress:', e)
    }

    return progressMap
  }

  const clearCache = () => {
    lastFetched.value = null
    tutorials.value = []
  }

  return {
    // State
    tutorials,
    currentTutorial,
    currentStep,
    completedSteps,
    isLoading,
    error,

    // Computed
    getTutorialsByDifficulty,
    currentStepData,
    isCurrentStepCompleted,
    canAdvance,
    canGoBack,
    isTutorialCompleted,
    progressPercentage,

    // Actions
    fetchTutorials,
    fetchTutorialBySlug,
    markStepCompleted,
    markStepIncomplete,
    nextStep,
    previousStep,
    goToStep,
    completeTutorial,
    resetTutorial,
    clearCurrentTutorial,

    // Persistence
    saveProgress,
    loadProgress,
    clearProgress,
    getAllProgress,
    clearCache,
  }
})
