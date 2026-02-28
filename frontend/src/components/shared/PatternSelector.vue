<script setup>
const props = defineProps({
  patterns: { type: Array, required: true }
})

const emit = defineEmits(['toggle', 'moveUp', 'moveDown', 'selectAll', 'deselectAll', 'updateLevel', 'updateSplit'])
</script>

<template>
  <div v-if="patterns.length > 0" class="space-y-3">
    <div class="flex items-center justify-between">
      <span class="text-sm text-gray-600 dark:text-gray-400">已检测到 {{ patterns.length }} 种章节模式</span>
      <div class="flex space-x-2">
        <button @click="$emit('selectAll')" class="text-xs text-indigo-600 dark:text-indigo-400 hover:underline">全选</button>
        <span class="text-gray-300 dark:text-gray-600">|</span>
        <button @click="$emit('deselectAll')" class="text-xs text-gray-500 hover:underline">全不选</button>
      </div>
    </div>
    
    <div class="space-y-2">
      <div v-for="(pattern, index) in patterns" :key="index"
        @click="$emit('toggle', pattern)"
        :class="[
          'flex items-center justify-between p-3 rounded-lg border-2 transition-all cursor-pointer',
          pattern.enabled 
            ? 'border-indigo-200 dark:border-indigo-800 bg-indigo-50 dark:bg-indigo-900/20' 
            : 'border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 hover:border-gray-200 dark:hover:border-gray-600'
        ]"
      >
        <div class="flex items-center space-x-3">
          <div :class="[
            'w-5 h-5 rounded flex items-center justify-center transition-colors',
            pattern.enabled ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-gray-700'
          ]">
            <svg v-if="pattern.enabled" class="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          
          <div class="flex items-center space-x-2">
            <select v-model="pattern.level" @click.stop @change="$emit('updateLevel')"
              class="text-xs font-bold rounded px-2 py-1 border-0 cursor-pointer
                     bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400
                     focus:ring-2 focus:ring-indigo-500"
            >
              <option :value="0">h1</option>
              <option :value="1">h2</option>
              <option :value="2">h3</option>
              <option :value="3">h4</option>
            </select>
            
            <div>
              <p class="text-sm font-medium text-gray-800 dark:text-gray-200">{{ pattern.name }}</p>
              <p class="text-xs text-gray-400 dark:text-gray-500 truncate max-w-xs">{{ pattern.example }}</p>
            </div>
          </div>
        </div>
        
        <div class="flex items-center space-x-2">
          <span class="text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">
            {{ pattern.count }} 处
          </span>
          
          <label @click.stop class="flex items-center space-x-1 text-xs text-gray-500 dark:text-gray-400">
            <input v-model="pattern.split" type="checkbox" 
              class="h-3 w-3 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              @change="$emit('updateSplit')"
            >
            <span>分割</span>
          </label>
          
          <div class="flex flex-col">
            <button @click.stop="$emit('moveUp', index)" :disabled="index === 0"
              :class="['text-gray-400 hover:text-indigo-600 disabled:opacity-30', 'leading-none']">
              <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 15l7-7 7 7" />
              </svg>
            </button>
            <button @click.stop="$emit('moveDown', index)" :disabled="index === patterns.length - 1"
              :class="['text-gray-400 hover:text-indigo-600 disabled:opacity-30', 'leading-none']">
              <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
    
    <p class="text-xs text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 rounded-lg p-2.5">
      ✓ 已选择 {{ patterns.filter(p => p.enabled).length }} 种模式，点击「开始转换」即可生成多级目录的 EPUB
    </p>
  </div>
</template>
