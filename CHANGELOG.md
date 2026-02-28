# 更新日志

## v1.0.3

### 新增功能
- 新增「掌阅→多看」脚注转换功能（独立模块，支持掌阅 inline aside 格式）

### 优化改进
- 重构「阅微→多看」模块为模块化函数，提升可维护性
- TXT → EPUB 输出标准 EPUB 2.0 格式（移除 nav.xhtml、OPF 降级为 version 2.0）
- TXT → EPUB 首行缩进改用 CSS `text-indent: 2em`，不再插入全角空格字符
- 源文本原有的首行全角空格在转换时自动去除

### 修复
- 修复 note.png 注入后 OPF manifest 路径不正确的问题（改用 `posixpath.relpath` 计算相对路径）
- 修复掌阅脚注 `<img>` src 未替换为 note.png 的问题
- 修复图片目录检测逻辑，支持不同 EPUB 结构的 images 目录

## v1.0.2

### 修复
- 修复章节分割正则表达式被 `:` 截断的问题（如 `(?:...)` 非捕获组）
- 修复 Windows 下中文正则参数因 GBK 编码导致乱码的问题（改用临时文件传递 UTF-8 参数）
