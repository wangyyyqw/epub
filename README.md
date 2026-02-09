# TXT to EPUB Converter (TXT转EPUB工具)

一个主要面向中文网文的本地化 TXT 转 EPUB 工具。基于 Tauri + React + Python 构建，提供现代化的界面和强大的章节识别功能。

A modern, localized TXT to EPUB converter built with Tauri, React, and Python, featuring powerful chapter detection.

![App Screenshot](https://github.com/wangyyyqw/epub/raw/main/screenshot.png)

## ✨ 特性 (Features)

## ✨ 特性 (Features)

- **🎨 现代化 "Cosmic Glass" 界面**:
  - **星空毛玻璃设计**: 采用深色磨砂玻璃质感，搭配紫罗兰微光渐变，提供沉浸式体验。
  - **流畅交互**: 底部固定操作栏、平滑的过渡动画、以及优化的滚动体验。
  - **可视化组件**: 精致的文件上传区域、胶囊式按钮和清晰的进度展示。

- **🧠 智能章节识别 (Smart Detection)**:
  - **实时预览**: 扫描时直接显示匹配到的规则示例（如 "第1章..."），所见即所得。
  - **多级目录支持**:
    - 自定义标题级别 (h1 - h6)，比如将“卷”设为 h1，“章”设为 h2。
    - 自由启用/禁用特定规则。
  - **内置丰富正则**:
    - 中文数字/阿拉伯数字标题 (第十五章、Chapter 1)
    - 纯数字/特殊符号标题 (1. 标题、【第一章】)
    - 结构性标题 (卷、部、序言、后记)

- **� 标准化 EPUB 输出**:
  - **无干扰阅读**: 生成的 EPUB 不包含强制插入的 HTML 目录页 (nav)，阅读体验更连贯。
  - **标准结构**: 严格遵循 EPUB 3 标准 (OEBPS/META-INF)，兼容所有主流阅读器 (Apple Books, Kindle, etc.)。

- **🛠️ 强大的清理功能**:
  - 自动修复缩进。
  - 移除多余空行。
  - 自动提取书名与作者。
- **🔒完全本地处理**: 所有转换都在本地完成，无需上传文件，保护隐私。

## 🧰 EPUB 工具箱 (EPUB Toolbox)

除了基础的 TXT 转 EPUB 功能，本项目还提供了一系列强大的 EPUB 后处理工具：

### 资源优化
- **图片压缩**: 减小 EPUB 体积。
- **图片转换**: 支持 WebP 与 PNG/JPG 互转。
- **字体子集化**: 仅保留文中使用的字符，大幅减小字体文件体积。
- **下载网络图片**: 自动扫描并下载文中的网络图片到本地，实现离线阅读。

### 内容处理
- **繁简转换**: 高质量的繁简中文互转（OpenCC）。
- **生僻字注音**: 自动为文中生僻字添加拼音标注。
- **正则脚注**: 将 `[1]` 形式的注角转换为 EPUB 标准脚注。
- **正则/链接注释**: 
  - 将正则匹配的内容（如 `[注:...]`）转换为弹窗式注释。
  - 将 HTML 脚注链接（`<a href="#note">`）转换为弹窗式注释，自动提取内容并清理原注脚。
  - 自动注入注释图标资源。

### 排版与安全
- **格式化**: 优化 HTML 结构与排版。
- **加密/解密**: 支持 EPUB 内容加密及字体混淆。

## 🚀 安装 (Installation)

目前仅支持 macOS (Apple Silicon/Intel)。Windows 版本待开发。

下载最新 Release 中的 `.dmg` 文件安装即可。

## 🛠️ 开发与构建 (Build from Source)

### 环境要求
- Node.js (v18+)
- Rust (latest stable)
- Python 3.9+ (用于构建后端 binary)

### 构建步骤

1. **安装依赖**:
   ```bash
   cd txt2epub-app
   npm install
   ```

2. **构建后端 (Python)**:
   ```bash
   cd backend
   pip install -r requirements.txt
   # 使用 PyInstaller 打包
   python3 -m PyInstaller --onefile --name converter-backend main.py
   # 复制到 Tauri binary 目录
   cp dist/converter-backend ../src-tauri/binaries/converter-backend-aarch64-apple-darwin
   ```

3. **运行开发环境**:
   ```bash
   npm run tauri dev
   ```

4. **打包应用**:
   ```bash
   npm run tauri build
   npm run tauri build
   ```

## � 插件扩展 (Plugin Extension)

本项目采用插件化架构，方便扩展新的转换功能。

1. **创建插件目录**:
   在 `backend/plugins/` 下创建一个新目录（例如 `docx_to_epub`）。

2. **实现插件逻辑**:
   在该目录下创建 `plugin.py`，需引入 `BasePlugin`:
   ```python
   from core.plugin_base import BasePlugin
   
   class DocxToEpubPlugin(BasePlugin):
       # 实现抽象方法...
   ```
   并实现以下方法：
   - `name`: 插件唯一标识 (ID)。
   - `description`: 插件描述。
   - `register_arguments(parser)`: 注册该插件需要的命令行参数。
   - `run(args)`: 实现具体的转换逻辑。

3. **注册插件**:
   在 `backend/main.py` 的 `plugins` 字典中添加新插件：
   ```python
   plugins = {
       "txt2epub": TxtToEpubPlugin(),
       "docx2epub": DocxToEpubPlugin(),  # 新增插件
   }
   ```

本项目使用了以下开源技术：
- [Tauri](https://tauri.app/)
- [React](https://reactjs.org/)
- [Python](https://www.python.org/)
- [EbookLib](https://github.com/aerkalov/EbookLib)

---
License: MIT
