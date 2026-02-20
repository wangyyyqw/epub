<script setup>
import { ref } from 'vue'

const recentFiles = ref([])

const features = [
  { icon: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253', label: 'TXT → EPUB', desc: '将纯文本文件转换为标准 EPUB 电子书，支持自动章节识别和分层目录。', color: 'indigo' },
  { icon: 'M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z', label: '加密 / 解密', desc: '对 EPUB 进行 DRM 加密或解密处理，支持字体混淆加密。', color: 'amber' },
  { icon: 'M4 6h16M4 10h16M4 14h16M4 18h16', label: 'EPUB 重构', desc: '解包并重新打包 EPUB，修复结构错误，清理冗余文件。', color: 'emerald' },
  { icon: 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z', label: '图片处理', desc: '压缩图片体积、转换 WebP 格式、下载远程网络图片到本地。', color: 'rose' },
  { icon: 'M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129', label: '简繁转换', desc: '简体繁体中文双向转换，基于词组级别精确转换。', color: 'violet' },
  { icon: 'M7 20l4-16m2 16l4-16M6 9h14M4 15h14', label: '注音 / 注释', desc: '为生僻字添加拼音注音，文本正则匹配生成脚注或弹窗注释。', color: 'cyan' },
]

const colorMap = {
  indigo: { bg: 'bg-indigo-50 dark:bg-indigo-900/20', icon: 'text-indigo-500 dark:text-indigo-400', border: 'border-indigo-100 dark:border-indigo-800/30' },
  amber: { bg: 'bg-amber-50 dark:bg-amber-900/20', icon: 'text-amber-500 dark:text-amber-400', border: 'border-amber-100 dark:border-amber-800/30' },
  emerald: { bg: 'bg-emerald-50 dark:bg-emerald-900/20', icon: 'text-emerald-500 dark:text-emerald-400', border: 'border-emerald-100 dark:border-emerald-800/30' },
  rose: { bg: 'bg-rose-50 dark:bg-rose-900/20', icon: 'text-rose-500 dark:text-rose-400', border: 'border-rose-100 dark:border-rose-800/30' },
  violet: { bg: 'bg-violet-50 dark:bg-violet-900/20', icon: 'text-violet-500 dark:text-violet-400', border: 'border-violet-100 dark:border-violet-800/30' },
  cyan: { bg: 'bg-cyan-50 dark:bg-cyan-900/20', icon: 'text-cyan-500 dark:text-cyan-400', border: 'border-cyan-100 dark:border-cyan-800/30' },
}
</script>

<template>
  <div class="h-full flex flex-col space-y-8">
    <!-- Header -->
    <header>
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">欢迎使用 EPUB 工具箱</h1>
      <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">一站式 EPUB 电子书处理工具，从创建到优化全覆盖。</p>
    </header>

    <!-- Quick Start -->
    <div class="bg-gradient-to-br from-indigo-500 to-indigo-700 dark:from-indigo-600 dark:to-indigo-800 rounded-2xl p-6 text-white shadow-lg shadow-indigo-200 dark:shadow-none">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-lg font-semibold">快速开始</h2>
          <p class="text-indigo-100 text-sm mt-1">选择左侧菜单中的工具开始处理你的 EPUB 文件，或从 TXT 创建新的电子书。</p>
        </div>
        <svg class="h-16 w-16 text-indigo-300 opacity-50 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
        </svg>
      </div>
    </div>

    <!-- Feature Grid -->
    <div>
      <h2 class="text-sm font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-4">功能概览</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="f in features" :key="f.label"
          :class="['rounded-xl p-5 border transition-all duration-200 hover:shadow-md cursor-default dark:border-opacity-50', colorMap[f.color].bg, colorMap[f.color].border]"
        >
          <div class="flex items-center space-x-3 mb-3">
            <div :class="['p-2 rounded-lg bg-white/70 dark:bg-black/20', colorMap[f.color].icon]">
              <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" :d="f.icon" />
              </svg>
            </div>
            <h3 class="font-semibold text-gray-800 dark:text-gray-200 text-sm">{{ f.label }}</h3>
          </div>
          <p class="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">{{ f.desc }}</p>
        </div>
      </div>
    </div>

    <!-- Tips -->
    <div class="bg-gray-50 border border-gray-100 dark:bg-gray-800/50 dark:border-gray-700 rounded-xl p-5">
      <h2 class="text-sm font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-3">使用提示</h2>
      <ul class="space-y-2 text-sm text-gray-600 dark:text-gray-400">
        <li class="flex items-start">
          <span class="text-indigo-400 dark:text-indigo-500 mr-2 mt-0.5">•</span>
          <span>处理前建议备份原始文件，部分操作会直接修改源文件。</span>
        </li>
        <li class="flex items-start">
          <span class="text-indigo-400 dark:text-indigo-500 mr-2 mt-0.5">•</span>
          <span>TXT 转 EPUB 支持自动检测编码、智能章节识别和多级目录。</span>
        </li>
        <li class="flex items-start">
          <span class="text-indigo-400 dark:text-indigo-500 mr-2 mt-0.5">•</span>
          <span>图片处理工具可大幅缩减 EPUB 文件体积，推荐转换为 WebP 格式。</span>
        </li>
      </ul>
    </div>
  </div>
</template>
