<script setup>
import { ref, computed, watch, nextTick, inject } from 'vue'
import FileDropZone from './FileDropZone.vue'

const toast = inject('toast')

const props = defineProps({
  activeTool: String
})

// --- State ---
const inputPaths = ref([])
const outputPath = ref('')
const selectedOperation = ref('')
const fontPath = ref('')
const regexPattern = ref('')
const loading = ref(false)
const outputLog = ref('')
const logContainer = ref(null)
const operationCompleted = ref(false)

// Font encrypt target selection state
const fontTargets = ref({ font_families: [], xhtml_files: [] })
const selectedFontFamilies = ref([])
const selectedXhtmlFiles = ref([])
const showFontTargetSelector = ref(false)

// OPF viewer state
const opfContent = ref('')

watch(() => props.activeTool, (newVal) => {
  if (newVal) {
    selectedOperation.value = newVal
    inputPaths.value = []
    outputPath.value = ''
    fontPath.value = ''
    regexPattern.value = ''
    outputLog.value = ''
    operationCompleted.value = false
    fontTargets.value = { font_families: [], xhtml_files: [] }
    selectedFontFamilies.value = []
    selectedXhtmlFiles.value = []
    showFontTargetSelector.value = false
    opfContent.value = ''
  }
}, { immediate: true })

const operationsMap = {
  encrypt: { label: '加密 EPUB', desc: '对 EPUB 文件进行 DRM 加密处理', details: '使用文件名混淆等方式对 EPUB 内容进行保护。', category: 'encrypt' },
  decrypt: { label: '解密 EPUB', desc: '移除 EPUB 文件的 DRM 加密', details: '解密受保护的 EPUB 文件，还原为可自由阅读的格式。', category: 'encrypt' },
  encrypt_font: { label: '字体加密', desc: '对 EPUB 内嵌字体进行混淆加密', details: '按照 EPUB 规范对内嵌字体进行 Adobe 或 IDPF 方式的混淆处理，防止字体被直接提取使用。', category: 'encrypt' },
  reformat: { label: 'EPUB 重构', desc: '将 EPUB 重新构建为标准结构', details: '解包并按照标准规范重新打包 EPUB，修复文件结构错误，清理冗余文件，标准化文件名和目录结构（Sigil 规范）。', category: 'format' },
  convert_version: { label: '版本转换', desc: 'EPUB2 与 EPUB3 相互转换', details: '在 EPUB2.0 和 EPUB3.0 规范之间进行转换。', category: 'format', hasMode: true, modes: [{ value: '3.0', label: '转为 EPUB3' }, { value: '2.0', label: '转为 EPUB2' }] },
  convert_chinese: { label: '简繁转换', desc: '简体中文与繁体中文互转', details: '基于词组级别的精确转换，支持简转繁和繁转简双向转换。', category: 'format', hasMode: true, modes: [{ value: 's2t', label: '简体 → 繁体' }, { value: 't2s', label: '繁体 → 简体' }] },
  font_subset: { label: '字体子集化', desc: '精简 EPUB 内嵌字体，仅保留用到的字符', details: '分析 EPUB 内容中实际使用的字符，生成最小化的字体子集，可大幅缩减文件体积。', category: 'format' },
  view_opf: { label: 'OPF 查看', desc: '查看 EPUB 的 OPF 文件内容和内部结构', details: '从 EPUB 中提取 OPF 文件内容，以格式化 XML 形式展示，同时列出 EPUB 内部文件结构。', category: 'format' },
  img_compress: { label: '图片压缩', desc: '压缩 EPUB 中所有图片的体积', details: '在保持可接受画质的前提下压缩图片，有效减小 EPUB 文件大小。', category: 'image' },
  convert_image_format: { label: '图片格式转换', desc: '在图片和 WebP 格式之间互转', details: 'WebP 格式可大幅减小体积，传统图片格式兼容性更好。', category: 'image', hasMode: true, modes: [{ value: 'img_to_webp', label: '图片 → WebP' }, { value: 'webp_to_img', label: 'WebP → 图片' }] },
  phonetic: { label: '生僻字注音', desc: '为 EPUB 中的生僻字添加拼音注音', details: '自动识别生僻字并添加 Ruby 拼音标注，方便阅读生僻汉字。', category: 'annotate' },
  comment: { label: '正则匹配→弹窗', desc: '用正则表达式匹配文本并转为弹窗注释', details: '将匹配到的注释内容转换为多看/Kindle 支持的弹窗式注释，点击即可查看。', category: 'annotate', hasRegex: true },
  footnote_conv: { label: '脚注→弹窗', desc: '将已有的链接式脚注转为阅微弹窗样式', details: '将 EPUB 中已有的超链接脚注转换为阅微弹窗样式的注释，阅读更流畅。', category: 'annotate', hasRegex: true },
  download_images: { label: '下载网络图片', desc: '将 EPUB 中引用的网络图片下载到本地', details: '扫描 EPUB 中所有引用外部 URL 的图片，下载并嵌入到 EPUB 文件中，确保离线阅读正常。', category: 'other' },
  yuewei: { label: '阅微→多看', desc: '将阅微格式的注释转换为多看格式', details: '兼容阅微平台导出的 EPUB 注释格式，转换为多看阅读器支持的标准格式。', category: 'other' }
}

