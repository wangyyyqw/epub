<script setup>
import { ref, nextTick, watch } from 'vue'

const props = defineProps({
  log: { type: String, default: '' },
  showOpenLog: { type: Boolean, default: false },
  opfContent: { type: String, default: '' }
})

const emit = defineEmits(['copy', 'copyOpf', 'clear', 'openLog'])

const logContainer = ref(null)

const scrollToBottom = async () => {
  await nextTick()
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

watch(() => props.log, () => { scrollToBottom() })

defineExpose({ scrollToBottom })
</script>

<template>
  <div v-if="log" class="bg-gray-900 rounded-xl overflow-hidden shadow-sm border border-gray-800">
    <div class="flex items-center justify-between px-4 py-2 bg-gray-800/50 border-b border-gray-800">
      <div class="flex items-center space-x-3">
        <h2 class="text-xs font-semibold text-gray-500 uppercase tracking-wider">输出日志</h2>
        <button @click="$emit('copy')" class="inline-flex items-center space-x-1 px-2 py-0.5 text-xs text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors">
          <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          <span>复制</span>
        </button>
        <button v-if="showOpenLog" @click="$emit('openLog')" class="inline-flex items-center space-x-1 px-2 py-0.5 text-xs text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors">
          <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
          <span>查看日志文件</span>
        </button>
        <button v-if="opfContent" @click="$emit('copyOpf')" class="inline-flex items-center space-x-1 px-2 py-0.5 text-xs text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors">
          <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          <span>复制 OPF 内容</span>
        </button>
      </div>
      <div class="flex space-x-1">
        <span class="w-2.5 h-2.5 rounded-full bg-red-400"></span>
        <span class="w-2.5 h-2.5 rounded-full bg-yellow-400"></span>
        <span class="w-2.5 h-2.5 rounded-full bg-green-400"></span>
      </div>
    </div>
    <pre ref="logContainer" class="text-xs text-green-400 font-mono whitespace-pre-wrap p-4 max-h-48 overflow-y-auto leading-relaxed">{{ log }}</pre>
  </div>
</template>
