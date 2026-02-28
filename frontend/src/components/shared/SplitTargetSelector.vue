<script setup>
defineProps({
  targets: { type: Array, required: true },
  selectedPoints: { type: Array, required: true }
})

const emit = defineEmits(['update:selectedPoints', 'toggleAll', 'invert', 'cancel', 'confirm'])

const onCheckChange = (idx, checked) => {
  // handled via v-model in parent
}
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4 animate-slide-in">
    <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">拆分点选择</h2>

    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <label class="text-sm font-medium text-gray-700 dark:text-gray-300">
          章节结构
          <span class="ml-1 text-xs text-gray-400 font-normal">(已选 {{ selectedPoints.length }}/{{ targets.length }})</span>
        </label>
        <div class="flex space-x-2">
          <button @click="$emit('toggleAll')" class="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">全选</button>
          <button @click="$emit('invert')" class="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">反选</button>
        </div>
      </div>
      <div class="max-h-64 overflow-y-auto space-y-1 rounded-lg border border-gray-100 dark:border-gray-700 p-2 bg-gray-50 dark:bg-gray-900/50">
        <label v-for="(target, idx) in targets" :key="idx"
          class="flex items-center px-2 py-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors"
          :style="{ paddingLeft: ((target.level - 1) * 1.5 + 0.5) + 'rem' }"
        >
          <input type="checkbox" :value="idx" :checked="selectedPoints.includes(idx)"
            @change="$emit('update:selectedPoints', $event.target.checked 
              ? [...selectedPoints, idx] 
              : selectedPoints.filter(i => i !== idx))"
            class="w-3.5 h-3.5 rounded border-gray-300 dark:border-gray-600 text-indigo-600 focus:ring-indigo-500 dark:bg-gray-800"
          >
          <span class="ml-2 text-sm text-gray-700 dark:text-gray-300 truncate" :title="target.href">{{ target.title }}</span>
        </label>
      </div>
    </div>

    <div v-if="selectedPoints.length === 0" class="flex items-center space-x-2 text-xs text-amber-600 dark:text-amber-400">
      <svg class="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      <span>请至少选择一个拆分点才能执行拆分</span>
    </div>

    <div class="flex items-center justify-end space-x-3 pt-2 border-t border-gray-100 dark:border-gray-700">
      <button @click="$emit('cancel')"
        class="px-4 py-2 text-sm font-medium rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
      >取消</button>
      <button @click="$emit('confirm')"
        :disabled="selectedPoints.length === 0"
        :class="[
          'px-4 py-2 text-sm font-medium rounded-lg shadow-sm text-white transition-all duration-200',
          selectedPoints.length === 0
            ? 'bg-gray-300 dark:bg-gray-700 cursor-not-allowed'
            : 'bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-600 dark:hover:bg-indigo-500'
        ]"
      >确认拆分</button>
    </div>
  </div>
</template>