const currentToolInfo = computed(() => operationsMap[selectedOperation.value] || { label: '未知功能', desc: '', details: '' })
const needsFontPath = computed(() => selectedOperation.value === 'encrypt_font')
const needsRegex = computed(() => operationsMap[selectedOperation.value]?.hasRegex)
const needsMode = computed(() => operationsMap[selectedOperation.value]?.hasMode)
const selectedMode = ref('')

watch(selectedOperation, (val) => {
  if (operationsMap[val]?.hasMode) {
    selectedMode.value = operationsMap[val].modes[0].value
  } else {
    selectedMode.value = ''
  }
})

// --- Shared Style Classes ---
const inputBaseClass = 'w-full rounded-lg border border-gray-200 dark:border-gray-600 px-3 py-2.5 text-sm text-gray-700 dark:text-gray-200 bg-gray-50 dark:bg-gray-900/50 focus:bg-white dark:focus:bg-gray-800 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-900/30 outline-none transition-all'
const inputReadonlyClass = inputBaseClass + ' cursor-pointer'
const buttonBaseClass = 'px-4 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-1'
const buttonSecondaryClass = buttonBaseClass + ' bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 focus:ring-gray-400'

// --- Methods ---
const handleEpubDrop = (pathsOrPath) => {
  if (!pathsOrPath) return
  const paths = Array.isArray(pathsOrPath) ? pathsOrPath : [pathsOrPath]
  const epubPaths = paths.filter(p => typeof p === 'string' && p.toLowerCase().endsWith('.epub'))
  if (epubPaths.length === 0) {
    toast?.error?.('请选择 EPUB 文件')
    return
  }
  // Deduplicate with existing
  const existing = new Set(inputPaths.value)
  const newPaths = epubPaths.filter(p => !existing.has(p))
  if (newPaths.length > 0) {
    inputPaths.value = [...inputPaths.value, ...newPaths]
    toast?.success?.(`已添加 ${newPaths.length} 个文件`)
  }
}

const selectFile = async () => {
  try {
    const paths = await window.go.main.App.SelectFiles()
    if (paths && paths.length > 0) {
      handleEpubDrop(paths)
    }
  } catch (err) { console.error(err) }
}

const removeFile = (index) => {
  inputPaths.value.splice(index, 1)
}

const clearFiles = () => {
  inputPaths.value = []
}

const selectOutputPath = async () => {
  try {
    const path = await window.go.main.App.SelectDirectory()
    if (path) {
      outputPath.value = path
      toast?.success?.('已设置输出目录')
    }
  } catch (err) { console.error(err) }
}

const selectFontFile = async () => {
  try {
    const path = await window.go.main.App.SelectFile()
    if (path) {
      fontPath.value = path
      toast?.success?.('已选择字体文件')
    }
  } catch (err) { console.error(err) }
}

const scrollLogToBottom = async () => {
  await nextTick()
  if (logContainer.value) logContainer.value.scrollTop = logContainer.value.scrollHeight
}

const fileName = (p) => p.split(/[\\/]/).pop()

