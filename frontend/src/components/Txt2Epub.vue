<script setup>
import { ref, nextTick, inject, computed } from 'vue'
import FileDropZone from './FileDropZone.vue'

const toast = inject('toast')

// --- State ---
const txtPath = ref('')
const epubPath = ref('')
const title = ref('')
const author = ref('Unknown')
const coverPath = ref('')
const customRegex = ref('')
const removeEmptyLine = ref(false)
const fixIndent = ref(false)
const splitChapterTitle = ref(false)
const headerImagePath = ref('')

const loading = ref(false)
const scanning = ref(false)
const outputLog = ref('')
const logContainer = ref(null)
const scanResults = ref(null)
const activeTab = ref('basic')

// Selected patterns for hierarchical mode
const selectedPatterns = ref([])

// Chapter preview data
const chapterPreview = ref([])
const previewLoading = ref(false)

// Check settings
const wordCountThreshold = ref(5000)
const enableWordCountCheck = ref(true)
const enableSequenceCheck = ref(true)

// --- Computed ---
const hasSelectedPatterns = computed(() => selectedPatterns.value.length > 0)

const patternsString = computed(() => {
  return selectedPatterns.value
    .filter(p => p.enabled)
    .sort((a, b) => a.order - b.order)
    .map(p => `${p.pattern}:${p.level}:${p.split}`)
    .join(' ||| ')
})

const totalChapters = computed(() => {
  let count = 0
  const countNodes = (nodes) => {
    for (const node of nodes) {
      count++
      if (node.children && node.children.length > 0) {
        countNodes(node.children)
      }
    }
  }
  countNodes(chapterPreview.value)
  return count
})

const warningCount = computed(() => {
  return chapterPreview.value.filter(c => c.hasWarning).length
})

// --- Helper Functions ---
const extractNumber = (title) => {
  // Try to extract Chinese number
  const chineseNums = {
    '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '百': 100, '千': 1000, '万': 10000,
    '〇': 0, '壹': 1, '贰': 2, '叁': 3, '肆': 4, '伍': 5, '陆': 6, '柒': 7, '捌': 8, '玖': 9, '拾': 10, '佰': 100, '仟': 1000
  }
  
  // Try Arabic number first
  const arabicMatch = title.match(/\d+/)
  if (arabicMatch) {
    return parseInt(arabicMatch[0])
  }
  
  // Try Chinese number
  const chineseMatch = title.match(/[零一二两三四五六七八九十百千万〇壹贰叁肆伍陆柒捌玖拾佰仟]+/)
  if (chineseMatch) {
    const str = chineseMatch[0]
    let result = 0   // 最终结果
    let section = 0  // 万以下的部分
    let temp = 0     // 当前数字

    for (let i = 0; i < str.length; i++) {
      const char = str[i]
      const val = chineseNums[char]

      if (val === 10000) {
        // 万是高位单位，把之前累积的都乘上
        if (temp === 0 && section === 0) section = 1
        section += temp
        result += section * val
        section = 0
        temp = 0
      } else if (val >= 10) {
        // 十、百、千
        if (temp === 0) temp = 1
        section += temp * val
        temp = 0
      } else {
        temp = val
      }
    }
    // 加上剩余的
    result += section + temp
    return result || null
  }
  
  return null
}

const checkSequence = (chapters) => {
  let prevNum = null
  let prevIndex = -1
  
  for (let i = 0; i < chapters.length; i++) {
    const chapter = chapters[i]
    const num = extractNumber(chapter.title)
    
    if (num !== null) {
      if (prevNum !== null && num <= prevNum) {
        chapter.sequenceWarning = true
        chapter.sequenceDetail = `序号 ${num} <= 前一章 ${prevNum}`
      }
      prevNum = num
      prevIndex = i
    }
  }
}

