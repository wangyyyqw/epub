<script setup>
defineProps({
  fontFamilies: { type: Array, default: () => [] },
  xhtmlFiles: { type: Array, default: () => [] },
  selectedFontFamilies: { type: Array, default: () => [] },
  selectedXhtmlFiles: { type: Array, default: () => [] }
})

const emit = defineEmits([
  'update:selectedFontFamilies', 'update:selectedXhtmlFiles',
  'toggleAllFonts', 'invertFonts', 'toggleAllXhtml', 'invertXhtml',
  'cancel', 'confirm'
])

const onFontChange = (family, checked) => {
  // handled via v-model in parent
}
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-5 animate-slide-in">
    <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">字体加密目标选择</h2>

    <!-- Font Families Section -->
    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <label class="text-sm font-medium text-gray-700 dark:text-gray-300">
          字体族
          <span class="ml-1 text-xs text-gray-400 font-normal">({{ selectedFontFamilies.length }}/{{ fontFamilies.length }})</span>
        </label>
        <div class="flex space-x-2">
          <button @click="$emit('toggleAllFonts')" class="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">全选</button>
          <button @click="$emit('invertFonts')" class="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">反选</button>
        </div>
      </div>
      <div v-if="fontFamilies.length === 0" class="text-xs text-gray-400 dark:text-gray-500 italic py-2">无可用字体族</div>
      <div v-else class="max-h-40 overflow-y-auto space-y-1 rounded-lg border border-gray-100 dark:border-gray-700 p-2 bg-gray-50 dark:bg-gray-900/50">
        <label v-for="family in fontFamilies" :key="family"
          class="flex items-center px-2 py-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors"
        >
          <input type="checkbox" :value="family" :checked="selectedFontFamilies.includes(family)"
            @change="$emit('update:selectedFontFamilies', $event.target.checked 
              ? [...selectedFontFamilies, family] 
              : selectedFontFamilies.filter(f => f !== family))"
            class="w-3.5 h-3.5 rounded border-gray-300 dark:border-gray-600 text-indigo-600 focus:ring-indigo-500 dark:bg-gray-800"
          >
          <span class="ml-2 text-sm text-gray-700 dark:text-gray-300">{{ family }}</span>
        </label>
      </div>
    </div>

    <!-- XHTML Files Section -->
    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <label class="text-sm font-medium text-gray-700 dark:text-gray-300">
          XHTML 文件
          <span class="ml-1 text-xs text-gray-400 font-normal">({{ selectedXhtmlFiles.length }}/{{ xhtmlFiles.length }})</span>
        </label>
        <div class="flex space-x-2">
          <button @click="$emit('toggleAllXhtml')" class="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">全选</button>
          <button @click="$emit('invertXhtml')" class="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">反选</button>
        </div>
      </div>
      <div v-if="xhtmlFiles.length === 0" class="text-xs text-gray-400 dark:text-gray-500 italic py-2">无可用 XHTML 文件</div>
      <div v-else class="max-h-48 overflow-y-auto space-y-1 rounded-lg border border-gray-100 dark:border-gray-700 p-2 bg-gray-50 dark:bg-gray-900/50">
        <label v-for="file in xhtmlFiles" :key="file"
          class="flex items-center px-2 py-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors"
        >
          <input type="checkbox" :value="file" :checked="selectedXhtmlFiles.includes(file)"
            @change="$emit('update:selectedXhtmlFiles', $event.target.checked 
              ? [...selectedXhtmlFiles, file] 
              : selectedXhtmlFiles.filter(f => f !== file))"
            class="w-3.5 h-3.5 rounded border-gray-300 dark:border-gray-600 text-indigo-600 focus:ring-indigo-500 dark:bg-gray-800"
          >
          <span class="ml-2 text-xs text-gray-600 dark:text-gray-400 font-mono truncate" :title="file">{{ file }}</span>
        </label>
      </div>
    </div>

    <!-- Confirm / Cancel Buttons -->
    <div class="flex items-center justify-end space-x-3 pt-2 border-t border-gray-100 dark:border-gray-700">
      <button @click="$emit('cancel')"
        class="px-4 py-2 text-sm font-medium rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
      >取消</button>
      <button @click="$emit('confirm')"
        :disabled="selectedFontFamilies.length === 0 && selectedXhtmlFiles.length === 0"
        :class="[
          'px-4 py-2 text-sm font-medium rounded-lg shadow-sm text-white transition-all duration-200',
          selectedFontFamilies.length === 0 && selectedXhtmlFiles.length === 0
            ? 'bg-gray-300 dark:bg-gray-700 cursor-not-allowed'
            : 'bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-600 dark:hover:bg-indigo-500'
        ]"
      >确认执行</button>
    </div>
  </div>
</template>
