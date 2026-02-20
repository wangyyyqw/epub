<script setup>
import { ref, provide } from 'vue'
import Toast from './Toast.vue'

const toasts = ref([])
let toastId = 0

const show = (message, type = 'info', duration = 3000) => {
  const id = ++toastId
  toasts.value.push({ id, message, type, duration })
  
  setTimeout(() => remove(id), duration + 500)
  return id
}

const remove = (id) => {
  const index = toasts.value.findIndex(t => t.id === id)
  if (index > -1) {
    toasts.value.splice(index, 1)
  }
}

const success = (message, duration) => show(message, 'success', duration)
const error = (message, duration) => show(message, 'error', duration)
const warning = (message, duration) => show(message, 'warning', duration)
const info = (message, duration) => show(message, 'info', duration)

provide('toast', { show, success, error, warning, info })
</script>

<template>
  <slot />
  
  <!-- Toast notifications -->
  <div class="fixed inset-0 flex items-end justify-center px-4 py-6 pointer-events-none sm:p-6 sm:items-start sm:justify-end z-50">
    <div class="flex flex-col space-y-3 w-full max-w-sm">
      <Toast
        v-for="toast in toasts"
        :key="toast.id"
        :message="toast.message"
        :type="toast.type"
        :duration="toast.duration"
        @close="remove(toast.id)"
      />
    </div>
  </div>
</template>