const scanFontTargets = async () => {
  if (inputPaths.value.length === 0) {
    toast?.warning?.('请先选择输入文件')
    return
  }
  loading.value = true
  const filePath = inputPaths.value[0]
  const name = fileName(filePath)
  outputLog.value = `▶ 扫描字体加密目标: ${name}\n${'─'.repeat(40)}\n`
  scrollLogToBottom()

  const args = ['--plugin', 'epub_tool', '--operation', 'list_font_targets', '--input-path', filePath]

  try {
    const result = await window.go.main.App.RunBackend(args)
    if (result.stderr) {
      outputLog.value += result.stderr + '\n'
      scrollLogToBottom()
    }
    const targets = JSON.parse(result.stdout)
    fontTargets.value = targets

    if (targets.font_families.length === 0 && targets.xhtml_files.length === 0) {
      toast?.warning?.('该 EPUB 无可加密的字体族或 XHTML 文件')
      outputLog.value += '⚠ 未找到可加密的字体族或 XHTML 文件\n'
      loading.value = false
      scrollLogToBottom()
      return
    }
    if (targets.font_families.length === 0) {
      toast?.warning?.('该 EPUB 无可加密的字体族')
      outputLog.value += '⚠ 未找到可加密的字体族\n'
    }
    if (targets.xhtml_files.length === 0) {
      toast?.warning?.('该 EPUB 无可加密的 XHTML 文件')
      outputLog.value += '⚠ 未找到可加密的 XHTML 文件\n'
    }

    // Default: select all
    selectedFontFamilies.value = [...targets.font_families]
    selectedXhtmlFiles.value = [...targets.xhtml_files]
    showFontTargetSelector.value = true

    outputLog.value += `✅ 扫描完成: 发现 ${targets.font_families.length} 个字体族, ${targets.xhtml_files.length} 个 XHTML 文件\n`
    toast?.success?.(`扫描完成，请选择要加密的目标`)
  } catch (err) {
    outputLog.value += `❌ 扫描失败: ${String(err)}\n`
    toast?.error?.('扫描字体加密目标失败，请重新选择文件')
  }
  loading.value = false
  scrollLogToBottom()
}

const toggleAllFontFamilies = () => {
  selectedFontFamilies.value = [...fontTargets.value.font_families]
}

const invertFontFamilies = () => {
  const current = new Set(selectedFontFamilies.value)
  selectedFontFamilies.value = fontTargets.value.font_families.filter(f => !current.has(f))
}

const toggleAllXhtmlFiles = () => {
  selectedXhtmlFiles.value = [...fontTargets.value.xhtml_files]
}

const invertXhtmlFiles = () => {
  const current = new Set(selectedXhtmlFiles.value)
  selectedXhtmlFiles.value = fontTargets.value.xhtml_files.filter(f => !current.has(f))
}

const cancelFontTargetSelection = () => {
  showFontTargetSelector.value = false
}

