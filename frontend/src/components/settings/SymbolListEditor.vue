<template>
  <div class="symbol-list-editor">
    <label
      v-if="label"
      :for="inputId"
      class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
    >
      {{ label }}
    </label>
    <div class="flex flex-wrap gap-2 mb-2">
      <Chip
        v-for="symbol in symbols"
        :key="symbol"
        :label="symbol"
        removable
        @remove="removeSymbol(symbol)"
        class="bg-primary-100 dark:bg-primary-900 text-primary-800 dark:text-primary-100"
      />
      <span
        v-if="symbols.length === 0"
        class="text-sm text-gray-500 dark:text-gray-400 italic"
      >
        {{ emptyMessage }}
      </span>
    </div>
    <div class="flex gap-2">
      <InputText
        :id="inputId"
        v-model="newSymbol"
        :placeholder="placeholder"
        class="flex-1"
        @keyup.enter="addSymbol"
        :disabled="disabled"
      />
      <Button
        label="Add"
        icon="pi pi-plus"
        @click="addSymbol"
        :disabled="disabled || !newSymbol.trim()"
        size="small"
      />
    </div>
    <small v-if="helpText" class="text-gray-500 dark:text-gray-400 mt-1 block">
      {{ helpText }}
    </small>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import Chip from 'primevue/chip'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'

interface Props {
  modelValue: string[]
  label?: string
  placeholder?: string
  emptyMessage?: string
  helpText?: string
  disabled?: boolean
}

interface Emits {
  (e: 'update:modelValue', value: string[]): void
}

const props = withDefaults(defineProps<Props>(), {
  label: '',
  placeholder: 'Enter symbol...',
  emptyMessage: 'No symbols added',
  helpText: '',
  disabled: false,
})

const emit = defineEmits<Emits>()

const newSymbol = ref('')
const inputId = ref(
  `symbol-input-${Math.random().toString(36).substring(2, 9)}`
)

const symbols = computed(() => props.modelValue || [])

function addSymbol(): void {
  const symbol = newSymbol.value.trim().toUpperCase()
  if (symbol && !symbols.value.includes(symbol)) {
    emit('update:modelValue', [...symbols.value, symbol])
    newSymbol.value = ''
  }
}

function removeSymbol(symbol: string): void {
  emit(
    'update:modelValue',
    symbols.value.filter((s) => s !== symbol)
  )
}
</script>

<style scoped>
.symbol-list-editor {
  width: 100%;
}
</style>
