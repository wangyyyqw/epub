import { useState, useRef, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import "./App.css";

interface ScanResult {
  name: string;
  pattern: string;
  count: number;
  chapters: string[];
  suggested_level?: number;
  example?: string;
}

function App() {

  const [txtPath, setTxtPath] = useState("");
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);

  // Advanced Options
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [removeEmptyLines, setRemoveEmptyLines] = useState(false);
  const [fixIndent, setFixIndent] = useState(true);
  const [customRegex, setCustomRegex] = useState("");
  const [disabledPatterns, setDisabledPatterns] = useState<Set<string>>(new Set());

  // Scanning State
  const [allScanResults, setAllScanResults] = useState<ScanResult[]>([]);  // Raw unfiltered results
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);  // Filtered results (enabled patterns)
  const [selectedPatternIndex, setSelectedPatternIndex] = useState<number>(-1);
  const [patternLevels, setPatternLevels] = useState<Record<string, number>>({});  // Pattern name -> heading level (1-6)

  // Navigation & Toolbox State
  const [activeTab, setActiveTab] = useState<'converter' | 'toolbox'>('converter');
  const [toolOperation, setToolOperation] = useState<string>('reformat');
  const [toolInputPath, setToolInputPath] = useState('');
  const [toolFontPath, setToolFontPath] = useState('');
  const [toolRegexPattern, setToolRegexPattern] = useState('\\[(\\d+)\\]');

  const logEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Re-filter when disabledPatterns changes (no re-scan needed)
  useEffect(() => {
    if (allScanResults.length > 0) {
      const filtered = allScanResults.filter(r => !disabledPatterns.has(r.name));
      setScanResults(filtered);
    }
  }, [disabledPatterns, allScanResults]);

  function addLog(msg: string) {
    setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
  }

  function parseProgress(line: string) {
    // Expected format: "PROGRESS: 10% (Description)"
    const match = line.match(/PROGRESS:\s*(\d+)%/);
    if (match) {
      setProgress(parseInt(match[1]));
    }
  }

  async function scanFile(path: string) {
    setScanResults([]);
    setAllScanResults([]);
    setSelectedPatternIndex(-1);
    addLog("正在扫描章节结构...");

    try {
      const jsonResult = await invoke("scan_chapters", { txtPath: path });

      // Try to handle both old and new format
      let results: ScanResult[] = [];

      try {
        const parsed = JSON.parse(jsonResult as string);
        if (Array.isArray(parsed)) {
          // Old format: direct array
          results = parsed;
        } else if (parsed.patterns) {
          // New format: {patterns: [], suggested_hierarchy: []}
          results = parsed.patterns || [];
        }
      } catch (parseErr) {
        addLog(`[ERROR] JSON解析失败: ${parseErr}`);
      }

      // Store ALL results with matches for checkbox display
      const matchedResults = results.filter(r => r.count > 0);
      matchedResults.sort((a, b) => b.count - a.count);
      setAllScanResults(matchedResults);

      // Filter out disabled patterns
      const filteredResults = matchedResults.filter(r => !disabledPatterns.has(r.name));
      setScanResults(filteredResults);

      // Log summary
      const totalChapters = filteredResults.reduce((sum, r) => sum + r.count, 0);
      if (filteredResults.length > 0) {
        addLog(`扫描完成，发现 ${filteredResults.length} 个匹配规则，共 ${totalChapters} 个章节标记`);
      } else {
        addLog("扫描完成，未发现匹配章节。");

      }
    } catch (e) {
      addLog(`扫描失败: ${e}`);
    }
  }

  function handlePatternSelect(index: number) {
    setSelectedPatternIndex(index);
    setCustomRegex(scanResults[index].pattern);
  }

  async function selectTxt() {
    try {
      const selected = await open({
        multiple: false,
        filters: [{ name: 'Text', extensions: ['txt'] }]
      });
      if (selected) {
        const path = selected as string;
        setTxtPath(path);
        addLog(`已选择文件: ${path}`);

        // Auto-guess title
        const filename = path.split(/[\\/]/).pop()?.replace('.txt', '') || "";
        setTitle(filename);

        // Trigger Scan
        scanFile(path);
      }
    } catch (err) {
      addLog(`选择文件出错: ${err}`);
    }
  }

  async function convert() {
    if (!txtPath || !title) {
      addLog("错误: 请先选择文件并输入标题。");
      return;
    }

    try {
      const epubPath = await save({
        filters: [{ name: 'EPUB', extensions: ['epub'] }],
        defaultPath: `${title}.epub`,
        title: '保存 EPUB 文件'
      });

      if (!epubPath) return;

      setLoading(true);
      setProgress(0);
      addLog(`开始转换...`);
      addLog(`输出路径: ${epubPath}`);

      // Collect ALL enabled patterns with their levels
      // Format: pattern:level|||pattern:level (e.g., ^第.+章:1|||^第.+节:2)
      const patternsWithLevels = scanResults.map(r => {
        const level = patternLevels[r.name] || 1;
        return `${r.pattern}:${level}`;
      });

      if (patternsWithLevels.length > 0) {
        addLog(`使用 ${patternsWithLevels.length} 个规则进行分章:`);
        scanResults.forEach(r => {
          const level = patternLevels[r.name] || 1;
          addLog(`  - ${r.name} → h${level} (${r.count} 章)`);
        });
      } else if (customRegex) {
        addLog(`使用自定义正则: ${customRegex}`);
      }

      const result = await invoke("convert_book", {
        txtPath,
        epubPath,
        title,
        author,
        customRegex: patternsWithLevels.length === 0 ? (customRegex || null) : null,
        patterns: patternsWithLevels.length > 0 ? patternsWithLevels.join("|||") : null,
        removeEmptyLine: removeEmptyLines,
        fixIndent: fixIndent
      });



      const lines = (result as string).split('\n');
      lines.forEach(line => {
        if (line.trim()) {
          if (line.includes("PROGRESS:")) {
            parseProgress(line);
          } else {
            addLog(`> ${line}`);
          }
        }
      });

      addLog("转换任务已完成。");
      setProgress(100);
    } catch (error) {
      addLog(`严重错误: ${error}`);
      setLoading(false);
    }
  }

  async function selectToolEpub() {
    try {
      const selected = await open({
        multiple: false,
        filters: [{ name: 'EPUB', extensions: ['epub'] }]
      });
      if (selected) {
        const path = selected as string;
        setToolInputPath(path);
        addLog(`已选择 EPUB: ${path}`);
      }
    } catch (err) {
      addLog(`选择文件出错: ${err}`);
    }
  }

  async function selectToolFont() {
    try {
      const selected = await open({
        multiple: false,
        filters: [{ name: 'Font', extensions: ['ttf', 'otf', 'woff', 'woff2'] }]
      });
      if (selected) {
        const path = selected as string;
        setToolFontPath(path);
        addLog(`已选择字体: ${path}`);
      }
    } catch (err) {
      addLog(`选择文件出错: ${err}`);
    }
  }

  async function runToolOperation() {
    if (!toolInputPath) {
      addLog("错误: 请先选择 EPUB 文件。");
      return;
    }

    if (toolOperation === 'encrypt' && !toolFontPath) {
      addLog("提示: 加密操作建议选择字体文件");
    }

    setLoading(true);
    setProgress(0);
    addLog(`开始执行 ${toolOperation} 操作...`);

    try {
      const result = await invoke("run_epub_tool", {
        operation: toolOperation,
        inputPath: toolInputPath,
        fontPath: toolFontPath || null,
        regexPattern: toolRegexPattern || null
      });

      const lines = (result as string).split('\n');
      lines.forEach(line => {
        if (line.trim()) {
          addLog(`> ${line}`);
        }
      });

      addLog(`${toolOperation} 操作完成。`);
      setProgress(100);
    } catch (error) {
      addLog(`严重错误: ${error}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-container" style={{ animation: 'fadeIn 0.5s ease-out' }}>
      {/* Sidebar Navigation */}
      <div className="sidebar">
        <div
          className={`sidebar-item ${activeTab === 'converter' ? 'active' : ''}`}
          onClick={() => setActiveTab('converter')}
          title="TXT 转换器"
        >
          <span style={{ fontSize: '20px' }}>📄</span>
          <span>转换</span>
        </div>
        <div
          className={`sidebar-item ${activeTab === 'toolbox' ? 'active' : ''}`}
          onClick={() => setActiveTab('toolbox')}
          title="EPUB 工具箱"
        >
          <span style={{ fontSize: '20px' }}>🛠️</span>
          <span>工具</span>
        </div>
      </div>

      <div className="main-content">
        {activeTab === 'converter' ? (
          <>
            {/* Left Panel: TXT Converter Operations */}
            <div className="left-panel">
              <h1>TXT 转 EPUB</h1>

              <div className="left-panel-scroll">
                <div>
                  <div className="section-title">1. 选择文件</div>
                  <div className="file-drop-area" onClick={selectTxt}>
                    {txtPath ? (
                      <span className="file-name">
                        {txtPath.split(/[\\/]/).pop()}
                      </span>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
                        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ opacity: 0.5 }}>
                          <path d="M12 16L12 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                          <path d="M9 11L12 8 15 11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                          <path d="M8 16H16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                          <path d="M3 15V19C3 20.1 3.9 21 5 21H19C20.1 21 21 20.1 21 19V15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        <span>点击选择 .txt 文件</span>
                      </div>
                    )}
                  </div>
                  {txtPath && <div className="file-path">{txtPath}</div>}
                </div>

                <div>
                  <div className="section-title">2. 书籍信息</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <input
                      placeholder="书籍标题 *"
                      value={title}
                      onChange={e => setTitle(e.target.value)}
                    />
                    <input
                      placeholder="作者"
                      value={author}
                      onChange={e => setAuthor(e.target.value)}
                    />
                  </div>
                </div>

                <div>
                  <div
                    className="section-title"
                    style={{ cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                    onClick={() => setShowAdvanced(!showAdvanced)}
                  >
                    <span>3. 高级选项 & 章节结构</span>
                    <span style={{ marginLeft: 'auto', transform: showAdvanced ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.3s' }}>▼</span>
                  </div>

                  {showAdvanced && (
                    <div className="advanced-options-container">
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <label style={{ display: 'flex', alignItems: 'center', fontSize: '0.9em' }}>
                          <input
                            type="checkbox"
                            checked={removeEmptyLines}
                            onChange={e => setRemoveEmptyLines(e.target.checked)}
                            style={{ width: 'auto', marginRight: '8px' }}
                          />
                          去除多余空行
                        </label>
                        <label style={{ display: 'flex', alignItems: 'center', fontSize: '0.9em' }}>
                          <input
                            type="checkbox"
                            checked={fixIndent}
                            onChange={e => setFixIndent(e.target.checked)}
                            style={{ width: 'auto', marginRight: '8px' }}
                          />
                          修正首行缩进
                        </label>


                        <div style={{ marginTop: '10px' }}>
                          <div className="advanced-section-title">自定义正则表达式</div>
                          <input
                            placeholder="例如: ^第.+章"
                            value={customRegex}
                            onChange={e => {
                              setCustomRegex(e.target.value);
                              setSelectedPatternIndex(-1); // Clear selection if typing manually
                            }}
                            style={{ fontSize: '0.9em', width: '100%' }}
                          />
                        </div>

                        <div className="advanced-section-divider">
                          <div className="advanced-section-title">匹配到的规则 (设置标题级别)</div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            {allScanResults.length > 0 ? (
                              allScanResults.map(result => {
                                const activeIndex = scanResults.findIndex(r => r.name === result.name);
                                return (
                                  <div key={result.name} style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    fontSize: '0.85em',
                                    gap: '8px',
                                    padding: '6px 8px',
                                    backgroundColor: selectedPatternIndex === activeIndex && activeIndex !== -1 ? 'rgba(0,0,0,0.05)' : 'transparent',
                                    borderRadius: '6px',
                                    border: selectedPatternIndex === activeIndex && activeIndex !== -1 ? '1px solid var(--border-active)' : '1px solid transparent',
                                    transition: 'all 0.2s ease'
                                  }}>
                                    <input
                                      type="checkbox"
                                      checked={!disabledPatterns.has(result.name)}
                                      onChange={e => {
                                        const newSet = new Set(disabledPatterns);
                                        if (e.target.checked) {
                                          newSet.delete(result.name);
                                        } else {
                                          newSet.add(result.name);
                                        }
                                        setDisabledPatterns(newSet);
                                      }}
                                      style={{ width: 'auto', flexShrink: 0 }}
                                    />
                                    <select
                                      value={patternLevels[result.name] || 1}
                                      onChange={e => {
                                        setPatternLevels(prev => ({
                                          ...prev,
                                          [result.name]: parseInt(e.target.value)
                                        }));
                                      }}
                                      disabled={disabledPatterns.has(result.name)}
                                      onClick={(e) => e.stopPropagation()}
                                      style={{
                                        width: '60px',
                                        padding: '2px 4px',
                                        fontSize: '0.9em',
                                        opacity: disabledPatterns.has(result.name) ? 0.5 : 1,
                                        flexShrink: 0
                                      }}
                                    >
                                      <option value={1}>h1</option>
                                      <option value={2}>h2</option>
                                      <option value={3}>h3</option>
                                      <option value={4}>h4</option>
                                      <option value={5}>h5</option>
                                      <option value={6}>h6</option>
                                    </select>
                                    <span
                                      onClick={() => activeIndex >= 0 && handlePatternSelect(activeIndex)}
                                      style={{
                                        flex: 1,
                                        cursor: activeIndex >= 0 ? 'pointer' : 'default',
                                        opacity: disabledPatterns.has(result.name) ? 0.5 : 1,
                                        color: selectedPatternIndex === activeIndex && activeIndex !== -1 ? 'var(--accent)' : 'inherit',
                                        minWidth: 0,
                                        overflow: 'hidden'
                                      }}
                                    >
                                      <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontWeight: 500 }}>
                                        {result.name}
                                      </div>
                                      {result.example && (
                                        <div style={{ fontSize: '0.9em', color: 'var(--text-muted)', marginTop: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                          示例: {result.example}
                                        </div>
                                      )}
                                    </span>
                                    <span style={{
                                      color: 'var(--accent)',
                                      fontWeight: 'bold',
                                      fontSize: '0.9em',
                                      opacity: disabledPatterns.has(result.name) ? 0.5 : 1,
                                      flexShrink: 0,
                                      marginLeft: '4px'
                                    }}>
                                      {result.count}
                                    </span>
                                  </div>
                                );
                              })
                            ) : (
                              <div style={{ fontSize: '0.85em', color: 'var(--text-muted)' }}>
                                {txtPath ? '扫描中...' : '请先选择文件'}
                              </div>
                            )}
                          </div>
                        </div>


                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="left-panel-footer">
                {loading && (
                  <div style={{ marginBottom: '10px' }}>
                    <div className="progress-bar-bg">
                      <div className="progress-bar-fill" style={{ width: `${progress}%` }}></div>
                    </div>
                    <div style={{ textAlign: 'right', fontSize: '0.8em', color: '#666', marginTop: '2px' }}>{progress}%</div>
                  </div>
                )}
                <button
                  className="primary"
                  onClick={convert}
                  disabled={loading || !txtPath}
                  style={{ width: '100%', padding: '15px', fontSize: '1.1em' }}
                >
                  {loading ? "正在转换..." : "开始转换"}
                </button>
              </div>
            </div>

            {/* Right Panel: Logs & Output */}
            <div className="right-panel">
              <div className="section-title">输出日志</div>
              <div className="log-container">
                {logs.length === 0 && <div style={{ color: '#666', fontStyle: 'italic' }}>等待操作...</div>}
                {logs.map((log, i) => (
                  <div key={i} className="log-entry">
                    {log}
                  </div>
                ))}
                <div ref={logEndRef} />
              </div>

              {/* Full Chapter List Section - Moved to Right Panel */}
              {selectedPatternIndex >= 0 && scanResults[selectedPatternIndex] && (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                  <div className="section-title">完整章节列表 ({scanResults[selectedPatternIndex].chapters.length})</div>
                  <div className="chapter-list-container">
                    {scanResults[selectedPatternIndex].chapters.map((chapter, i) => (
                      <div key={i} className="chapter-list-item">
                        <span className="chapter-index">{i + 1}.</span>
                        <span className="chapter-title">{chapter}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        ) : (
          <>
            {/* Toolbox View */}
            <div className="left-panel">
              <h1>EPUB 工具箱</h1>

              <div className="left-panel-scroll">
                <div>
                  <div className="section-title">1. 选择操作</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <select
                      value={toolOperation}
                      onChange={e => setToolOperation(e.target.value)}
                      style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-medium)', background: 'var(--bg-input)' }}
                    >
                      <optgroup label="基础处理">
                        <option value="reformat">📐 重排 (Reformat)</option>
                        <option value="encrypt">🔒 加密 (Encrypt)</option>
                        <option value="decrypt">🔓 解密 (Decrypt)</option>
                      </optgroup>
                      <optgroup label="文本与辅助">
                        <option value="s2t">🇹 简体转繁体</option>
                        <option value="t2s">🇸 繁体转简体</option>
                        <option value="phonetic">🔤 生僻字注音</option>
                        <option value="pinyin">🔡 全文拼音标注</option>
                        <option value="yuewei">📖 阅微转多看</option>
                        <option value="footnote">📑 正则脚注处理</option>
                      </optgroup>
                      <optgroup label="资源优化">
                        <option value="font_subset">🔠 字体子集化</option>
                        <option value="img_compress">🖼️ 图片无损压缩</option>
                        <option value="img_to_webp">🕸️ 图片转 WebP</option>
                        <option value="webp_to_img">🖼️ WebP 转图片</option>
                      </optgroup>
                    </select>
                  </div>
                </div>

                <div>
                  <div className="section-title">2. 选择 EPUB 文件</div>
                  <div className="file-drop-area" onClick={selectToolEpub}>
                    {toolInputPath ? (
                      <span className="file-name">
                        {toolInputPath.split(/[\\\/]/).pop()}
                      </span>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
                        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ opacity: 0.5 }}>
                          <path d="M12 16L12 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                          <path d="M9 11L12 8 15 11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                          <path d="M8 16H16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                          <path d="M3 15V19C3 20.1 3.9 21 5 21H19C20.1 21 21 20.1 21 19V15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        <span>点击选择 .epub 文件</span>
                      </div>
                    )}
                  </div>
                  {toolInputPath && <div className="file-path">{toolInputPath}</div>}
                </div>

                {toolOperation === 'encrypt' && (
                  <div>
                    <div className="section-title">3. 选择字体文件 (可选)</div>
                    <div className="file-drop-area" onClick={selectToolFont} style={{ padding: '16px' }}>
                      {toolFontPath ? (
                        <span className="file-name">
                          {toolFontPath.split(/[\\\/]/).pop()}
                        </span>
                      ) : (
                        <span style={{ fontSize: '0.9em' }}>点击选择字体文件</span>
                      )}
                    </div>
                    {toolFontPath && <div className="file-path">{toolFontPath}</div>}
                  </div>
                )}

                {toolOperation === 'footnote' && (
                  <div>
                    <div className="section-title">3. 脚注匹配正则表达式</div>
                    <input
                      type="text"
                      value={toolRegexPattern}
                      onChange={e => setToolRegexPattern(e.target.value)}
                      placeholder="例如: \[(\d+)\]"
                    />
                    <div style={{ fontSize: '0.8em', color: 'var(--text-muted)', marginTop: '4px' }}>
                      默认: \[(\d+)\] (匹配 [1], [2] 等)
                    </div>
                  </div>
                )}
              </div>

              <div className="left-panel-footer">
                {loading && (
                  <div style={{ marginBottom: '10px' }}>
                    <div className="progress-bar-bg">
                      <div className="progress-bar-fill" style={{ width: `${progress}%` }}></div>
                    </div>
                    <div style={{ textAlign: 'right', fontSize: '0.8em', color: '#666', marginTop: '2px' }}>{progress}%</div>
                  </div>
                )}
                <button
                  className="primary"
                  onClick={runToolOperation}
                  disabled={loading || !toolInputPath}
                  style={{ width: '100%', padding: '15px', fontSize: '1.1em' }}
                >
                  {loading ? "处理中..." : "执行任务"}
                </button>
              </div>
            </div>

            {/* Right Panel: Same logs */}
            <div className="right-panel">
              <div className="section-title">输出日志</div>
              <div className="log-container">
                {logs.length === 0 && <div style={{ color: '#666', fontStyle: 'italic' }}>等待操作...</div>}
                {logs.map((log, i) => (
                  <div key={i} className="log-entry">
                    {log}
                  </div>
                ))}
                <div ref={logEndRef} />
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default App;