const runTool = async () => {
  if (inputPaths.value.length === 0 || !selectedOperation.value) {
    toast?.warning?.('请先选择输入文件')
    return
  }

  // Intercept encrypt_font: scan first if target selector not shown yet
  if (selectedOperation.value === 'encrypt_font' && !showFontTargetSelector.value) {
    await scanFontTargets()
    return
  }

  // Special handling for view_opf: only process first file, display OPF content
  if (selectedOperation.value === 'view_opf') {
    loading.value = true
    opfContent.value = ''
    const filePath = inputPaths.value[0]
    const name = fileName(filePath)
    outputLog.value = `▶ OPF 查看: ${name}\n${'─'.repeat(40)}\n`
    scrollLogToBottom()

    const args = ['--plugin', 'epub_tool', '--operation', 'view_opf', '--input-path', filePath]

    try {
      const result = await window.go.main.App.RunBackend(args)
      if (result.stderr) {
        outputLog.value += result.stderr + '\n'
      }
      if (result.stdout) {
        // Extract OPF content between markers
        const opfMatch = result.stdout.match(/=== OPF Content ===([\s\S]*?)(?==== File List ===|$)/)
        if (opfMatch) {
          opfContent.value = opfMatch[1].trim()
        }
        outputLog.value += result.stdout + '\n'
      }
      outputLog.value += `\n✅ OPF 查看完成\n`
      toast?.success?.('OPF 查看完成')
    } catch (err) {
      outputLog.value += `❌ 失败: ${String(err)}\n`
      toast?.error?.('OPF 查看失败')
    }
    loading.value = false
    operationCompleted.value = true
    scrollLogToBottom()
    return
  }

  loading.value = true
  const total = inputPaths.value.length
  let successCount = 0
  let failCount = 0
  outputLog.value = `▶ 批量执行: ${currentToolInfo.value.label}（共 ${total} 个文件）\n${'─'.repeat(40)}\n`
  toast?.info?.(`开始批量执行 ${total} 个文件...`, 2000)

  for (let i = 0; i < total; i++) {
    const filePath = inputPaths.value[i]
    const name = fileName(filePath)
    outputLog.value += `\n[${i + 1}/${total}] ${name}\n`
    scrollLogToBottom()

    const args = ['--plugin', 'epub_tool', '--operation', selectedOperation.value, '--input-path', filePath]
    if (fontPath.value && needsFontPath.value) args.push('--font-path', fontPath.value)
    if (outputPath.value) args.push('--output-path', outputPath.value)
    if (regexPattern.value && needsRegex.value) args.push('--regex-pattern', regexPattern.value)

    // Add font encrypt target arguments when user has made selections
    if (selectedOperation.value === 'encrypt_font' && showFontTargetSelector.value) {
      if (selectedFontFamilies.value.length > 0) {
        args.push('--target-font-families', ...selectedFontFamilies.value)
      }
      if (selectedXhtmlFiles.value.length > 0) {
        args.push('--target-xhtml-files', ...selectedXhtmlFiles.value)
      }
    }

    if (['convert_chinese', 'convert_image_format'].includes(selectedOperation.value)) {
      const opIndex = args.indexOf('--operation')
      if (opIndex > -1) args[opIndex + 1] = selectedMode.value
    } else if (selectedOperation.value === 'convert_version') {
      args.push('--target-version', selectedMode.value)
    }

    try {
      const result = await window.go.main.App.RunBackend(args)
      if (result.stderr) outputLog.value += result.stderr + '\n'
      if (result.stdout) outputLog.value += result.stdout + '\n'
      outputLog.value += `  ✅ 完成\n`
      successCount++
    } catch (err) {
      const errStr = String(err)
      if (errStr.includes('ZHANGYUE_DRM') || errStr.includes('zhangyue_drm')) {
        outputLog.value += `  ⚠️ 该文件为掌阅(ZhangYue)DRM加密书籍，因版权保护原因不支持解密处理\n`
        toast?.warning?.('检测到掌阅DRM加密，不支持解密')
      } else {
        outputLog.value += `  ❌ 失败: ${errStr}\n`
      }
      failCount++
    }
    scrollLogToBottom()
  }

  outputLog.value += `\n${'─'.repeat(40)}\n`
  outputLog.value += `📊 执行结果: 成功 ${successCount}，失败 ${failCount}，共 ${total} 个文件\n`
  loading.value = false
  operationCompleted.value = true
  // Reset font target selector after encrypt_font execution
  if (selectedOperation.value === 'encrypt_font') {
    showFontTargetSelector.value = false
    fontTargets.value = { font_families: [], xhtml_files: [] }
    selectedFontFamilies.value = []
    selectedXhtmlFiles.value = []
  }
  scrollLogToBottom()
  if (failCount === 0) {
    toast?.success?.(`全部完成（${successCount} 个文件）`)
  } else {
    toast?.warning?.(`完成: ${successCount} 成功, ${failCount} 失败`)
  }
}

const openLogFile = async () => {
  try {
    await window.go.main.App.OpenLogFile()
  } catch (err) {
    toast?.error?.('打开日志文件失败: ' + String(err))
  }
}

const copyLog = async () => {
  try {
    await navigator.clipboard.writeText(outputLog.value)
    toast?.success?.('已复制日志到剪贴板')
  } catch { toast?.error?.('复制失败') }
}

const copyOpfContent = async () => {
  try {
    await navigator.clipboard.writeText(opfContent.value)
    toast?.success?.('已复制 OPF 内容到剪贴板')
  } catch { toast?.error?.('复制失败') }
}

const clearLog = () => { outputLog.value = '' }
</script>

