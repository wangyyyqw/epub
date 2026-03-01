<script setup>
import { ref, nextTick, inject, computed } from 'vue'
import FileDropZone from './FileDropZone.vue'
import PatternSelector from './shared/PatternSelector.vue'
import ChapterPreview from './shared/ChapterPreview.vue'
import OutputLog from './shared/OutputLog.vue'

const toast = inject('toast')

// --- State ---
const txtPath = ref('')
const epubPath = ref('')
const title = ref('')
const author = ref('Unknown')
const coverPath = ref('')
const coverSearchResults = ref([])
const coverSearching = ref(false)
const showCoverPicker = ref(false)
const coverDownloading = ref(false)
const customRegex = ref('')
const removeEmptyLine = ref(false)
const fixIndent = ref(false)
const splitChapterTitle = ref(false)
const headerImagePath = ref('')

const loading = ref(false)
const scanning = ref(false)
const outputLog = ref('')
const scanResults = ref(null)
const activeTab = ref('basic')

const selectedPatterns = ref([])
const chapterPreview = ref([])
const previewLoading = ref(false)

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
      if (node.children && node.children.length > 0) countNodes(node.children)
    }
  }
  countNodes(chapterPreview.value)
  return count
})

const warningCount = computed(() => chapterPreview.value.filter(c => c.hasWarning).length)
const wordWarningCount = computed(() => chapterPreview.value.filter(c => c.hasWordWarning).length)
const sequenceWarningCount = computed(() => chapterPreview.value.filter(c => c.sequenceWarning).length)

// --- Helper Functions ---
const extractNumber = (title) => {
  const chineseNums = {
    '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '百': 100, '千': 1000, '万': 10000,
    '〇': 0, '壹': 1, '贰': 2, '叁': 3, '肆': 4, '伍': 5, '陆': 6, '柒': 7, '捌': 8, '玖': 9, '拾': 10, '佰': 100, '仟': 1000
  }
  const arabicMatch = title.match(/\d+/)
  if (arabicMatch) return parseInt(arabicMatch[0])
  const chineseMatch = title.match(/[零一二两三四五六七八九十百千万〇壹贰叁肆伍陆柒捌玖拾佰仟]+/)
  if (chineseMatch) {
    const str = chineseMatch[0]
    let result = 0, section = 0, temp = 0
    for (let i = 0; i < str.length; i++) {
      const val = chineseNums[str[i]]
      if (val === 10000) {
        if (temp === 0 && section === 0) section = 1
        section += temp; result += section * val; section = 0; temp = 0
      } else if (val >= 10) {
        if (temp === 0) temp = 1
        section += temp * val; temp = 0
      } else { temp = val }
    }
    result += section + temp
    return result || null
  }
  return null
}

const checkSequence = (chapters) => {
  let prevNum = null
  for (const chapter of chapters) {
    const num = extractNumber(chapter.title)
    if (num !== null) {
      if (prevNum !== null && num <= prevNum) {
        chapter.sequenceWarning = true
        chapter.sequenceDetail = `序号 ${num} <= 前一章 ${prevNum}`
      }
      prevNum = num
    }
  }
}

