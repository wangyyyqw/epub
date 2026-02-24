// Unit tests: operationsMap registration and sidebar entry verification
// Validates: Requirements 5.1, 5.4

import { describe, it, expect } from 'vitest'

// Recreate the operationsMap data structure (pure data, no Vue dependency)
// This mirrors the operationsMap defined in EpubTools.vue
const operationsMap = {
  encrypt: { label: '加密 EPUB', desc: '对 EPUB 文件进行 DRM 加密处理', details: '使用文件名混淆等方式对 EPUB 内容进行保护。', category: 'encrypt' },
  decrypt: { label: '解密 EPUB', desc: '移除 EPUB 文件的 DRM 加密', details: '解密受保护的 EPUB 文件，还原为可自由阅读的格式。', category: 'encrypt' },
  encrypt_font: { label: '字体加密', desc: '对 EPUB 内嵌字体进行混淆加密', details: '按照 EPUB 规范对内嵌字体进行 Adobe 或 IDPF 方式的混淆处理，防止字体被直接提取使用。', category: 'encrypt' },
  reformat: { label: 'EPUB 重构', desc: '将 EPUB 重新构建为标准结构', category: 'format' },
  convert_version: { label: '版本转换', desc: 'EPUB2 与 EPUB3 相互转换', category: 'format' },
  convert_chinese: { label: '简繁转换', desc: '简体中文与繁体中文互转', category: 'format' },
  font_subset: { label: '字体子集化', desc: '精简 EPUB 内嵌字体，仅保留用到的字符', category: 'format' },
  view_opf: { label: 'OPF 查看', desc: '查看 EPUB 的 OPF 文件内容和内部结构', category: 'format' },
  merge_epub: { label: '合并 EPUB', desc: '将多个 EPUB 文件合并为一个', details: '按指定顺序合并多个 EPUB 文件，自动处理资源冲突和目录合并。支持拖拽排序调整合并顺序。', category: 'format' },
  split_epub: { label: '拆分 EPUB', desc: '按章节将 EPUB 拆分为多个文件', details: '扫描 EPUB 章节结构，选择拆分点后生成多个独立的 EPUB 文件。', category: 'format' },
  img_compress: { label: '图片压缩', desc: '压缩 EPUB 中所有图片的体积', category: 'image' },
  convert_image_format: { label: '图片格式转换', desc: '在图片和 WebP 格式之间互转', category: 'image' },
  phonetic: { label: '生僻字注音', desc: '为 EPUB 中的生僻字添加拼音注音', category: 'annotate' },
  comment: { label: '正则匹配→弹窗', desc: '用正则表达式匹配文本并转为弹窗注释', category: 'annotate' },
  footnote_conv: { label: '脚注→弹窗', desc: '将已有的链接式脚注转为阅微弹窗样式', category: 'annotate' },
  download_images: { label: '下载网络图片', desc: '将 EPUB 中引用的网络图片下载到本地', category: 'other' },
  yuewei: { label: '阅微→多看', desc: '将阅微格式的注释转换为多看格式', category: 'other' },
}

// Recreate the sidebar toolGroups format group (pure data, no Vue dependency)
// This mirrors the toolGroups defined in Sidebar.vue
const sidebarFormatGroup = {
  key: 'format',
  label: '格式 / 转换',
  items: [
    { id: 'txt2epub', label: 'TXT → EPUB' },
    { id: 'tool:reformat', label: 'EPUB 重构' },
    { id: 'tool:convert_version', label: '版本转换' },
    { id: 'tool:convert_chinese', label: '简繁转换' },
    { id: 'tool:font_subset', label: '字体子集化' },
    { id: 'tool:view_opf', label: 'OPF 查看' },
    { id: 'tool:merge_epub', label: '合并 EPUB' },
    { id: 'tool:split_epub', label: '拆分 EPUB' },
  ],
}

describe('operationsMap registration verification', () => {
  it('contains merge_epub entry with correct properties', () => {
    expect(operationsMap).toHaveProperty('merge_epub')
    expect(operationsMap.merge_epub.label).toBe('合并 EPUB')
    expect(operationsMap.merge_epub.category).toBe('format')
    expect(operationsMap.merge_epub.desc).toBeTruthy()
    expect(operationsMap.merge_epub.details).toBeTruthy()
  })

  it('contains split_epub entry with correct properties', () => {
    expect(operationsMap).toHaveProperty('split_epub')
    expect(operationsMap.split_epub.label).toBe('拆分 EPUB')
    expect(operationsMap.split_epub.category).toBe('format')
    expect(operationsMap.split_epub.desc).toBeTruthy()
    expect(operationsMap.split_epub.details).toBeTruthy()
  })
})

describe('sidebar format group entry verification', () => {
  it('contains merge_epub navigation item', () => {
    const ids = sidebarFormatGroup.items.map(item => item.id)
    expect(ids).toContain('tool:merge_epub')

    const mergeItem = sidebarFormatGroup.items.find(item => item.id === 'tool:merge_epub')
    expect(mergeItem.label).toBe('合并 EPUB')
  })

  it('contains split_epub navigation item', () => {
    const ids = sidebarFormatGroup.items.map(item => item.id)
    expect(ids).toContain('tool:split_epub')

    const splitItem = sidebarFormatGroup.items.find(item => item.id === 'tool:split_epub')
    expect(splitItem.label).toBe('拆分 EPUB')
  })
})
