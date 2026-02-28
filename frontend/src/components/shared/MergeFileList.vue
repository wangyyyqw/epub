<script setup>
import { ref } from 'vue'
import FileDropZone from '../FileDropZone.vue'

defineProps({
  files: { type: Array, required: true }
})

const emit = defineEmits(['drop', 'select', 'remove', 'clear', 'reorder'])

const dragIndex = ref(-1)

const fileName = (p) => p.split(/[\\/]/).pop()

const onDragStart = (index) => {
  dragIndex.value = index
}

const onDragOver = (event, index) => {
  event.preventDefault()
  if (dragIndex.value === -1 || dragIndex.value === index) return
  emit('reorder', dragIndex.value, index)
  dragIndex.value = index
}

const onDragEnd = () => {
  dragIndex.value = -1
}
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4 animate-slide-in">
    <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">合并文件列表</h2>

    <FileDropZone
      accept=".epub,application/epub+zip"
      :multiple="true"
      @drop="$emit('drop', $event)"
      @click="$emit('select')"
      :disabled="false"
    >
      <div class="flex flex-col items-center justify-center py-4 px-4 text-center">
        <div class="w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center mb-2">
          <svg class="w-5 h-5 text-indigo-600 dark:text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
        </div>
        <p class="text-sm font-medium text-gray-700 dark:text-gray-300">拖拽 EPUB 文件到此处添加到合并列表</p>
        <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">或点击选择文件，支持拖拽排序调整顺序</p>
      </div>
    </FileDropZone>

    <div v-if="files.length > 0" class="space-y-1">
      <div v-for="(p, idx) in files" :key="p + idx"
        draggable="true"
        @dragstart="onDragStart(idx)"
        @dragover="onDragOver($event, idx)"
        @dragend="onDragEnd"
        :class="[
          'flex items-center justify-between px-3 py-2 rounded-lg group cursor-grab active:cursor-grabbing transition-all',
          dragIndex === idx
            ? 'bg-indigo-50 dark:bg-indigo-900/30 border border-indigo-200 dark:border-indigo-700'
            : 'bg-gray-50 dark:bg-gray-900/50'
        ]"
      >
        <div class="flex items-center min-w-0 flex-1 mr-2">
          <span class="text-xs font-medium text-indigo-500 dark:text-indigo-400 mr-2 flex-shrink-0 w-5 text-center">{{ idx + 1 }}</span>
          <svg class="w-3.5 h-3.5 text-gray-300 dark:text-gray-600 mr-2 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 8h16M4 16h16" />
          </svg>
          <span class="text-xs text-gray-600 dark:text-gray-400 truncate" :title="p">{{ fileName(p) }}</span>
        </div>
        <button @click="$emit('remove', idx)" class="text-gray-400 hover:text-red-500 transition-colors flex-shrink-0 opacity-0 group-hover:opacity-100">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <button @click="$emit('clear')" class="text-xs text-gray-400 hover:text-red-500 transition-colors mt-1">清空全部文件</button>
    </div>

    <div v-if="files.length < 2" class="flex items-center space-x-2 text-xs text-amber-600 dark:text-amber-400">
      <svg class="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      <span>请至少添加 2 个 EPUB 文件才能执行合并</span>
    </div>
  </div>
</template>
