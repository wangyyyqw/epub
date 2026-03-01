<script setup>
defineProps({
  chapters: { type: Array, required: true },
  totalChapters: { type: Number, default: 0 },
  warningCount: { type: Number, default: 0 },
  wordWarningCount: { type: Number, default: 0 },
  sequenceWarningCount: { type: Number, default: 0 },
  previewLoading: { type: Boolean, default: false },
  hasPatterns: { type: Boolean, default: false },
  enableWordCountCheck: { type: Boolean, default: true },
  enableSequenceCheck: { type: Boolean, default: true },
  wordCountThreshold: { type: Number, default: 5000 }
})

const emit = defineEmits(['refresh', 'update:enableWordCountCheck', 'update:enableSequenceCheck', 'update:wordCountThreshold'])
</script>

<template>
  <!-- Check Settings -->
  <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
    <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">检查设置</h2>
    <div class="flex flex-wrap items-center gap-4">
      <label class="flex items-center space-x-2 cursor-pointer">
        <input :checked="enableWordCountCheck" type="checkbox"
          class="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
          @change="$emit('update:enableWordCountCheck', $event.target.checked); $emit('refresh')"
        >
        <span class="text-sm text-gray-700 dark:text-gray-300">字数检查</span>
      </label>
      <div v-if="enableWordCountCheck" class="flex items-center space-x-2">
        <span class="text-sm text-gray-500">超过</span>
        <input :value="wordCountThreshold" type="number"
          class="w-20 px-2 py-1 text-sm rounded border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900/50 text-gray-700 dark:text-gray-200"
          @change="$emit('update:wordCountThreshold', Number($event.target.value)); $emit('refresh')"
        >
        <span class="text-sm text-gray-500">字高亮</span>
      </div>
      <label class="flex items-center space-x-2 cursor-pointer">
        <input :checked="enableSequenceCheck" type="checkbox"
          class="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
          @change="$emit('update:enableSequenceCheck', $event.target.checked); $emit('refresh')"
        >
        <span class="text-sm text-gray-700 dark:text-gray-300">断序检查</span>
      </label>
    </div>
  </div>

  <!-- Chapter List -->
  <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">目录预览</h2>
        <div class="flex flex-wrap items-center gap-2 mt-1">
          <span v-if="totalChapters > 0" class="text-sm text-indigo-600 dark:text-indigo-400 font-medium">
            共 {{ totalChapters }} 章
          </span>
          <span v-if="wordWarningCount > 0"
            class="inline-flex items-center text-xs px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 font-medium"
          >📏 字数过大 {{ wordWarningCount }}</span>
          <span v-if="sequenceWarningCount > 0"
            class="inline-flex items-center text-xs px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 font-medium"
          >🔀 断序 {{ sequenceWarningCount }}</span>
        </div>
      </div>
      <button @click="$emit('refresh')" :disabled="previewLoading || !hasPatterns"
        :class="[
          'inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
          previewLoading || !hasPatterns
            ? 'bg-gray-200 dark:bg-gray-700 text-gray-400 cursor-not-allowed'
            : 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-200'
        ]"
      >
        <svg v-if="previewLoading" class="animate-spin -ml-0.5 mr-1.5 h-3 w-3" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        刷新预览
      </button>
    </div>

    <div v-if="!hasPatterns" class="text-sm text-amber-600 bg-amber-50 dark:bg-amber-900/20 dark:text-amber-300 rounded-lg p-3">
      请先在「基本设置」中扫描并选择章节模式
    </div>

    <div v-else-if="chapters.length === 0 && !previewLoading" class="text-sm text-gray-500 dark:text-gray-400 text-center py-8">
      <svg class="w-12 h-12 mx-auto text-gray-300 dark:text-gray-600 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      暂无章节预览，请点击「刷新预览」
    </div>

    <!-- Chapter Items -->
    <div v-else class="max-h-96 overflow-y-auto border border-gray-100 dark:border-gray-700 rounded-lg">
      <div class="divide-y divide-gray-50 dark:divide-gray-700">
        <div v-for="(chapter, index) in chapters" :key="index"
          :class="[
            'flex items-center px-4 py-2.5 transition-colors',
            chapter.sequenceWarning ? 'bg-red-50 dark:bg-red-900/10' : '',
            !chapter.sequenceWarning && chapter.hasWordWarning ? 'bg-amber-50 dark:bg-amber-900/20' : '',
            !chapter.hasWarning && chapter.level === 0 ? 'bg-indigo-50/50 dark:bg-indigo-900/10' : '',
            !chapter.hasWarning && chapter.level >= 2 ? 'bg-gray-50/50 dark:bg-gray-800/50' : '',
            'hover:bg-gray-100 dark:hover:bg-gray-700/50'
          ]"
        >
          <div :class="[
            'w-6 h-6 rounded flex items-center justify-center text-xs font-bold mr-3 flex-shrink-0',
            chapter.sequenceWarning ? 'bg-red-200 dark:bg-red-800 text-red-700 dark:text-red-300' : '',
            !chapter.sequenceWarning && chapter.hasWordWarning ? 'bg-amber-200 dark:bg-amber-800 text-amber-700 dark:text-amber-300' : '',
            !chapter.hasWarning && chapter.level === 0 ? 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400' : '',
            !chapter.hasWarning && chapter.level === 1 ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400' : '',
            !chapter.hasWarning && chapter.level >= 2 ? 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400' : ''
          ]">
            {{ chapter.levelLabel }}
          </div>
          
          <span :class="[
            'text-sm truncate flex-1',
            chapter.sequenceWarning ? 'text-red-700 dark:text-red-300 font-medium' : '',
            !chapter.sequenceWarning && chapter.hasWordWarning ? 'text-amber-700 dark:text-amber-300 font-medium' : '',
            !chapter.hasWarning && chapter.level === 0 ? 'font-semibold text-gray-900 dark:text-white' : '',
            !chapter.hasWarning && chapter.level === 1 ? 'font-medium text-gray-800 dark:text-gray-200' : '',
            !chapter.hasWarning && chapter.level >= 2 ? 'text-gray-600 dark:text-gray-400' : ''
          ]">
            {{ chapter.title }}
          </span>
          
          <span v-if="chapter.wordCount !== undefined"
            :class="[
              'text-xs px-2 py-0.5 rounded ml-2 flex-shrink-0',
              chapter.hasWordWarning 
                ? 'bg-amber-200 dark:bg-amber-800 text-amber-700 dark:text-amber-300 font-medium' 
                : 'text-gray-400 dark:text-gray-500 bg-gray-100 dark:bg-gray-700'
            ]"
          >
            {{ chapter.hasWordWarning ? '📏 ' : '' }}{{ chapter.wordCount.toLocaleString() }} 字
          </span>
          
          <span v-if="chapter.sequenceWarning"
            class="text-xs px-2 py-0.5 rounded ml-2 bg-red-200 dark:bg-red-900/40 text-red-700 dark:text-red-300 font-medium flex-shrink-0"
            :title="chapter.sequenceDetail"
          >🔀 {{ chapter.sequenceDetail }}</span>
          
          <span class="text-xs text-gray-400 dark:text-gray-500 ml-2 flex-shrink-0">
            #{{ index + 1 }}
          </span>
        </div>
      </div>
    </div>

    <div v-if="chapters.length >= 100" class="text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded-lg p-2">
      章节数量较多 ({{ chapters.length }} 章)，滚动查看更多
    </div>
  </div>
</template>
