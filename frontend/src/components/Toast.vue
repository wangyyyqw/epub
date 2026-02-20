<script setup>
import { ref, onMounted, computed } from 'vue'

const props = defineProps({
  message: String,
  type: {
    type: String,
    default: 'info',
    validator: (value) => ['success', 'error', 'warning', 'info'].includes(value)
  },
  duration: {
    type: Number,
    default: 3000
  }
})

const emit = defineEmits(['close'])

const visible = ref(false)
const progress = ref(100)

const typeConfig = {
  success: {
    icon: 'M5 13l4 4L19 7',
    bgClass: 'bg-green-50 dark:bg-green-900/20',
    borderClass: 'border-green-200 dark:border-green-800/30',
    textClass: 'text-green-800 dark:text-green-200',
    iconClass: 'text-green-500 dark:text-green-400'
  },
  error: {
    icon: 'M6 18L18 6M6 6l12 12',
    bgClass: 'bg-red-50 dark:bg-red-900/20',
    borderClass: 'border-red-200 dark:border-red-800/30',
    textClass: 'text-red-800 dark:text-red-200',
    iconClass: 'text-red-500 dark:text-red-400'
  },
  warning: {
    icon: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
    bgClass: 'bg-amber-50 dark:bg-amber-900/20',
    borderClass: 'border-amber-200 dark:border-amber-800/30',
    textClass: 'text-amber-800 dark:text-amber-200',
    iconClass: 'text-amber-500 dark:text-amber-400'
  },
  info: {
    icon: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    bgClass: 'bg-blue-50 dark:bg-blue-900/20',
    borderClass: 'border-blue-200 dark:border-blue-800/30',
    textClass: 'text-blue-800 dark:text-blue-200',
    iconClass: 'text-blue-500 dark:text-blue-400'
  }
}

const currentType = computed(() => typeConfig[props.type])

onMounted(() => {
  visible.value = true
  
  const startTime = Date.now()
  const interval = setInterval(() => {
    const elapsed = Date.now() - startTime
    progress.value = Math.max(0, 100 - (elapsed / props.duration) * 100)
    
    if (progress.value <= 0) {
      clearInterval(interval)
      close()
    }
  }, 16)
})

const close = () => {
  visible.value = false
  setTimeout(() => emit('close'), 300)
}
</script>

<template>
  <Transition
    enter-active-class="transform ease-out duration-300 transition"
    enter-from-class="translate-y-2 opacity-0 sm:translate-y-0 sm:translate-x-2"
    enter-to-class="translate-y-0 opacity-100 sm:translate-x-0"
    leave-active-class="transition ease-in duration-100"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="visible"
      :class="[
        'pointer-events-auto w-full max-w-sm overflow-hidden rounded-lg shadow-lg ring-1 ring-black ring-opacity-5',
        currentType.bgClass,
        currentType.borderClass,
        'border'
      ]"
    >
      <div class="p-4">
        <div class="flex items-start">
          <div class="flex-shrink-0">
            <svg
              :class="['h-5 w-5', currentType.iconClass]"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              stroke-width="2"
            >
              <path stroke-linecap="round" stroke-linejoin="round" :d="currentType.icon" />
            </svg>
          </div>
          <div class="ml-3 w-0 flex-1 pt-0.5">
            <p :class="['text-sm font-medium', currentType.textClass]">{{ message }}</p>
          </div>
          <div class="ml-4 flex flex-shrink-0">
            <button
              @click="close"
              :class="[
                'inline-flex rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2',
                currentType.textClass,
                'hover:opacity-75'
              ]"
            >
              <span class="sr-only">关闭</span>
              <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>
        </div>
      </div>
      <div class="h-1 bg-black/5 dark:bg-white/5">
        <div
          class="h-full transition-all duration-100 ease-linear"
          :class="currentType.iconClass.replace('text-', 'bg-')"
          :style="{ width: progress + '%' }"
        ></div>
      </div>
    </div>
  </Transition>
</template>