// --- Methods ---
const handleTxtDrop = async (fileOrPath) => {
  if (!fileOrPath) return
  const path = typeof fileOrPath === 'string' ? fileOrPath : (fileOrPath.path || await window.go.main.App.SelectFile())
  if (path) {
    if (!path.toLowerCase().endsWith('.txt') && !path.toLowerCase().includes('.txt')) {
      toast?.error?.('请选择 TXT 文本文件'); return
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
  } catch (err) { console.error(err); toast?.error?.('选择文件失败') }
}

const selectEpubSavePath = async () => {
  try {
    const defaultName = title.value ? title.value + '.epub' : 'output.epub'
    const path = await window.go.main.App.SaveFile(defaultName)
    if (path) { epubPath.value = path; toast?.success?.('已设置输出路径') }
  } catch (err) { console.error(err); toast?.error?.('设置输出路径失败') }
}

const selectCoverFile = async () => {
  try {
    const path = await window.go.main.App.SelectFile()
    if (path) { coverPath.value = path; toast?.success?.('已选择封面图片') }
  } catch (err) { console.error(err); toast?.error?.('选择封面图片失败') }
}

const searchDoubanCover = async () => {
  const query = title.value?.trim()
  if (!query) { toast?.warning?.('请先填写书名'); return }
  coverSearching.value = true
  coverSearchResults.value = []
  showCoverPicker.value = true
  try {
    const raw = await window.go.main.App.SearchDoubanCover(query)
    const results = JSON.parse(raw)
    if (!results || results.length === 0) {
      toast?.warning?.('未找到相关图书')
      showCoverPicker.value = false
      return
    }
    coverSearchResults.value = results
    toast?.success?.(`找到 ${results.length} 个结果`)
  } catch (err) {
    console.error(err)
    toast?.error?.('搜索失败: ' + err)
    showCoverPicker.value = false
  } finally { coverSearching.value = false }
}

const selectDoubanCover = async (item) => {
  if (!item.cover_url) { toast?.error?.('该结果没有封面图片'); return }
  coverDownloading.value = true
  try {
    const raw = await window.go.main.App.DownloadDoubanCover(item.cover_url)
    const result = JSON.parse(raw)
    if (result.path) {
      coverPath.value = result.path
      showCoverPicker.value = false
      // 同时自动填充作者
      if (item.author && (!author.value || author.value === 'Unknown')) {
        author.value = item.author
      }
      toast?.success?.('封面已下载')
    }
  } catch (err) {
    console.error(err)
    toast?.error?.('下载封面失败: ' + err)
  } finally { coverDownloading.value = false }
}

const selectHeaderImage = async () => {
  try {
    const path = await window.go.main.App.SelectFile()
    if (path) { headerImagePath.value = path; toast?.success?.('已选择章节头图') }
  } catch (err) { console.error(err); toast?.error?.('选择章节头图失败') }
}

const scanChapters = async () => {
  if (!txtPath.value) { toast?.warning?.('请先选择 TXT 文件'); return }
  scanning.value = true
  outputLog.value = '▶ 正在扫描章节结构...\n'
  scanResults.value = null; selectedPatterns.value = []; chapterPreview.value = []
  const args = ['--plugin', 'txt2epub', '--txt-path', txtPath.value, '--epub-path', '/dev/null', '--title', 'scan', '--scan']
  try {
    const result = await window.go.main.App.RunBackend(args)
    if (result.stderr) outputLog.value += result.stderr + '\n'
    const data = JSON.parse(result.stdout)
    scanResults.value = data
    if (data.suggested_hierarchy && data.suggested_hierarchy.length > 0) {
      selectedPatterns.value = data.suggested_hierarchy.map((h, index) => ({
        ...h, enabled: true, order: index, split: h.split !== false
      }))
    }
    const patternCount = data.suggested_hierarchy?.length || 0
    outputLog.value += `✅ 扫描完成，找到 ${patternCount} 种章节模式\n`
    toast?.success?.(`扫描完成，找到 ${patternCount} 种章节模式`)
    await generatePreview()
  } catch (err) {
    outputLog.value += '❌ 扫描失败: ' + err + '\n'
    toast?.error?.('扫描失败: ' + err)
  } finally { scanning.value = false }
}

const generatePreview = async () => {
  if (!txtPath.value) { chapterPreview.value = []; return }
  if (!patternsString.value && selectedPatterns.value.filter(p => p.enabled).length === 0) {
    chapterPreview.value = []; return
  }
  previewLoading.value = true
  try {
    const chapters = []
    if (scanResults.value && scanResults.value.patterns) {
      const enabledPatterns = selectedPatterns.value.filter(p => p.enabled).sort((a, b) => a.order - b.order)
      for (const pattern of enabledPatterns) {
        const matched = scanResults.value.patterns.find(p => p.pattern === pattern.pattern)
        if (matched && matched.chapter_details) {
          const level = pattern.level
          const levelLabels = ['h1', 'h2', 'h3', 'h4']
          for (const detail of matched.chapter_details) {
            const wordCount = detail.word_count || 0
            const hasWordWarning = enableWordCountCheck.value && wordCount > wordCountThreshold.value
            chapters.push({
              title: detail.title, level, levelLabel: levelLabels[level] || 'h2',
              wordCount, hasWordWarning, sequenceWarning: false, sequenceDetail: '',
              hasWarning: hasWordWarning, children: []
            })
          }
        }
      }
      if (enableSequenceCheck.value) {
        checkSequence(chapters)
        chapters.forEach(c => { if (c.sequenceWarning) c.hasWarning = true })
      }
    }
    chapterPreview.value = chapters
  } catch (err) { console.error('Preview error:', err); chapterPreview.value = [] }
  finally { previewLoading.value = false }
}

const togglePattern = (pattern) => { pattern.enabled = !pattern.enabled; generatePreview() }
const movePatternUp = (index) => {
  if (index <= 0) return
  const temp = selectedPatterns.value[index].order
  selectedPatterns.value[index].order = selectedPatterns.value[index - 1].order
  selectedPatterns.value[index - 1].order = temp
  selectedPatterns.value.sort((a, b) => a.order - b.order); generatePreview()
}
const movePatternDown = (index) => {
  if (index >= selectedPatterns.value.length - 1) return
  const temp = selectedPatterns.value[index].order
  selectedPatterns.value[index].order = selectedPatterns.value[index + 1].order
  selectedPatterns.value[index + 1].order = temp
  selectedPatterns.value.sort((a, b) => a.order - b.order); generatePreview()
}
const selectAllPatterns = () => { selectedPatterns.value.forEach(p => p.enabled = true); generatePreview() }
const deselectAllPatterns = () => { selectedPatterns.value.forEach(p => p.enabled = false); generatePreview() }

const runConversion = async () => {
  if (!txtPath.value || !epubPath.value || !title.value) {
    const missing = []
    if (!txtPath.value) missing.push('TXT 文件')
    if (!epubPath.value) missing.push('EPUB 路径')
    if (!title.value) missing.push('书名')
    toast?.warning?.(`请填写: ${missing.join('、')}`); return
  }
  loading.value = true
  outputLog.value = '▶ 开始转换...\n'
  toast?.info?.('开始转换...', 2000)
  const args = ['--plugin', 'txt2epub', '--txt-path', txtPath.value, '--epub-path', epubPath.value, '--title', title.value, '--author', author.value]
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
      outputLog.value += '提示: 后端程序执行失败，请检查:\n  1. TXT 文件是否存在且可读\n  2. 输出目录是否有写入权限\n  3. Python 环境是否正确配置\n'
    }
    toast?.error?.('转换失败，请查看日志详情')
  } finally { loading.value = false }
}

