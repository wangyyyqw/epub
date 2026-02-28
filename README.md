# EPUB 工具箱

一站式 EPUB 电子书处理工具，从创建到优化全覆盖。

## 功能特性

- **TXT → EPUB**：将纯文本文件转换为标准 EPUB 电子书，支持自动章节识别和分层目录
- **加密 / 解密**：对 EPUB 进行 DRM 加密或解密处理，支持字体混淆加密
- **EPUB 重构**：解包并重新打包 EPUB，修复结构错误，清理冗余文件
- **图片处理**：压缩图片体积、转换 WebP 格式、下载远程网络图片到本地
- **简繁转换**：简体繁体中文双向转换，基于词组级别精确转换
- **注音 / 注释**：为生僻字添加拼音注音，文本正则匹配生成脚注或弹窗注释
- **脚注转换**：阅微→多看、掌阅→多看脚注格式转换，支持 note.png 自动注入

## 技术栈

- **桌面框架**：Go + [Wails](https://wails.io/)
- **前端**：Vue 3 + Tailwind CSS
- **后端逻辑**：Python

## 运行方式

### 前置依赖

- Go 1.18+
- Node.js 14+
- Python 3.9+
- Wails CLI：`go install github.com/wailsapp/wails/v2/cmd/wails@latest`

### 开发模式

```bash
wails dev
```

### 构建发布

```bash
wails build
```

构建产物位于 `build/bin/` 目录。

## 致谢

感谢以下用户和项目的贡献：

- [遥遥心航](https://tieba.baidu.com/home/main?id=tb.1.7f262ae1.5_dXQ2Jp0F0MH9YJtgM2Ew)
- [lgernier](https://github.com/lgernier)
- [fontObfuscator](https://github.com/solarhell/fontObfuscator)
- [epub_tool](https://github.com/cnwxi/epub_tool?tab=readme-ov-file)