<template>
  <div class="h-full flex flex-col space-y-6">
    <!-- Header -->
    <header>
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{{ currentToolInfo.label }}</h1>
      <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{{ currentToolInfo.desc }}</p>
    </header>

    <div class="flex-1 overflow-y-auto space-y-5">

      <!-- Info Card -->
      <div v-if="currentToolInfo.details" class="bg-blue-50/80 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800/30 rounded-xl p-4">
        <div class="flex items-start">
          <svg class="w-4 h-4 text-blue-400 dark:text-blue-300 mt-0.5 mr-2.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p class="text-sm text-blue-700 dark:text-blue-200 leading-relaxed">{{ currentToolInfo.details }}</p>
        </div>
      </div>

      <!-- File Selection -->
      <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4">
        <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">文件设置</h2>

        <!-- Input Files with Drag Drop -->
        <div>
          <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
            输入文件 <span class="text-red-400">*</span>
            <span v-if="inputPaths.length > 0" class="ml-2 text-xs text-indigo-500 font-normal">已选 {{ inputPaths.length }} 个文件</span>
          </label>
          <div class="space-y-2">
            <FileDropZone
              accept=".epub,application/epub+zip"
              :multiple="true"
              @drop="handleEpubDrop"
              @click="selectFile"
              :disabled="false"
            >
              <div class="flex flex-col items-center justify-center py-6 px-4 text-center">
                <div class="w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center mb-2">
                  <svg class="w-5 h-5 text-indigo-600 dark:text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                </div>
                <p class="text-sm font-medium text-gray-700 dark:text-gray-300">拖拽 EPUB 文件到此处（支持多选）</p>
                <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">或点击选择文件</p>
              </div>
            </FileDropZone>

            <!-- File List -->
            <div v-if="inputPaths.length > 0" class="space-y-1">
              <div v-for="(p, idx) in inputPaths" :key="p"
                class="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-900/50 rounded-lg group"
              >
                <div class="flex items-center min-w-0 flex-1 mr-2">
                  <span class="text-xs text-gray-400 mr-2 flex-shrink-0">{{ idx + 1 }}.</span>
                  <span class="text-xs text-gray-600 dark:text-gray-400 truncate" :title="p">{{ fileName(p) }}</span>
                </div>
                <button @click="removeFile(idx)" class="text-gray-400 hover:text-red-500 transition-colors flex-shrink-0 opacity-0 group-hover:opacity-100">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <button @click="clearFiles" class="text-xs text-gray-400 hover:text-red-500 transition-colors mt-1">清空全部文件</button>
            </div>
          </div>
        </div>

        <!-- Output Path -->
        <div>
          <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
            输出目录 <span class="text-gray-400 font-normal">（可选）</span>
          </label>
          <div class="flex space-x-2">
            <input v-model="outputPath" type="text"
              :class="inputReadonlyClass"
              placeholder="默认为源文件同目录"
              readonly
              @click="selectOutputPath"
            >
            <button @click="selectOutputPath" :class="buttonSecondaryClass">浏览</button>
          </div>
        </div>
      </div>

      <!-- Font Path -->
      <div v-if="needsFontPath" class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4 animate-slide-in">
        <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">加密选项</h2>
        <div>
          <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
            字体文件 <span class="text-gray-400 font-normal">（可选）</span>
          </label>
          <div class="flex space-x-2">
            <input v-model="fontPath" type="text"
              :class="inputReadonlyClass"
              placeholder="选择字体文件用于混淆加密"
              readonly
              @click="selectFontFile"
            >
            <button @click="selectFontFile" :class="buttonSecondaryClass">浏览</button>
          </div>
        </div>
      </div>

      <!-- Mode Selection -->
      <div v-if="needsMode" class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4 animate-slide-in">
        <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">转换模式</h2>
        <div class="flex space-x-3">
          <label v-for="mode in currentToolInfo.modes" :key="mode.value"
            :class="[
              'flex-1 flex items-center justify-center px-4 py-2.5 rounded-lg border-2 cursor-pointer transition-all duration-150 text-sm font-medium',
              selectedMode === mode.value
                ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300'
                : 'border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:border-gray-300 dark:hover:border-gray-500'
            ]"
          >
            <input type="radio" v-model="selectedMode" :value="mode.value" class="sr-only">
            <span>{{ mode.label }}</span>
          </label>
        </div>
      </div>

      <!-- Regex Pattern -->
      <div v-if="needsRegex" class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-4 animate-slide-in">
        <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">正则选项</h2>
        <div>
          <label class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">正则表达式</label>
          <input v-model="regexPattern" type="text"
            :class="inputBaseClass + ' font-mono'"
            :placeholder="selectedOperation === 'footnote_conv' ? '默认: \\[(\\d+)\\] 或 #.+' : '默认: \\[(.*?)\\]'"
          >
          <p class="text-xs text-gray-400 mt-2">留空将使用默认正则表达式。</p>
        </div>
      </div>

      <!-- Font Encrypt Target Selector -->
      <div v-if="showFontTargetSelector" class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-100 dark:border-gray-700 space-y-5 animate-slide-in">
        <h2 class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">字体加密目标选择</h2>

        <!-- Font Families Section -->
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300">
              字体族
              <span class="ml-1 text-xs text-gray-400 font-normal">({{ selectedFontFamilies.length }}/{{ fontTargets.font_families.length }})</span>
            </label>
            <div class="flex space-x-2">
              <button @click="toggleAllFontFamilies" class="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">全选</button>
              <button @click="invertFontFamilies" class="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">反选</button>
            </div>
          </div>
          <div v-if="fontTargets.font_families.length === 0" class="text-xs text-gray-400 dark:text-gray-500 italic py-2">无可用字体族</div>
          <div v-else class="max-h-40 overflow-y-auto space-y-1 rounded-lg border border-gray-100 dark:border-gray-700 p-2 bg-gray-50 dark:bg-gray-900/50">
            <label v-for="family in fontTargets.font_families" :key="family"
              class="flex items-center px-2 py-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors"
            >
              <input type="checkbox" :value="family" v-model="selectedFontFamilies"
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
              <span class="ml-1 text-xs text-gray-400 font-normal">({{ selectedXhtmlFiles.length }}/{{ fontTargets.xhtml_files.length }})</span>
            </label>
            <div class="flex space-x-2">
              <button @click="toggleAllXhtmlFiles" class="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">全选</button>
              <button @click="invertXhtmlFiles" class="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">反选</button>
            </div>
          </div>
          <div v-if="fontTargets.xhtml_files.length === 0" class="text-xs text-gray-400 dark:text-gray-500 italic py-2">无可用 XHTML 文件</div>
          <div v-else class="max-h-48 overflow-y-auto space-y-1 rounded-lg border border-gray-100 dark:border-gray-700 p-2 bg-gray-50 dark:bg-gray-900/50">
            <label v-for="file in fontTargets.xhtml_files" :key="file"
              class="flex items-center px-2 py-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors"
            >
              <input type="checkbox" :value="file" v-model="selectedXhtmlFiles"
                class="w-3.5 h-3.5 rounded border-gray-300 dark:border-gray-600 text-indigo-600 focus:ring-indigo-500 dark:bg-gray-800"
              >
              <span class="ml-2 text-xs text-gray-600 dark:text-gray-400 font-mono truncate" :title="file">{{ file }}</span>
            </label>
          </div>
        </div>

        <!-- Confirm / Cancel Buttons -->
        <div class="flex items-center justify-end space-x-3 pt-2 border-t border-gray-100 dark:border-gray-700">
          <button @click="cancelFontTargetSelection"
            class="px-4 py-2 text-sm font-medium rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          >取消</button>
          <button @click="runTool"
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

      <!-- Action Button -->
      <div class="flex items-center justify-between pt-2">
        <button v-if="outputLog" @click="clearLog"
          class="text-sm text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
        >清除日志</button>
        <div v-else></div>
        <button
          @click="runTool"
          :disabled="loading || inputPaths.length === 0"
          :class="[
            'inline-flex items-center px-6 py-2.5 text-sm font-medium rounded-lg shadow-sm text-white transition-all duration-200',
            loading || inputPaths.length === 0
              ? 'bg-gray-300 dark:bg-gray-700 cursor-not-allowed'
              : 'bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-600 dark:hover:bg-indigo-500 hover:shadow-md active:scale-[0.98]'
          ]"
        >
          <svg v-if="loading" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          {{ loading ? '执行中...' : inputPaths.length > 1 ? `批量执行（${inputPaths.length} 个文件）` : '开始执行' }}
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
            <button v-if="operationCompleted" @click="openLogFile" class="inline-flex items-center space-x-1 px-2 py-0.5 text-xs text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors">
              <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              <span>查看日志文件</span>
            </button>
            <button v-if="opfContent" @click="copyOpfContent" class="inline-flex items-center space-x-1 px-2 py-0.5 text-xs text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors">
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
        <pre ref="logContainer" class="text-xs text-green-400 font-mono whitespace-pre-wrap p-4 max-h-48 overflow-y-auto leading-relaxed">{{ outputLog }}</pre>
      </div>

    </div>
  </div>
</template>

<style scoped>
.animate-slide-in {
  animation: slideIn 0.25s ease-out;
}
@keyframes slideIn {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