const copyLog = async () => {
  try { await navigator.clipboard.writeText(outputLog.value); toast?.success?.('已复制日志到剪贴板') }
  catch { toast?.error?.('复制失败') }
}
const clearLog = () => { outputLog.value = ''; scanResults.value = null; selectedPatterns.value = []; chapterPreview.value = [] }

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
    <header>
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">TXT → EPUB</h1>
      <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">将纯文本文件转换为标准 EPUB 电子书</p>
    </header>

    <div class="flex space-x-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1 w-fit">
      <button v-for="tab in tabs" :key="tab.key" @click="activeTab = tab.key"
        :class="['px-4 py-1.5 text-sm font-medium rounded-md transition-all duration-150',
          activeTab === tab.key
            ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200']"
      >{{ tab.label }}</button>
    </div>

    <div class="flex-1 overflow-y-auto space-y-5">

      <!-- Basic Tab -->
      <template v-if="activeTab === 'basic'">
        <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
          <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">文件路径</h2>
          <div>
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
              TXT 文件 <span class="text-red-400">*</span>
            </label>
            <div class="space-y-2">
              <FileDropZone accept=".txt,text/plain" @drop="handleTxtDrop" @click="selectTxtFile" :disabled="false">
                <div class="flex flex-col items-center justify-center py-6 px-4 text-center">
                  <div class="w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center mb-2">
                    <svg class="w-5 h-5 text-indigo-600 dark:text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <p class="text-sm font-medium text-gray-700 dark:text-gray-300">
                    {{ txtPath ? txtPath.split(/[\\/]/).pop() : '拖拽 TXT 文件到此处' }}
                  </p>
                  <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">或点击选择文件</p>
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
          <div>
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">EPUB 输出路径</label>
            <div class="flex space-x-2">
              <input v-model="epubPath" type="text" :class="inputReadonlyClass" placeholder="输出路径（自动生成）" readonly @click="selectEpubSavePath">
              <button @click="selectEpubSavePath" :class="buttonSecondaryClass">浏览</button>
            </div>
          </div>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
          <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">元数据</h2>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">书名 <span class="text-red-400">*</span></label>
              <input v-model="title" type="text" :class="inputBaseClass" placeholder="输入书名">
            </div>
            <div>
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">作者</label>
              <input v-model="author" type="text" :class="inputBaseClass" placeholder="Unknown">
            </div>
          </div>
          <div>
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">封面图片 <span class="text-gray-400 font-normal">（可选）</span></label>
            <div class="flex space-x-2">
              <input v-model="coverPath" type="text" :class="inputReadonlyClass" placeholder="选择封面图片或从豆瓣搜索" readonly @click="selectCoverFile">
              <button @click="selectCoverFile" :class="buttonSecondaryClass">浏览</button>
              <button @click="searchDoubanCover" :disabled="coverSearching || !title"
                :class="['px-4 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-1',
                  coverSearching || !title
                    ? 'bg-gray-200 dark:bg-gray-700 text-gray-400 cursor-not-allowed'
                    : 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 hover:bg-amber-200 dark:hover:bg-amber-800/30 focus:ring-amber-400']"
              >
                <span v-if="coverSearching" class="flex items-center">
                  <svg class="animate-spin -ml-0.5 mr-1.5 h-3.5 w-3.5" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  搜索中
                </span>
                <span v-else>豆瓣</span>
              </button>
            </div>
            <!-- Douban Cover Picker -->
            <div v-if="showCoverPicker && coverSearchResults.length > 0" class="mt-3 p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-gray-200 dark:border-gray-600">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs font-medium text-gray-500 dark:text-gray-400">选择封面（{{ coverSearchResults.length }} 个结果）</span>
                <button @click="showCoverPicker = false" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
              <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 max-h-64 overflow-y-auto">
                <button v-for="item in coverSearchResults" :key="item.id" @click="selectDoubanCover(item)"
                  :disabled="coverDownloading"
                  class="flex flex-col items-center p-2 rounded-lg border border-gray-200 dark:border-gray-600 hover:border-indigo-400 dark:hover:border-indigo-500 hover:bg-white dark:hover:bg-gray-800 transition-all cursor-pointer group"
                >
                  <img v-if="item.cover_url" :src="item.cover_url" :alt="item.title"
                    class="w-16 h-22 object-cover rounded shadow-sm mb-1.5 group-hover:shadow-md transition-shadow"
                    loading="lazy" referrerpolicy="no-referrer"
                  >
                  <div v-else class="w-16 h-22 bg-gray-200 dark:bg-gray-700 rounded flex items-center justify-center mb-1.5">
                    <svg class="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                  </div>
                  <span class="text-xs text-gray-700 dark:text-gray-300 text-center line-clamp-1 w-full">{{ item.title }}</span>
                  <span class="text-[10px] text-gray-400 dark:text-gray-500 text-center line-clamp-1 w-full">{{ item.author }}</span>
                </button>
              </div>
              <div v-if="coverDownloading" class="mt-2 text-xs text-indigo-600 dark:text-indigo-400 flex items-center">
                <svg class="animate-spin mr-1.5 h-3.5 w-3.5" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                正在下载封面...
              </div>
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
              :class="['inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200',
                scanning || !txtPath
                  ? 'bg-gray-200 dark:bg-gray-700 text-gray-400 dark:text-gray-400 cursor-not-allowed'
                  : 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-200 dark:hover:bg-indigo-800/30']"
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
          <PatternSelector
            :patterns="selectedPatterns"
            @toggle="togglePattern"
            @moveUp="movePatternUp"
            @moveDown="movePatternDown"
            @selectAll="selectAllPatterns"
            @deselectAll="deselectAllPatterns"
            @updateLevel="generatePreview"
            @updateSplit="generatePreview"
          />
        </div>
      </template>

      <!-- Preview Tab -->
      <template v-if="activeTab === 'preview'">
        <ChapterPreview
          :chapters="chapterPreview"
          :totalChapters="totalChapters"
          :warningCount="warningCount"
          :wordWarningCount="wordWarningCount"
          :sequenceWarningCount="sequenceWarningCount"
          :previewLoading="previewLoading"
          :hasPatterns="!!patternsString"
          v-model:enableWordCountCheck="enableWordCountCheck"
          v-model:enableSequenceCheck="enableSequenceCheck"
          v-model:wordCountThreshold="wordCountThreshold"
          @refresh="generatePreview"
        />
      </template>

      <!-- Advanced Tab -->
      <template v-if="activeTab === 'advanced'">
        <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-5">
          <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">文本清理</h2>
          <div class="flex flex-wrap gap-6">
            <label class="flex items-center space-x-2.5 cursor-pointer group">
              <input v-model="removeEmptyLine" type="checkbox" class="h-4 w-4 rounded border-gray-300 dark:border-gray-600 text-indigo-600 dark:text-indigo-400 focus:ring-indigo-500 dark:focus:ring-indigo-400 bg-white dark:bg-gray-700 cursor-pointer">
              <span class="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white transition-colors">移除多余空行</span>
            </label>
            <label class="flex items-center space-x-2.5 cursor-pointer group">
              <input v-model="fixIndent" type="checkbox" class="h-4 w-4 rounded border-gray-300 dark:border-gray-600 text-indigo-600 dark:text-indigo-400 focus:ring-indigo-500 dark:focus:ring-indigo-400 bg-white dark:bg-gray-700 cursor-pointer">
              <span class="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white transition-colors">修复段落缩进</span>
            </label>
            <label class="flex items-center space-x-2.5 cursor-pointer group">
              <input v-model="splitChapterTitle" type="checkbox" class="h-4 w-4 rounded border-gray-300 dark:border-gray-600 text-indigo-600 dark:text-indigo-400 focus:ring-indigo-500 dark:focus:ring-indigo-400 bg-white dark:bg-gray-700 cursor-pointer">
              <span class="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white transition-colors">拆分章节标题 (序号/标题换行)</span>
            </label>
          </div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
          <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">样式增强</h2>
          <div>
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">章节头图 <span class="text-gray-400 font-normal">（可选）</span></label>
            <div class="flex space-x-2">
              <input v-model="headerImagePath" type="text" :class="inputReadonlyClass" placeholder="选择图片（显示在每章开头）" readonly @click="selectHeaderImage">
              <button @click="selectHeaderImage" :class="buttonSecondaryClass">浏览</button>
            </div>
            <p class="text-xs text-gray-400 mt-2">将在每个章节标题前插入该图片，自动应用居中和多看样式。</p>
          </div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
          <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">手动模式</h2>
          <div>
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">自定义正则 <span class="text-gray-400 font-normal">（单层模式，优先级高于自动扫描）</span></label>
            <input v-model="customRegex" type="text" :class="inputBaseClass + ' font-mono'" placeholder="例如: ^第[0-9]+章">
            <p class="text-xs text-gray-400 mt-2">留空则使用上方扫描结果或内置默认规则。</p>
          </div>
        </div>
      </template>

      <!-- Action Button -->
      <div class="flex items-center justify-between pt-2">
        <button v-if="outputLog" @click="clearLog" class="text-sm text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors">清除日志</button>
        <div v-else></div>
        <button @click="runConversion" :disabled="loading || !txtPath || !epubPath || !title"
          :class="['inline-flex items-center px-6 py-2.5 text-sm font-medium rounded-lg shadow-sm text-white transition-all duration-200',
            loading || !txtPath || !epubPath || !title
              ? 'bg-gray-300 dark:bg-gray-700 cursor-not-allowed'
              : 'bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-600 dark:hover:bg-indigo-500 hover:shadow-md active:scale-[0.98]']"
        >
          <svg v-if="loading" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          {{ loading ? '转换中...' : '开始转换' }}
        </button>
      </div>

      <OutputLog :log="outputLog" @copy="copyLog" />
    </div>
  </div>
</template>
