<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { OnFileDrop, OnFileDropOff } from '../../wailsjs/runtime/runtime'

const props = defineProps({
  accept: { type: String, default: '*' },
  multiple: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['drop', 'click'])
const isDragging = ref(false)

const onDrop = (x, y, paths) => {
  if (props.disabled || !paths || paths.length === 0) return
  isDragging.value = false
  let filtered = paths
  if (props.accept && props.accept !== '*') {
    const exts = props.accept.split(',').map(t => t.trim()).filter(t => t.startsWith('.'))
    if (exts.length > 0) {
      filtered = paths.filter(p => exts.some(ext => p.toLowerCase().endsWith(ext)))
    }
  }
  if (filtered.length === 0) return
  if (!props.multiple) filtered = [filtered[0]]
  emit('drop', props.multiple ? filtered : filtered[0])
}

onMounted(() => { OnFileDrop(onDrop, true) })
onUnmounted(() => { OnFileDropOff() })

const handleDragOver = (e) => { if (props.disabled) return; e.preventDefault(); e.stopPropagation(); isDragging.value = true }
const handleDragLeave = (e) => { if (props.disabled) return; e.preventDefault(); e.stopPropagation(); isDragging.value = false }
const handleDrop = (e) => { e.preventDefault(); e.stopPropagation(); isDragging.value = false }
const handleClick = () => { if (!props.disabled) emit('click') }
</script>

<template>
  <div @dragover="handleDragOver" @dragleave="handleDragLeave" @drop="handleDrop" @click="handleClick" style="--wails-drop-target: drop" :class="['relative border-2 border-dashed rounded-xl transition-all duration-200 cursor-pointer', isDragging ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20 scale-[1.02]' : 'border-gray-300 dark:border-gray-600 hover:border-indigo-400 dark:hover:border-indigo-500 hover:bg-gray-50 dark:hover:bg-gray-800/50', disabled && 'opacity-50 cursor-not-allowed pointer-events-none']">
    <slot>
      <div class="flex flex-col items-center justify-center py-8 px-4 text-center">
        <div :class="['w-12 h-12 rounded-full flex items-center justify-center mb-3 transition-colors', isDragging ? 'bg-indigo-100 dark:bg-indigo-800/30 text-indigo-600 dark:text-indigo-400' : 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500']">
          <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
        </div>
        <p class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">拖拽文件到此处</p>
        <p class="text-xs text-gray-400 dark:text-gray-500">或点击选择文件</p>
      </div>
    </slot>
    <div v-if="isDragging" class="absolute inset-0 bg-indigo-500/5 dark:bg-indigo-500/10 rounded-xl pointer-events-none"></div>
  </div>
</template>
