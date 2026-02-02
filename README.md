# TXT to EPUB Converter (TXT转EPUB工具)

一个主要面向中文网文的本地化 TXT 转 EPUB 工具。基于 Tauri + React + Python 构建，提供现代化的界面和强大的章节识别功能。

A modern, localized TXT to EPUB converter built with Tauri, React, and Python, featuring powerful chapter detection.

![App Screenshot](https://github.com/wangyyyqw/epub/raw/main/screenshot.png)

## ✨ 特性 (Features)

- **🔒完全本地处理**: 所有转换都在本地完成，无需上传文件，保护隐私。
- **🧠 智能章节识别**:
  - 内置多种预设正则，完美支持：
    - 中文数字标题 (第十五章、第一千零一章)
    - 阿拉伯数字标题 (第100章、Chapter 1)
    - 纯数字标题 (1. 标题、1、标题)
    - 特殊符号标题 (【第一章】、☆、标题)
    - 卷、部、集、篇 (卷一、第一部)
    - 序言、前言、后记、尾声 (智能识别非正文部分)
    - 分页/分节阅读标记识别
- **📑 多级目录支持 (Multi-level TOC)**:
  - 扫描后自动列出匹配到的规则。
  - **自定义标题级别**: 比如将“卷”设为 h1，“章”设为 h2，“节”设为 h3，生成层级分明的 EPUB 目录。
  - 自由启用/禁用特定规则。
- **🛠️ 强大的清理功能**:
  - 自动修复缩进。
  - 移除多余空行。
- **🎨 现代化界面**:
  - 支持拖拽上传。
  - 实时转换进度显示。
  - 自动元数据提取 (书名、作者)。

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
   ```

## 📝 鸣谢

本项目使用了以下开源技术：
- [Tauri](https://tauri.app/)
- [React](https://reactjs.org/)
- [Python](https://www.python.org/)
- [EbookLib](https://github.com/aerkalov/EbookLib)

---
License: MIT