// --- Methods ---
const handleTxtDrop = async (fileOrPath) => {
  if (!fileOrPath) return
  // Wails native drop gives us a path string directly
  const path = typeof fileOrPath === 'string' ? fileOrPath : (fileOrPath.path || await window.go.main.App.SelectFile())
  if (path) {
    if (!path.toLowerCase().endsWith('.txt') && !path.toLowerCase().includes('.txt')) {
      toast?.error?.('请选择 TXT 文本文件')
      return
    }
    txtPath.value = path
    const filename = path.split(/[\\/]/).pop()
    const name = filename.replace(/\.[^/.]+$/, '')
    if (!title.value) title.value = name
    if (!epubPath.value) epubPath.value = path.replace(/\.[^/.]+$/, '.epub')
    toast?.success?.(`已选择文件: ${filename}`)
  }
}

const selectTxtFile = async () => {
  try {
    const path = await window.go.main.App.SelectFile()
    if (path) {
      txtPath.value = path
      const filename = path.split(/[\\/]/).pop()
      const name = filename.replace(/\.[^/.]+$/, '')
      if (!title.value) title.value = name
      if (!epubPath.value) epubPath.value = path.replace(/\.[^/.]+$/, '.epub')
      toast?.success?.(`已选择文件: ${filename}`)
    }
  } catch (err) { 
    console.error(err)
    toast?.error?.('选择文件失败')
  }
}

const selectEpubSavePath = async () => {
  try {
    const defaultName = title.value ? title.value + '.epub' : 'output.epub'
    const path = await window.go.main.App.SaveFile(defaultName)
    if (path) {
      epubPath.value = path
      toast?.success?.('已设置输出路径')
    }
  } catch (err) { 
    console.error(err)
    toast?.error?.('设置输出路径失败')
  }
}

const selectCoverFile = async () => {
  try {
    const path = await window.go.main.App.SelectFile()
    if (path) {
      coverPath.value = path
      toast?.success?.('已选择封面图片')
    }
  } catch (err) { 
    console.error(err)
    toast?.error?.('选择封面图片失败')
  }
}

const selectHeaderImage = async () => {
  try {
    const path = await window.go.main.App.SelectFile()
    if (path) {
      headerImagePath.value = path
      toast?.success?.('已选择章节头图')
    }
  } catch (err) { 
    console.error(err)
    toast?.error?.('选择章节头图失败')
  }
}

