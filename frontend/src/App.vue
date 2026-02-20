<script setup>
import Sidebar from './components/Sidebar.vue'
import Dashboard from './components/Dashboard.vue'
import Txt2Epub from './components/Txt2Epub.vue'
import EpubTools from './components/EpubTools.vue'
import ToastContainer from './components/ToastContainer.vue'
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

const currentView = ref('dashboard')

// --- Theme Management ---
const theme = ref(localStorage.getItem('theme') || 'auto')

const applyTheme = (val) => {
  const isDark = val === 'dark' || (val === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  if (isDark) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

watch(theme, (val) => {
  localStorage.setItem('theme', val)
  applyTheme(val)
})

let mediaQuery = null
const onMediaChange = () => {
  if (theme.value === 'auto') applyTheme('auto')
}

onMounted(() => {
  applyTheme(theme.value)
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  mediaQuery.addEventListener('change', onMediaChange)
})

onUnmounted(() => {
  if (mediaQuery) {
    mediaQuery.removeEventListener('change', onMediaChange)
  }
})

const toggleTheme = () => {
  if (theme.value === 'light') theme.value = 'dark'
  else if (theme.value === 'dark') theme.value = 'auto'
  else theme.value = 'light'
}

const isEpubToolView = computed(() => {
  return currentView.value && currentView.value.startsWith('tool:')
})

const activeTool = computed(() => {
  if (isEpubToolView.value) {
    return currentView.value.split(':')[1]
  }
  return ''
})
</script>

<template>
  <ToastContainer>
    <div class="flex h-screen bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-100 font-sans antialiased transition-colors duration-200">
      <!-- Sidebar -->
      <Sidebar 
        @change-view="(view) => currentView = view" 
        :current-view="currentView"
        :current-theme="theme"
        @toggle-theme="toggleTheme"
      />

      <!-- Main Content -->
      <main class="flex-1 flex flex-col min-w-0 overflow-hidden bg-gray-50 dark:bg-gray-900 transition-colors duration-200">
        <!-- Window Drag Region (Right) -->
        <div class="h-10 w-full drag-region flex-shrink-0"></div>

        <!-- Scrollable Area -->
        <div class="flex-1 overflow-auto">
          <div class="max-w-4xl mx-auto px-8 py-2 pb-8">
            <Dashboard v-if="currentView === 'dashboard'" />
            <Txt2Epub v-else-if="currentView === 'txt2epub'" />
            <EpubTools v-else-if="isEpubToolView" :active-tool="activeTool" />
            <div v-else class="flex items-center justify-center h-full text-gray-400">
              <div class="text-center">
                <svg class="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
                <p class="mt-2 text-sm">{{ currentView }} — 开发中</p>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </ToastContainer>
</template>

<style>
.drag-region {
  --wails-draggable: drag;
}
</style>