const scrollLogToBottom = async () => {
  await nextTick()
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

const scanChapters = async () => {
  if (!txtPath.value) {
    toast?.warning?.('请先选择 TXT 文件')
    return
  }

  scanning.value = true
  outputLog.value = '▶ 正在扫描章节结构...\n'
  scanResults.value = null
  selectedPatterns.value = []
  chapterPreview.value = []

  const args = ['--plugin', 'txt2epub', '--txt-path', txtPath.value, '--epub-path', '/dev/null', '--title', 'scan', '--scan']

  try {
    const result = await window.go.main.App.RunBackend(args)
    if (result.stderr) outputLog.value += result.stderr + '\n'
    const data = JSON.parse(result.stdout)
    scanResults.value = data
    
    // Auto-select suggested patterns
    if (data.suggested_hierarchy && data.suggested_hierarchy.length > 0) {
      selectedPatterns.value = data.suggested_hierarchy.map((h, index) => ({
        ...h,
        enabled: true,
        order: index,
        split: h.split !== false
      }))
    }
    
    const patternCount = data.suggested_hierarchy?.length || 0
    outputLog.value += `✅ 扫描完成，找到 ${patternCount} 种章节模式\n`
    toast?.success?.(`扫描完成，找到 ${patternCount} 种章节模式`)
    
    // Auto-generate preview
    await generatePreview()
  } catch (err) {
    outputLog.value += '❌ 扫描失败: ' + err + '\n'
    toast?.error?.('扫描失败: ' + err)
  } finally {
    scanning.value = false
    scrollLogToBottom()
  }
}

const generatePreview = async () => {
  if (!txtPath.value) {
    chapterPreview.value = []
    return
  }
  
  if (!patternsString.value && selectedPatterns.value.filter(p => p.enabled).length === 0) {
    chapterPreview.value = []
    return
  }
  
  previewLoading.value = true
  
  try {
    const chapters = []
    
    // Build preview from scan results directly
    if (scanResults.value && scanResults.value.patterns) {
      const enabledPatterns = selectedPatterns.value.filter(p => p.enabled).sort((a, b) => a.order - b.order)
      
      for (const pattern of enabledPatterns) {
        const matched = scanResults.value.patterns.find(p => p.pattern === pattern.pattern)
        if (matched && matched.chapter_details) {
          const level = pattern.level
          const levelLabels = ['h1', 'h2', 'h3', 'h4']
          const levelLabel = levelLabels[level] || 'h2'
          
          for (const detail of matched.chapter_details) {
            const wordCount = detail.word_count || 0
            const hasWordWarning = enableWordCountCheck.value && wordCount > wordCountThreshold.value
            
            chapters.push({
              title: detail.title,
              level: level,
              levelLabel: levelLabel,
              wordCount: wordCount,
              hasWordWarning: hasWordWarning,
              sequenceWarning: false,
              sequenceDetail: '',
              hasWarning: hasWordWarning,
              children: []
            })
          }
        }
      }
      
      // Check sequence
      if (enableSequenceCheck.value) {
        checkSequence(chapters)
        chapters.forEach(c => {
          if (c.sequenceWarning) c.hasWarning = true
        })
      }
    }
    
    chapterPreview.value = chapters
  } catch (err) {
    console.error('Preview error:', err)
    chapterPreview.value = []
  } finally {
    previewLoading.value = false
  }
}

const togglePattern = (pattern) => {
  pattern.enabled = !pattern.enabled
  generatePreview()
}

const movePatternUp = (index) => {
  if (index <= 0) return
  const temp = selectedPatterns.value[index].order
  selectedPatterns.value[index].order = selectedPatterns.value[index - 1].order
  selectedPatterns.value[index - 1].order = temp
  selectedPatterns.value.sort((a, b) => a.order - b.order)
  generatePreview()
}

const movePatternDown = (index) => {
  if (index >= selectedPatterns.value.length - 1) return
  const temp = selectedPatterns.value[index].order
  selectedPatterns.value[index].order = selectedPatterns.value[index + 1].order
  selectedPatterns.value[index + 1].order = temp
  selectedPatterns.value.sort((a, b) => a.order - b.order)
  generatePreview()
}

const selectAllPatterns = () => {
  selectedPatterns.value.forEach(p => p.enabled = true)
  generatePreview()
}

const deselectAllPatterns = () => {
  selectedPatterns.value.forEach(p => p.enabled = false)
  generatePreview()
}

const runConversion = async () => {
  if (!txtPath.value || !epubPath.value || !title.value) {
    const missing = []
    if (!txtPath.value) missing.push('TXT 文件')
    if (!epubPath.value) missing.push('EPUB 路径')
    if (!title.value) missing.push('书名')
    toast?.warning?.(`请填写: ${missing.join('、')}`)
    return
  }

  loading.value = true
  outputLog.value = '▶ 开始转换...\n'
  toast?.info?.('开始转换...', 2000)

  const args = ['--plugin', 'txt2epub']
  args.push('--txt-path', txtPath.value)
  args.push('--epub-path', epubPath.value)
  args.push('--title', title.value)
  args.push('--author', author.value)

  if (coverPath.value) args.push('--cover-path', coverPath.value)
  if (customRegex.value) args.push('--custom-regex', customRegex.value)
  if (patternsString.value) args.push('--patterns', patternsString.value)
  if (removeEmptyLine.value) args.push('--remove-empty-line')
  if (fixIndent.value) args.push('--fix-indent')
  if (splitChapterTitle.value) args.push('--split-title')
  if (headerImagePath.value) args.push('--header-image', headerImagePath.value)

  try {
    const result = await window.go.main.App.RunBackend(args)
    if (result.stderr) outputLog.value += result.stderr + '\n'
    if (result.stdout) outputLog.value += result.stdout + '\n'
    outputLog.value += '✅ 转换完成！'
    toast?.success?.('转换完成！')
  } catch (err) {
    const errStr = String(err)
    outputLog.value += '❌ 错误: ' + errStr + '\n'
    
    if (errStr.includes('exit status 2')) {
      outputLog.value += '提示: 后端程序执行失败，请检查:\n'
      outputLog.value += '  1. TXT 文件是否存在且可读\n'
      outputLog.value += '  2. 输出目录是否有写入权限\n'
      outputLog.value += '  3. Python 环境是否正确配置\n'
    }
    
    toast?.error?.('转换失败，请查看日志详情')
  } finally {
    loading.value = false
    scrollLogToBottom()
  }
}

const copyLog = async () => {
  try {
    await navigator.clipboard.writeText(outputLog.value)
    toast?.success?.('已复制日志到剪贴板')
  } catch {
    toast?.error?.('复制失败')
  }
}

const clearLog = () => {
  outputLog.value = ''
  scanResults.value = null
  selectedPatterns.value = []
  chapterPreview.value = []
}

const tabs = [
  { key: 'basic', label: '基本设置' },
  { key: 'preview', label: '目录预览' },
  { key: 'advanced', label: '高级选项' },
]

const inputBaseClass = 'w-full rounded-lg border border-gray-200 dark:border-gray-600 px-3 py-2.5 text-sm text-gray-700 dark:text-gray-200 bg-gray-50 dark:bg-gray-900/50 focus:bg-white dark:focus:bg-gray-800 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-900/30 outline-none transition-all'
const inputReadonlyClass = inputBaseClass + ' cursor-pointer'
const buttonBaseClass = 'px-4 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-1'
const buttonPrimaryClass = buttonBaseClass + ' bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-600 dark:hover:bg-indigo-500 text-white shadow-sm hover:shadow active:scale-[0.98] focus:ring-indigo-500'
const buttonSecondaryClass = buttonBaseClass + ' bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 focus:ring-gray-400'
</script>

<template>
  <div class="h-full flex flex-col space-y-6">
    <!-- Header -->
    <header>
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">TXT → EPUB</h1>
      <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">将纯文本文件转换为标准 EPUB 电子书</p>
    </header>

    <!-- Tabs -->
    <div class="flex space-x-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1 w-fit">
      <button
        v-for="tab in tabs" :key="tab.key"
        @click="activeTab = tab.key"
        :class="[
          'px-4 py-1.5 text-sm font-medium rounded-md transition-all duration-150',
          activeTab === tab.key
            ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
        ]"
      >{{ tab.label }}</button>
    </div>

    <div class="flex-1 overflow-y-auto space-y-5">

      <!-- Basic Tab -->
      <template v-if="activeTab === 'basic'">
        <!-- File Input with Drag Drop -->
        <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
          <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">文件路径</h2>

          <!-- TXT File with Drag Drop -->
          <div>
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
              TXT 文件 <span class="text-red-400">*</span>
            </label>
            <div class="space-y-2">
              <FileDropZone
                accept=".txt,text/plain"
                @drop="handleTxtDrop"
                @click="selectTxtFile"
                :disabled="false"
              >
                <div class="flex flex-col items-center justify-center py-6 px-4 text-center">
                  <div class="w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center mb-2">
                    <svg class="w-5 h-5 text-indigo-600 dark:text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <p class="text-sm font-medium text-gray-700 dark:text-gray-300">
                    {{ txtPath ? txtPath.split(/[\\/]/).pop() : '拖拽 TXT 文件到此处' }}
                  </p>
                  <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">
                    或点击选择文件
                  </p>
                </div>
              </FileDropZone>
              <div v-if="txtPath" class="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-900/50 rounded-lg">
                <span class="text-xs text-gray-600 dark:text-gray-400 truncate flex-1 mr-2">{{ txtPath }}</span>
                <button @click="txtPath = ''" class="text-gray-400 hover:text-red-500 transition-colors">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          </div>

          <!-- EPUB Output Path -->
          <div>
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">EPUB 输出路径</label>
            <div class="flex space-x-2">
              <input v-model="epubPath" type="text"
                :class="inputReadonlyClass"
                placeholder="输出路径（自动生成）"
                readonly
                @click="selectEpubSavePath"
              >
              <button @click="selectEpubSavePath" :class="buttonSecondaryClass">
                浏览
              </button>
            </div>
          </div>
        </div>

        <!-- Metadata -->
        <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
          <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">元数据</h2>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                书名 <span class="text-red-400">*</span>
              </label>
              <input v-model="title" type="text"
                :class="inputBaseClass"
                placeholder="输入书名"
              >
            </div>
            <div>
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">作者</label>
              <input v-model="author" type="text"
                :class="inputBaseClass"
                placeholder="Unknown"
              >
            </div>
          </div>
          <div>
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
              封面图片 <span class="text-gray-400 font-normal">（可选）</span>
            </label>
            <div class="flex space-x-2">
              <input v-model="coverPath" type="text"
                :class="inputReadonlyClass"
                placeholder="选择封面图片"
                readonly
                @click="selectCoverFile"
              >
              <button @click="selectCoverFile" :class="buttonSecondaryClass">
                浏览
              </button>
            </div>
          </div>
        </div>

        <!-- Chapter Scan Section -->
        <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">章节识别</h2>
              <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">自动扫描并选择章节模式</p>
            </div>
            <button @click="scanChapters" :disabled="scanning || !txtPath"
              :class="[
                'inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200',
                scanning || !txtPath
                  ? 'bg-gray-200 dark:bg-gray-700 text-gray-400 dark:text-gray-400 cursor-not-allowed'
                  : 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-200 dark:hover:bg-indigo-800/30'
              ]"
            >
              <svg v-if="scanning" class="animate-spin -ml-0.5 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              {{ scanning ? '扫描中...' : '扫描章节' }}
            </button>
          </div>

          <div v-if="!txtPath" class="text-sm text-amber-600 bg-amber-50 dark:bg-amber-900/20 dark:text-amber-300 rounded-lg p-3">
            请先选择 TXT 文件
          </div>

          <!-- Pattern Selection (Visual) -->
          <div v-if="selectedPatterns.length > 0" class="space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-sm text-gray-600 dark:text-gray-400">已检测到 {{ selectedPatterns.length }} 种章节模式</span>
              <div class="flex space-x-2">
                <button @click="selectAllPatterns" class="text-xs text-indigo-600 dark:text-indigo-400 hover:underline">全选</button>
                <span class="text-gray-300 dark:text-gray-600">|</span>
                <button @click="deselectAllPatterns" class="text-xs text-gray-500 hover:underline">全不选</button>
              </div>
            </div>
            
            <div class="space-y-2">
              <div v-for="(pattern, index) in selectedPatterns" :key="index"
                @click="togglePattern(pattern)"
                :class="[
                  'flex items-center justify-between p-3 rounded-lg border-2 transition-all cursor-pointer',
                  pattern.enabled 
                    ? 'border-indigo-200 dark:border-indigo-800 bg-indigo-50 dark:bg-indigo-900/20' 
                    : 'border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 hover:border-gray-200 dark:hover:border-gray-600'
                ]"
              >
                <div class="flex items-center space-x-3">
                  <!-- Checkbox -->
                  <div :class="[
                    'w-5 h-5 rounded flex items-center justify-center transition-colors',
                    pattern.enabled ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-gray-700'
                  ]">
                    <svg v-if="pattern.enabled" class="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  
                  <!-- Level Badge -->
                  <div class="flex items-center space-x-2">
                    <select v-model="pattern.level" @click.stop @change="generatePreview"
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
                  <!-- Match Count -->
                  <span class="text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">
                    {{ pattern.count }} 处
                  </span>
                  
                  <!-- Split Toggle -->
                  <label @click.stop class="flex items-center space-x-1 text-xs text-gray-500 dark:text-gray-400">
                    <input v-model="pattern.split" type="checkbox" 
                      class="h-3 w-3 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                      @change="generatePreview"
                    >
                    <span>分割</span>
                  </label>
                  
                  <!-- Order Buttons -->
                  <div class="flex flex-col">
                    <button @click.stop="movePatternUp(index)" :disabled="index === 0"
                      :class="['text-gray-400 hover:text-indigo-600 disabled:opacity-30', 'leading-none']">
                      <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M5 15l7-7 7 7" />
                      </svg>
                    </button>
                    <button @click.stop="movePatternDown(index)" :disabled="index === selectedPatterns.length - 1"
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
              ✓ 已选择 {{ selectedPatterns.filter(p => p.enabled).length }} 种模式，点击「开始转换」即可生成多级目录的 EPUB
            </p>
          </div>
        </div>
      </template>

      <!-- Preview Tab -->
      <template v-if="activeTab === 'preview'">
        <!-- Check Settings -->
        <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
          <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">检查设置</h2>
          <div class="flex flex-wrap items-center gap-4">
            <label class="flex items-center space-x-2 cursor-pointer">
              <input v-model="enableWordCountCheck" type="checkbox"
                class="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                @change="generatePreview"
              >
              <span class="text-sm text-gray-700 dark:text-gray-300">字数检查</span>
            </label>
            <div v-if="enableWordCountCheck" class="flex items-center space-x-2">
              <span class="text-sm text-gray-500">超过</span>
              <input v-model.number="wordCountThreshold" type="number"
                class="w-20 px-2 py-1 text-sm rounded border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900/50 text-gray-700 dark:text-gray-200"
                @change="generatePreview"
              >
              <span class="text-sm text-gray-500">字高亮</span>
            </div>
            <label class="flex items-center space-x-2 cursor-pointer">
              <input v-model="enableSequenceCheck" type="checkbox"
                class="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                @change="generatePreview"
              >
              <span class="text-sm text-gray-700 dark:text-gray-300">断序检查</span>
            </label>
          </div>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">目录预览</h2>
              <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
                预览识别到的章节结构
                <span v-if="totalChapters > 0" class="text-indigo-600 dark:text-indigo-400 font-medium">
                  (共 {{ totalChapters }} 章)
                </span>
                <span v-if="warningCount > 0" class="text-amber-600 dark:text-amber-400 font-medium ml-2">
                  ⚠️ {{ warningCount }} 个警告
                </span>
              </p>
            </div>
            <button @click="generatePreview" :disabled="previewLoading || !patternsString"
              :class="[
                'inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
                previewLoading || !patternsString
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

          <div v-if="!patternsString" class="text-sm text-amber-600 bg-amber-50 dark:bg-amber-900/20 dark:text-amber-300 rounded-lg p-3">
            请先在「基本设置」中扫描并选择章节模式
          </div>

          <div v-else-if="chapterPreview.length === 0 && !previewLoading" class="text-sm text-gray-500 dark:text-gray-400 text-center py-8">
            <svg class="w-12 h-12 mx-auto text-gray-300 dark:text-gray-600 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            暂无章节预览，请点击「刷新预览」
          </div>

          <!-- Chapter List -->
          <div v-else class="max-h-96 overflow-y-auto border border-gray-100 dark:border-gray-700 rounded-lg">
            <div class="divide-y divide-gray-50 dark:divide-gray-700">
              <div v-for="(chapter, index) in chapterPreview" :key="index"
                :class="[
                  'flex items-center px-4 py-2.5 transition-colors',
                  chapter.hasWarning ? 'bg-amber-50 dark:bg-amber-900/20' : '',
                  !chapter.hasWarning && chapter.level === 0 ? 'bg-indigo-50/50 dark:bg-indigo-900/10' : '',
                  !chapter.hasWarning && chapter.level === 1 ? '' : '',
                  !chapter.hasWarning && chapter.level >= 2 ? 'bg-gray-50/50 dark:bg-gray-800/50' : '',
                  'hover:bg-gray-100 dark:hover:bg-gray-700/50'
                ]"
              >
                <!-- Level Indicator -->
                <div :class="[
                  'w-6 h-6 rounded flex items-center justify-center text-xs font-bold mr-3 flex-shrink-0',
                  chapter.hasWarning ? 'bg-amber-200 dark:bg-amber-800 text-amber-700 dark:text-amber-300' : '',
                  !chapter.hasWarning && chapter.level === 0 ? 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400' : '',
                  !chapter.hasWarning && chapter.level === 1 ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400' : '',
                  !chapter.hasWarning && chapter.level >= 2 ? 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400' : ''
                ]">
                  {{ chapter.levelLabel }}
                </div>
                
                <!-- Title -->
                <span :class="[
                  'text-sm truncate flex-1',
                  chapter.hasWarning ? 'text-amber-700 dark:text-amber-300 font-medium' : '',
                  !chapter.hasWarning && chapter.level === 0 ? 'font-semibold text-gray-900 dark:text-white' : '',
                  !chapter.hasWarning && chapter.level === 1 ? 'font-medium text-gray-800 dark:text-gray-200' : '',
                  !chapter.hasWarning && chapter.level >= 2 ? 'text-gray-600 dark:text-gray-400' : ''
                ]">
                  {{ chapter.title }}
                </span>
                
                <!-- Word Count -->
                <span v-if="chapter.wordCount !== undefined"
                  :class="[
                    'text-xs px-2 py-0.5 rounded ml-2 flex-shrink-0',
                    chapter.hasWordWarning 
                      ? 'bg-amber-200 dark:bg-amber-800 text-amber-700 dark:text-amber-300 font-medium' 
                      : 'text-gray-400 dark:text-gray-500 bg-gray-100 dark:bg-gray-700'
                  ]"
                >
                  {{ chapter.wordCount.toLocaleString() }} 字
                </span>
                
                <!-- Sequence Warning -->
                <span v-if="chapter.sequenceWarning"
                  class="text-xs px-2 py-0.5 rounded ml-2 bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 flex-shrink-0"
                  :title="chapter.sequenceDetail"
                >
                  ⚠️ 断序
                </span>
                
                <!-- Index -->
                <span class="text-xs text-gray-400 dark:text-gray-500 ml-2 flex-shrink-0">
                  #{{ index + 1 }}
                </span>
              </div>
            </div>
          </div>

          <div v-if="chapterPreview.length >= 100" class="text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded-lg p-2">
            章节数量较多 ({{ chapterPreview.length }} 章)，滚动查看更多
          </div>
        </div>
      </template>

      <!-- Advanced Tab -->
      <template v-if="activeTab === 'advanced'">
        <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-5">
          <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">文本清理</h2>
          <div class="flex flex-wrap gap-6">
            <label class="flex items-center space-x-2.5 cursor-pointer group">
              <input v-model="removeEmptyLine" type="checkbox"
                class="h-4 w-4 rounded border-gray-300 dark:border-gray-600 text-indigo-600 dark:text-indigo-400 focus:ring-indigo-500 dark:focus:ring-indigo-400 bg-white dark:bg-gray-700 cursor-pointer"
              >
              <span class="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white transition-colors">移除多余空行</span>
            </label>
            <label class="flex items-center space-x-2.5 cursor-pointer group">
              <input v-model="fixIndent" type="checkbox"
                class="h-4 w-4 rounded border-gray-300 dark:border-gray-600 text-indigo-600 dark:text-indigo-400 focus:ring-indigo-500 dark:focus:ring-indigo-400 bg-white dark:bg-gray-700 cursor-pointer"
              >
              <span class="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white transition-colors">修复段落缩进</span>
            </label>
            <label class="flex items-center space-x-2.5 cursor-pointer group">
              <input v-model="splitChapterTitle" type="checkbox"
                class="h-4 w-4 rounded border-gray-300 dark:border-gray-600 text-indigo-600 dark:text-indigo-400 focus:ring-indigo-500 dark:focus:ring-indigo-400 bg-white dark:bg-gray-700 cursor-pointer"
              >
              <span class="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white transition-colors">拆分章节标题 (序号/标题换行)</span>
            </label>
          </div>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
          <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">样式增强</h2>
          <div>
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
              章节头图 <span class="text-gray-400 font-normal">（可选）</span>
            </label>
            <div class="flex space-x-2">
              <input v-model="headerImagePath" type="text"
                :class="inputReadonlyClass"
                placeholder="选择图片（显示在每章开头）"
                readonly
                @click="selectHeaderImage"
              >
              <button @click="selectHeaderImage" :class="buttonSecondaryClass">
                浏览
              </button>
            </div>
            <p class="text-xs text-gray-400 mt-2">将在每个章节标题前插入该图片，自动应用居中和多看样式。</p>
          </div>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
          <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">手动模式</h2>
          <div>
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
              自定义正则 <span class="text-gray-400 font-normal">（单层模式，优先级高于自动扫描）</span>
            </label>
            <input v-model="customRegex" type="text"
              :class="inputBaseClass + ' font-mono'"
              placeholder="例如: ^第[0-9]+章"
            >
            <p class="text-xs text-gray-400 mt-2">留空则使用上方扫描结果或内置默认规则。</p>
          </div>
        </div>
      </template>

      <!-- Action Button -->
      <div class="flex items-center justify-between pt-2">
        <button v-if="outputLog" @click="clearLog"
          class="text-sm text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
        >清除日志</button>
        <div v-else></div>
        <button
          @click="runConversion"
          :disabled="loading || !txtPath || !epubPath || !title"
          :class="[
            'inline-flex items-center px-6 py-2.5 text-sm font-medium rounded-lg shadow-sm text-white transition-all duration-200',
            loading || !txtPath || !epubPath || !title
              ? 'bg-gray-300 dark:bg-gray-700 cursor-not-allowed'
              : 'bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-600 dark:hover:bg-indigo-500 hover:shadow-md active:scale-[0.98]'
          ]"
        >
          <svg v-if="loading" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          {{ loading ? '转换中...' : '开始转换' }}
        </button>
      </div>

      <!-- Log Output -->
      <div v-if="outputLog" class="bg-gray-900 rounded-xl overflow-hidden shadow-sm border border-gray-800">
        <div class="flex items-center justify-between px-4 py-2 bg-gray-800/50 border-b border-gray-800">
          <div class="flex items-center space-x-3">
            <h2 class="text-xs font-semibold text-gray-500 uppercase tracking-wider">输出日志</h2>
            <button @click="copyLog" class="inline-flex items-center space-x-1 px-2 py-0.5 text-xs text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors">
              <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              <span>复制</span>
            </button>
          </div>
          <div class="flex space-x-1">
            <span class="w-2.5 h-2.5 rounded-full bg-red-400"></span>
            <span class="w-2.5 h-2.5 rounded-full bg-yellow-400"></span>
            <span class="w-2.5 h-2.5 rounded-full bg-green-400"></span>
          </div>
        </div>
        <pre ref="logContainer" class="text-xs text-green-400 font-mono whitespace-pre-wrap p-4 max-h-48 overflow-y-auto leading-relaxed">{{ outputLog }}</pre>
      </div>

    </div>
  </div>
</template>
